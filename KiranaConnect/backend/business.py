from decimal import Decimal
from typing import Literal, Protocol
import re
from pydantic import BaseModel, ConfigDict, Field
from .store import *


class Rule(ValueError):
    pass


class Duplicate(Rule):
    pass


class Strict(BaseModel):
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, allow_inf_nan=False
    )


class Line(Strict):
    product: str = Field(min_length=1, max_length=100)
    unit: str = Field(min_length=1, max_length=12)
    qty: Decimal = Field(ge=0, le=100000, decimal_places=3)
    price: Decimal | None = Field(default=None, gt=0, le=1000000, decimal_places=2)


class Proposal(Strict):
    kind: Literal["order", "invoice", "payment", "stock", "credit", "purchase"]
    ref: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]{1,79}$")
    party: str = Field(min_length=1, max_length=100)
    items: list[Line] = Field(default_factory=list, max_length=100)
    amount: Decimal | None = Field(default=None, gt=0, le=100000000, decimal_places=2)
    confidence: float = Field(default=1, ge=0, le=1)
    suspicious: bool = False


class Product(Strict):
    name: str = Field(min_length=1, max_length=100)
    unit: Literal["kg", "piece", "litre", "pack"]
    buy: Decimal = Field(gt=0, le=1000000, decimal_places=2)
    sell: Decimal = Field(gt=0, le=1000000, decimal_places=2)
    stock: Decimal = Field(ge=0, le=100000, decimal_places=3)
    threshold: Decimal = Field(ge=0, le=100000, decimal_places=3)


def cents(n):
    return int((Decimal(str(n)) * 100).quantize(Decimal("1")))


def owner(role):
    if role != "owner":
        raise PermissionError("Owner access required")


class Provider(Protocol):
    def status(self, ref: str, party: str, amount: int) -> str: ...


class MockProvider:
    def status(self, ref, party, amount):
        records = json.loads((ROOT / "samples" / "provider.json").read_text())
        decisions = {
            r["status"]
            for r in records
            if r.get("ref") == ref
            and r.get("party") == party
            and r.get("paise") == amount
            and r.get("currency") == "INR"
            and r.get("merchant") == "KC-DEMO"
        }
        if decisions == {"settled"}:
            return "verified"
        if decisions == {"confirmed fraudulent"}:
            return "rejected"
        return "pending verification"


class NoProvider:
    def status(self, *args):
        return "pending verification"


def provider() -> Provider:
    return MockProvider() if os.getenv("PAYMENT_PROVIDER") == "mock" else NoProvider()


def move(c, p, delta, res, reason):
    run(
        c,
        "update products set stock=round(stock+:d,3),reserved=round(reserved+:r,3) where id=:id",
        d=delta,
        r=res,
        id=p["id"],
    )
    run(
        c,
        "insert into movements(at,product,delta,reservation,reason) values(:at,:p,:d,:r,:why)",
        at=now(),
        p=p["name"],
        d=delta,
        r=res,
        why=reason,
    )


def save_product(c, role, actor, data, pid=None):
    owner(role)
    d = Product.model_validate(data)
    args = dict(
        name=d.name,
        unit=d.unit,
        buy=cents(d.buy),
        sell=cents(d.sell),
        threshold=float(d.threshold),
    )
    if pid is None:
        pid = run(
            c,
            "insert into products(name,unit,buy,sell,threshold,stock) values(:name,:unit,:buy,:sell,:threshold,0)",
            **args
        ).lastrowid
    p = one(c, "select * from products where id=:id and active=1", id=pid)
    if not p or float(d.stock) < p["reserved"]:
        raise Rule("Missing product or stock below reservations")
    if p["unit"] != d.unit or (p["reserved"] and p["name"] != d.name):
        raise Rule("Unit is fixed. Fulfil reservations before renaming.")
    run(
        c,
        "update products set name=:name,buy=:buy,sell=:sell,threshold=:threshold where id=:id",
        id=pid,
        **args
    )
    move(c, {**p, "name": d.name}, float(d.stock) - p["stock"], 0, "Catalog edit")
    audit(c, actor, "catalog.saved", d.name)
    return pid


def execute(c, proposal, role, actor, approved=False, job=None):
    d = Proposal.model_validate(proposal)
    if one(c, "select id from records where kind=:k and ref=:r", k=d.kind, r=d.ref):
        raise Duplicate("Business reference already processed")
    if d.suspicious or d.confidence < 0.90:
        raise Rule("Suspicious content or confidence below 90%")
    if d.kind in ("credit", "stock", "purchase") or approved:
        owner(role)
    amount = cents(d.amount) if d.amount else 0
    status = {
        "order": "reserved",
        "invoice": "received",
        "stock": "counted",
        "credit": "debited",
        "purchase": "requested",
        "payment": "pending verification",
    }[d.kind]
    if d.kind in ("credit", "payment"):
        if not amount or d.items:
            raise Rule("Expected an amount and no line items")
        if d.kind == "payment":
            status = provider().status(d.ref, d.party, amount)
    else:
        if not d.items:
            raise Rule("Missing line items")
        total = 0
        seen = set()
        for item in d.items:
            p = one(
                c, "select * from products where name=:p and active=1", p=item.product
            )
            if not p or p["unit"] != item.unit or p["id"] in seen:
                raise Rule(
                    "Unknown, repeated or unit-mismatched product: " + item.product
                )
            seen.add(p["id"])
            q = float(item.qty)
            if q == 0 and d.kind != "stock":
                raise Rule("Positive quantity required")
            if p["unit"] in ("piece", "pack") and not q.is_integer():
                raise Rule("Whole units required")
            price = p["sell"] if d.kind == "order" else p["buy"]
            if d.kind == "invoice" and item.price is None:
                raise Rule("Missing invoice price")
            if item.price is not None:
                if d.kind == "order" and cents(item.price) != price:
                    raise Rule("Selling price mismatch")
                price = cents(item.price)
            total += int((item.qty * price).quantize(Decimal("1")))
            if d.kind == "order":
                if q > round(p["stock"] - p["reserved"], 3):
                    raise Rule("Insufficient available stock")
                move(c, p, 0, q, d.ref)
            if d.kind == "stock":
                if q < p["reserved"]:
                    raise Rule("Count below reserved quantity")
                move(c, p, q - p["stock"], 0, d.ref)
            if d.kind == "invoice":
                move(c, p, q, 0, d.ref)
        if d.kind == "invoice" and not amount:
            raise Rule("Missing invoice total")
        if amount and amount != total:
            raise Rule("Line total does not match document total")
        amount = total
        if (
            d.kind == "invoice"
            and total > one(c, "select invoice_limit from settings")["invoice_limit"]
            and not approved
        ):
            raise Rule("Invoice exceeds automatic approval limit")
    audit(c, actor, "validated", d.ref, job)
    audit(c, actor, "authorized", role + " / " + d.kind, job)
    rid = run(
        c,
        "insert into records(kind,ref,party,amount,status,items,at) values(:k,:r,:p,:a,:s,:i,:t)",
        k=d.kind,
        r=d.ref,
        p=d.party,
        a=amount,
        s=status,
        i=json.dumps([x.model_dump(mode="json") for x in d.items]),
        t=now(),
    ).lastrowid
    audit(c, actor, "record." + status, d.ref, job)
    return {"id": rid, "status": status, "ref": d.ref, "amount_paise": amount}
