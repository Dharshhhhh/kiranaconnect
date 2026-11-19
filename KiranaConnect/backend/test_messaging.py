import unittest, uuid, time
from .test_e2e import seed, app, ROOT, TestClient, os


class ChatTest(unittest.TestCase):
    def test_customer_order_and_chat(self):
        seed()
        with TestClient(app) as user, TestClient(app) as staff:
            self.assertEqual(user.get("/api/inbox").status_code, 401)
            user.post("/api/customer/start", json={"name": "Meena"}).raise_for_status()
            cmd = {"body": "Order 5 kg Rice", "nonce": str(uuid.uuid4())}
            for _ in range(2):
                user.post("/api/customer/message", json=cmd).raise_for_status()
            staff.post(
                "/api/login",
                json={"name": "owner", "password": os.environ["OWNER_PASSWORD"]},
            ).raise_for_status()
            cid = staff.get("/api/inbox").json()[0]["id"]
            read = staff.get(f"/api/inbox/{cid}").json()
            self.assertEqual(sum(bool(m["ref"]) for m in read), 1)
            self.assertEqual(read[-1]["order_status"], "reserved")
            staff.post(
                f"/api/inbox/{cid}",
                json={"body": "Pickup at the counter", "nonce": str(uuid.uuid4())},
            ).raise_for_status()
            self.assertEqual(
                user.get("/api/customer/thread").json()["messages"][-1]["body"],
                "Pickup at the counter",
            )
            data = (ROOT / "samples/01-order.png").read_bytes()
            for client, url in [
                (staff, f"/api/inbox/{cid}/image"),
                (user, "/api/customer/image"),
            ]:
                client.post(
                    url,
                    files={"file": ("image.png", data, "image/png")},
                    data={"nonce": str(uuid.uuid4())},
                ).raise_for_status()
            for _ in range(70):
                msgs = user.get("/api/customer/thread").json()["messages"]
                if msgs[-1]["job_status"] == "completed":
                    break
                time.sleep(0.1)
            self.assertEqual(msgs[-1]["job_status"], "completed")
            self.assertEqual(
                user.get("/api/customer/photo/" + str(msgs[-2]["id"])).content, data
            )
            self.assertEqual(
                user.get("/api/customer/images/" + str(msgs[-1]["job"])).content, data
            )
            user.post(
                "/api/customer/start", json={"name": "Other customer"}
            ).raise_for_status()
            self.assertEqual(
                user.get("/api/customer/images/" + str(msgs[-1]["job"])).status_code,
                404,
            )
            self.assertEqual(
                user.get("/api/customer/photo/" + str(msgs[-2]["id"])).status_code, 404
            )


if __name__ == "__main__":
    unittest.main()
