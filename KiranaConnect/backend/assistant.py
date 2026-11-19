from uuid import uuid4
from .automation import gemini
from .summary import *

TOOLS = {
    "sales": "Sales from orders fulfilled today",
    "low_stock": "Products at or below available stock threshold",
    "pending_invoices": "Supplier invoices awaiting review",
    "inventory_value": "Inventory value at cost",
    "order": "Reserve product stock for a customer",
    "history": "Customer payment history",
    "purchase": "Create one purchase order for low-stock items",
    "activity": "Summary of today in store time",
}
PARAMS = {
    "order": {
        "product": "STRING",
        "qty": "NUMBER",
        "unit": "STRING",
        "party": "STRING",
    },
    "history": {"party": "STRING"},
}


def route(message):
    if os.getenv("CHAT_MODE") == "sarvam":
        from .sarvam import completion

        functions = [
            {
                "type": "function",
                "function": {
                    "name": n,
                    "description": description,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            k: {"type": v.lower()} for k, v in PARAMS.get(n, {}).items()
                        },
                        "required": list(PARAMS.get(n, {})),
                    },
                },
            }
            for n, description in TOOLS.items()
        ]
        result = completion(
            [
                {
                    "role": "system",
                    "content": "Choose one tool only for the explicit request. Default customer is Walk-in. Never invent figures.",
                },
                {"role": "user", "content": message},
            ],
            tools=functions,
        )
        calls = result.get("tool_calls", [])
        if len(calls) != 1:
            raise Rule("Ask for one supported store operation.")
        f = calls[0]["function"]
        return f["name"], json.loads(f["arguments"])
    if os.getenv("CHAT_MODE", "offline") == "gemini":
        decl = []
        for name, desc in TOOLS.items():
            fields = PARAMS.get(name, {})
            decl.append(
                {
                    "name": name,
                    "description": desc,
                    **(
                        {
                            "parameters": {
                                "type": "OBJECT",
                                "properties": {
                                    k: {"type": v} for k, v in fields.items()
                                },
                                "required": list(fields),
                            }
                        }
                        if fields
                        else {}
                    ),
                }
            )
        parts = gemini(
            {
                "contents": [{"parts": [{"text": message}]}],
                "systemInstruction": {
                    "parts": [
                        {
                            "text": "Select one tool for the explicit user request. Never invent data. For an order with no customer use Walk-in."
                        }
                    ]
                },
                "tools": [{"functionDeclarations": decl}],
            }
        )
        calls = [p["functionCall"] for p in parts if "functionCall" in p]
        if len(calls) != 1:
            raise Rule("Ask for one supported store operation at a time.")
        return calls[0]["name"], calls[0].get("args", {})
    s = message.strip().lower().rstrip("?.")
    if "purchase order" in s:
        return "purchase", {}
    if "order" in s:
        m = re.search(
            r"(\d+(?:\.\d+)?)\s*(kg|piece|litre|pack)s?\s+(?:of\s+)?(.+?)(?:\s+for\s+(.+))?$",
            s,
        )
        if m:
            return "order", dict(
                qty=m[1], unit=m[2], product=m[3], party=m[4] or "Walk-in"
            )
    if "payment" in s and "history" in s:
        party = re.search(
            r"(?:history (?:for|of) |^(.+?)(?:\x27s)? payment history$)", s
        )
        name = (s[party.end() :] or party[1]) if party else ""
        if name:
            return "history", {"party": name}
    for name, word in [
        ("sales", "sales"),
        ("low_stock", "low"),
        ("inventory_value", "value"),
        ("pending_invoices", "invoice"),
        ("activity", "activity"),
        ("activity", "summary"),
    ]:
        if word in s:
            return name, {}
    raise Rule("Try “create an order for 5 kg rice” or “payment history for Meena”.")


def tool(c, name, args, user, confirmed=False):
    if name not in TOOLS or set(args) != set(PARAMS.get(name, {})):
        raise Rule("Invalid tool arguments")
    m = metrics(c)
    if name in ("purchase", "order"):
        if name == "purchase":
            owner(user["role"])
        if not confirmed:
            return {
                "confirm": True,
                "tool": name,
                "args": args,
                "answer": (
                    "Confirm stock reservation"
                    if name == "order"
                    else "Confirm purchase order for low-stock products"
                ),
            }
        if name == "purchase":
            items = [
                dict(
                    product=p["name"],
                    unit=p["unit"],
                    qty=round(
                        max(1, 2 * p["threshold"] - (p["stock"] - p["reserved"])), 3
                    ),
                )
                for p in m["low"]
            ]
            if not items:
                return {"answer": "No low-stock products."}
            party = "Unassigned supplier"
        else:
            party = args["party"]
            items = [{k: v for k, v in args.items() if k != "party"}]
        result = execute(
            c,
            dict(kind=name, ref="KC-" + uuid4().hex[:12], party=party, items=items),
            user["role"],
            user["name"],
        )
        return {
            "answer": f"{result['ref']} · {result['status']} · ₹{result['amount_paise']/100:,.2f}"
        }
    if name == "sales":
        answer = (
            f"Today’s fulfilled sales: ₹{m['sales']:,.2f}."
            if any(x["sales"] for x in m["chart"][-1:])
            else "No fulfilled sales today."
        )
    if name == "inventory_value":
        answer = (
            f"Inventory at buying cost: ₹{m['inventory']:,.2f}."
            if one(c, "select id from products where active=1")
            else "No inventory data."
        )
    if name == "low_stock":
        answer = "\n".join(
            f"{p['name']}: {p['stock']-p['reserved']:g} {p['unit']} available"
            for p in m["low"]
        )
    if name == "pending_invoices":
        answer = "\n".join(
            f"#{j['id']} {j['name']} — {j['reason']}"
            for j in rows(c, "select * from jobs where status='review'")
            if json.loads(j["payload"]).get("kind") == "invoice"
        )
    if name == "history":
        answer = "\n".join(
            f"{r['at'][:10]} · {r['ref']} · ₹{r['amount']/100:g} · {r['status']}"
            for r in rows(
                c,
                "select * from records where kind='payment' and party=:p order by id desc",
                p=args["party"],
            )
        )
    if name == "activity":
        n = one(
            c, "select count(*) n from jobs where substr(at,1,10)=:d", d=now()[:10]
        )["n"]
        answer = f"Today: {m['orders']} orders created, ₹{m['sales']:g} fulfilled sales, {n} screenshots received."
    return {"answer": answer or "No matching data."}
