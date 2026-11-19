from .business import *
from datetime import date


def metrics(c):
    day = now()[:10]
    products = rows(c, "select * from products where active=1 order by name")
    rec = rows(c, "select * from records order by id desc")
    today = [r for r in rec if r["at"][:10] == day]
    sales = lambda rs: sum(
        r["amount"] for r in rs if r["kind"] == "order" and r["status"] == "fulfilled"
    )
    chart = []
    for i in reversed(range(7)):
        d = (date.fromisoformat(day) - timedelta(days=i)).isoformat()
        chart.append(
            {
                "day": d,
                "sales": sales(
                    r for r in rec if (r.get("fulfilled_at") or "")[:10] == d
                )
                / 100,
            }
        )
    return {
        "sales": chart[-1]["sales"],
        "orders": sum(r["kind"] == "order" for r in today),
        "inventory": sum(round(p["stock"] * p["buy"]) for p in products) / 100,
        "pending": sum(
            r["amount"]
            for r in rec
            if r["kind"] == "payment" and r["status"] == "pending verification"
        )
        / 100,
        "low": [p for p in products if p["stock"] - p["reserved"] <= p["threshold"]],
        "chart": chart,
        "recent": rec[:8],
        "suppliers": rows(
            c,
            "select party,count(*) as invoices,sum(amount)/100.0 as purchases from records where kind='invoice' group by party",
        ),
        "notifications": rows(
            c, "select id,name,status,reason from jobs order by id desc limit 8"
        ),
        "activity": rows(c, "select * from audit order by id desc limit 10"),
    }


def customers(c):
    return rows(
        c,
        """select party,sum(case when kind='credit' then amount when kind='payment' and status='verified' then -amount else 0 end)/100.0 as balance,
    count(*) as entries from records where kind in ('order','credit','payment') group by party""",
    )
