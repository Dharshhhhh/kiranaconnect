from .test_e2e import seed, app, TestClient, os, ROOT
import uuid, time, unittest


class PaymentTest(unittest.TestCase):
    def test_payments(self):
        seed()
        with TestClient(app) as client:
            client.post(
                "/api/login",
                json=dict(name="owner", password=os.environ["OWNER_PASSWORD"]),
            ).raise_for_status()
            client.post(
                "/api/customer/start", json=dict(name="Meena")
            ).raise_for_status()

            def send(body):
                client.post(
                    "/api/customer/message",
                    json=dict(body=body, nonce=str(uuid.uuid4())),
                ).raise_for_status()

            def state():
                return client.get("/api/state").json()

            def msgs():
                return client.get("/api/customer/thread").json()["messages"]

            def upload(name):
                client.post(
                    "/api/customer/image",
                    data=dict(nonce=str(uuid.uuid4())),
                    files={
                        "file": (
                            "receipt.png",
                            (ROOT / "samples" / name).read_bytes(),
                            "image/png",
                        )
                    },
                ).raise_for_status()
                for _ in range(80):
                    if state()["jobs"][0]["status"] != "queued":
                        return
                    time.sleep(0.08)
                self.fail("worker timeout")

            def latest():
                return next(r for r in state()["records"] if r["kind"] == "order")

            send("Rice 3 kg")
            r = latest()
            self.assertEqual(
                client.post(f"/api/records/{r['id']}/advance").status_code, 422
            )
            upload("payment-demo/10-rejected.png")
            self.assertEqual(latest()["status"], "cancelled")
            self.assertIn("place a new order", msgs()[-1]["body"])
            p = next(p for p in state()["products"] if p["name"] == "Rice")
            self.assertEqual((p["stock"], p["reserved"]), (80, 0))
            upload("payment-demo/10-rejected.png")
            self.assertEqual(state()["jobs"][0]["status"], "duplicate")
            send("Rice 14 kg")
            upload("08-unmatched.png")
            self.assertEqual(latest()["status"], "payment hold")
            self.assertIn("recheck", msgs()[-1]["body"])
            send("Rice 5 kg")
            upload("03-payment.png")
            r = latest()
            client.post(f"/api/records/{r['id']}/advance").raise_for_status()
            self.assertEqual(latest()["status"], "fulfilled")


if __name__ == "__main__":
    unittest.main()
