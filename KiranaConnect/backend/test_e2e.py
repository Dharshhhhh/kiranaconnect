"""Offline integration test. Uses a fresh, private database on every run."""

import os, tempfile, time, unittest, uuid
from pathlib import Path

tmp = tempfile.TemporaryDirectory()
os.environ.update(
    DATA_DIR=tmp.name,
    OWNER_PASSWORD="local-test-owner",
    STAFF_PASSWORD="local-test-staff",
    VISION_MODE="fixtures",
    CHAT_MODE="offline",
    PAYMENT_PROVIDER="mock",
)
from fastapi.testclient import TestClient
from .seed import seed
from .api import app
from .store import ROOT


class StoreFlow(unittest.TestCase):
    def test_counter(self):
        seed()
        with TestClient(app) as client:
            self.assertEqual(client.get("/api/state").status_code, 401)

            def post(path, d):
                r = client.post("/api/" + path, json=d)
                self.assertEqual(r.status_code, 200, r.text)
                return r.json()

            def state():
                return client.get("/api/state").json()

            def wait(jid):
                for _ in range(100):
                    j = next(j for j in state()["jobs"] if j["id"] == jid)
                    if j["status"] != "queued":
                        return j
                    time.sleep(0.08)
                self.fail("Worker timeout")

            post("login", dict(name="owner", password=os.environ["OWNER_PASSWORD"]))
            expected = [
                "completed",
                "completed",
                "completed",
                "completed",
                "completed",
                "duplicate",
                "review",
                "completed",
                "duplicate",
            ]
            for f, st in zip(
                sorted((ROOT / "samples").glob("*.png")), expected, strict=True
            ):
                r = client.post(
                    "/api/uploads",
                    files={"file": (f.name, f.read_bytes(), "image/png")},
                )
                self.assertEqual(r.status_code, 200, r.text)
                j = wait(r.json()["id"])
                self.assertEqual(j["status"], st, j)
                if st == "review":
                    suspicious = j
            self.assertEqual(
                post("jobs/" + str(suspicious["id"]) + "/review", {"reject": True})[
                    "status"
                ],
                "rejected",
            )
            data = state()
            pay = {
                r["ref"]: r["status"] for r in data["records"] if r["kind"] == "payment"
            }
            self.assertEqual(
                pay, {"UPI50611001": "verified", "UPI50611999": "pending verification"}
            )
            rice = next(p for p in data["products"] if p["name"] == "Rice")
            self.assertEqual((rice["stock"], rice["reserved"]), (65, 5))
            self.assertEqual(data["customers"][0]["balance"], 100)
            order = next(r for r in data["records"] if r["kind"] == "order")
            post(f"records/{order['id']}/advance", {})
            self.assertEqual(state()["dashboard"]["sales"], 250)
            for q in [
                "today sales",
                "low-stock products",
                "pending invoices",
                "inventory value",
                "payment history for Meena",
                "today activity",
            ]:
                self.assertTrue(post("chat", {"message": q})["answer"])
            for q in [
                "create an order for 5 kg rice",
                "create a purchase order for low-stock items",
            ]:
                a = post("chat", {"message": q})
                cmd = dict(tool=a["tool"], args=a["args"], request_id=str(uuid.uuid4()))
                self.assertEqual(post("chat/confirm", cmd), post("chat/confirm", cmd))
            invoice = dict(
                kind="invoice",
                party="Kaveri",
                ref="BIG-01",
                amount=6000,
                items=[dict(product="Rice", unit="kg", qty=150, price=40)],
            )
            before = state()["products"]
            self.assertEqual(client.post("/api/records", json=invoice).status_code, 422)
            self.assertEqual(before, state()["products"])
            post("logout", {})
            self.assertEqual(
                client.post(
                    "/api/login",
                    json=dict(name="staff", password=os.environ["STAFF_PASSWORD"]),
                ).status_code,
                401,
            )
            post("login", dict(name="owner", password=os.environ["OWNER_PASSWORD"]))
            self.assertEqual(
                client.post(
                    "/api/uploads", files={"file": ("bad.png", b"bad", "image/png")}
                ).status_code,
                422,
            )
            # Copy an existing image into the monitored folder. Hash dedup still applies.
            f = ROOT / "samples/01-order.png"
            (Path(tmp.name) / "inbox" / f.name).write_bytes(f.read_bytes())
            for _ in range(60):
                if any(
                    j["source"] == "folder" and j["status"] == "duplicate"
                    for j in state()["jobs"]
                ):
                    break
                time.sleep(0.1)
            else:
                self.fail("Folder monitor timeout")


if __name__ == "__main__":
    unittest.main()
