"""Apply an independently reconciled payment to one order in its originating chat."""

from .business import move, Rule
from .store import one, rows, run, audit, now
import json


def notify(c, chat, text):
    run(
        c,
        "insert into messages(chat,side,body,at) values(:chat,'shop',:msg,:at)",
        chat=chat,
        msg=text,
        at=now(),
    )


def paid(c, oid):
    return one(
        c,
        "select p.id from receipt_links l join records p on p.id=l.payment where l.order_id=:i and p.status='verified'",
        i=oid,
    )


def apply_result(c, pid):
    details = one(
        c,
        """select o.*,p.ref as receipt,p.status as decision,l.chat from receipt_links l
    join records o on o.id=l.order_id join records p on p.id=l.payment where p.id=:p""",
        p=pid,
    )
    if not details:
        return
    o = details
    if o["status"] not in ("reserved", "payment hold"):
        return
    if o["decision"] != "verified" and paid(c, o["id"]):
        return
    if o["decision"] == "verified":
        status = "reserved"
        message = (
            f"Payment verified for order {o['ref']}. Your order can now be fulfilled."
        )
    elif o["decision"] == "rejected":
        for item in json.loads(o["items"]):
            p = one(c, "select * from products where name=:name", name=item["product"])
            q = float(item["qty"])
            if not p or p["reserved"] < q:
                raise Rule("Reservation mismatch. Owner review required.")
            move(c, p, 0, -q, "Payment rejected: " + o["ref"])
        status = "cancelled"
        message = f"Order {o['ref']} was cancelled because the payment provider rejected receipt {o['receipt']}. Please recheck the amount and UPI reference, then place a new order from the beginning."
    else:
        status = "payment hold"
        message = f"Order {o['ref']} is on hold. Please recheck the amount and UPI reference and send the correct payment details. Your items have not been dispatched."
    run(c, "update records set status=:s where id=:i", s=status, i=o["id"])
    notify(c, o["chat"], message)
    audit(c, "reconciliation", "order." + status, message)


def bind(c, chat, p, o):
    if p["amount"] != o["amount"]:
        raise Rule("The receipt amount must match the order total.")
    if o["status"] not in ("reserved", "payment hold") or paid(c, o["id"]):
        raise Rule("This order is already paid or closed.")
    if one(c, "select payment from receipt_links where payment=:p", p=p["id"]):
        raise Rule("This receipt already has an order.")
    run(
        c,
        "insert into receipt_links values(:p,:o,:chat)",
        p=p["id"],
        o=o["id"],
        chat=chat,
    )
    apply_result(c, p["id"])


def received(c, chat, pid):
    run(c, "insert into receipt_chats values(:p,:ch)", p=pid, ch=chat)
    p = one(c, "select * from records where id=:i", i=pid)
    orders = rows(
        c,
        """select distinct o.* from records o join messages m on m.record=o.id
    where m.chat=:ch and o.kind='order' and o.amount=:a and o.status in ('reserved','payment hold')
    and not exists(select 1 from receipt_links l join records r on r.id=l.payment where l.order_id=o.id and r.status='verified')""",
        ch=chat,
        a=p["amount"],
    )
    if len(orders) == 1:
        bind(c, chat, p, orders[0])
    else:
        notify(
            c,
            chat,
            f"Receipt {p['ref']}: {p['status']}. Please recheck the payment details. To select an unpaid order with the same amount, send: Link {p['ref']} to YOUR-ORDER-REFERENCE.",
        )


def explicit_link(c, chat, pref, oref):
    p = one(
        c,
        "select p.* from records p join receipt_chats a on a.payment=p.id where a.chat=:ch and p.ref=:ref",
        ch=chat,
        ref=pref,
    )
    o = one(
        c,
        "select o.* from records o join messages m on m.record=o.id where m.chat=:ch and o.kind='order' and o.ref=:ref",
        ch=chat,
        ref=oref,
    )
    if not p or not o:
        raise Rule("Check the receipt and order references in this conversation.")
    bind(c, chat, p, o)
