import hashlib, hmac, json, unittest
from unittest.mock import patch
from .test_e2e import seed, app, TestClient, os


class WebhookTest(unittest.TestCase):
    def test_intake(self):
        seed()
        with patch.dict(
            os.environ,
            dict(
                WA_APP_SECRET="secret",
                WA_VERIFY_TOKEN="verify",
                WA_ACCESS_TOKEN="demo",
                WA_GRAPH_VERSION="test",
                WA_PHONE_ID="123",
                WA_SENDERS="",
            ),
        ), TestClient(app) as c:
            msgs = [
                dict(id="wamid1", type="text", text=dict(body="Rice 5 kg\n1 pack Tea")),
                dict(
                    id="wamid2", type="text", text=dict(body="https://example.org/list")
                ),
            ]
            for m in msgs:
                m["from"] = "917000000000"
            b = json.dumps(
                dict(
                    entry=[
                        dict(
                            changes=[
                                dict(
                                    value=dict(
                                        metadata=dict(phone_number_id="123"),
                                        contacts=[],
                                        messages=msgs,
                                    )
                                )
                            ]
                        )
                    ]
                )
            ).encode()
            self.assertEqual(c.post("/webhook/whatsapp", content=b).status_code, 403)
            for _ in range(2):
                c.post(
                    "/webhook/whatsapp",
                    content=b,
                    headers={
                        "x-hub-signature-256": "sha256="
                        + hmac.new(b"secret", b, hashlib.sha256).hexdigest()
                    },
                ).raise_for_status()
            c.post(
                "/api/login",
                json=dict(name="owner", password=os.environ["OWNER_PASSWORD"]),
            ).raise_for_status()
            chat = c.get("/api/inbox").json()[0]
            thread = c.get("/api/inbox/" + str(chat["id"])).json()
            self.assertEqual(sum(bool(x["ref"]) for x in thread), 1)
            self.assertTrue(any("Link received" in x["body"] for x in thread))


if __name__ == "__main__":
    unittest.main()
