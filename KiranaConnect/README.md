# KiranaConnect Business

**KiranaConnect – From Screenshot to Action, Powered by AI.**

An incoming image enters a persistent queue. A worker proposes one business document, the business layer validates it, and SQLite commits the document, stock or ledger change, and audit entries together. The dashboard polls the API every three seconds. The packaged frontend runs from FastAPI on the same origin.

## Windows 11 quick start

Install Python 3.12 with the Windows Python launcher. Extract the ZIP, open PowerShell in the directory containing this README, and run:

~~~powershell
powershell -ExecutionPolicy Bypass -File .\Start-Windows.ps1
~~~

Open **http://127.0.0.1:8000**. On first launch the script generates an owner password in the local `.env` file. Sign in as **owner** using OWNER_PASSWORD. The script seeds four inventory products. Sales start at zero until you fulfil an order. The initial dependency install needs internet access. For subsequent offline starts:

~~~powershell
.\.venv\Scripts\python.exe -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
~~~

### Manual setup

~~~powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
# Fill OWNER_PASSWORD with a value of 10+ characters before seeding.
.\.venv\Scripts\python.exe -m backend.seed
.\.venv\Scripts\python.exe -m uvicorn backend.api:app --port 8000
~~~

Run one server process per data directory. The durable queue and folder consumer are designed for a single worker. Passwords are hashed at initial account creation. Editing a bootstrap password later does not rotate an existing account. Keep .env, data/, and local inbox permissions private. Do not commit or share them.

## Use your Sarvam API key

In the root `.env`, change the following values, then restart FastAPI:

~~~dotenv
SARVAM_API_KEY=your_key_here
SARVAM_MODEL=gemma4
VISION_MODE=sarvam
CHAT_MODE=sarvam
~~~

Use an account with access to the selected multimodal, tool-capable model. The backend calls Sarvam's v2 chat completions API. The first image request classifies the document, the second extracts fields. The assistant sends function declarations and processes one proposed call. Responses shown to the shopkeeper are formatted from database results. Images or questions leave the laptop when their respective live modes are selected. A provider failure sends a screenshot to review or returns a chat error. For an immediate stage fallback, restore fixture and offline modes and restart. To use Gemini instead, set both modes to `gemini`, fill `GEMINI_API_KEY`, and choose an available `GEMINI_MODEL`.

Provider reference: https://docs.sarvam.ai/api/token-factory/chat-completions and https://ai.google.dev/gemini-api/docs/function-calling

| Feature | Works locally after installation | Credential or dependency |
|---|---|---|
| Dashboard, catalog, forms, reports, audit, sessions, approval, SQLite | Yes | Store login |
| Screenshot fixtures | Yes | VISION_MODE=fixtures recognizes bundled image bytes by hash. This replays known extractions. Unknown images enter review. |
| Arbitrary screenshot recognition | Online | Sarvam multimodal model or Gemini Vision |
| Eight assistant examples | Yes | CHAT_MODE=offline uses a small intent parser |
| Flexible natural-language tool routing | Online | Sarvam or Gemini |
| Automatic local arrivals | Yes | Copy a completed image into data/inbox |
| WhatsApp arrivals | Online | Signed webhook, HTTPS, Meta credentials |
| Mock reconciliation | Yes | PAYMENT_PROVIDER=mock compares a read-only application fixture |
| Real bank/payment verification | Integration point | Supply a merchant provider adapter. No live bank adapter ships. Set PAYMENT_PROVIDER=disabled to leave payments pending. |

## Two-minute judge demo

1. Sign in as owner. Inventory starts with 80 kg of Rice at ₹40 buying cost and ₹50 selling price.
2. Upload `samples/01-order.png`. After the queue completes, Inventory shows 5 kg reserved and 75 kg available. Orders → **Fulfil order** reduces on-hand stock to 75 kg and records ₹250 in today's sales.
3. Upload `03-payment.png`. Its reference, amount and customer match the independent seeded merchant settlement, so Payments shows **verified**. Upload `08-unmatched.png` to show **pending verification**. Reconcile checks the provider again.
4. Upload `06-byte-duplicate.png`, then `09-reference-repeat.png`. Both are duplicates. The second has different image bytes and the same business reference.
5. Upload `07-suspicious.png`. The queue displays the reason. An owner can compare the image with the proposal, correct fields and approve, or reject it. Validation runs again. A conflicting invoice total will still fail. Payment verification is always recomputed by the provider.
6. Ask the assistant “payment history for Meena”, then “create an order for 5 kg rice”. The first answer reads real records. The second requires confirmation to reserve stock.
7. Demonstrate automatic ingestion with PowerShell:

~~~powershell
Copy-Item .\samples\02-invoice.png .\data\inbox\
~~~

A running worker moves consumed files to data/processed or data/rejected. Uploads use the signed-in role. Customer arrivals use limited intake permissions. For large slow copies, write a temporary extension and rename to PNG/JPEG/WebP when finished.

### Sample outcomes on a clean store

| File | Owner-upload result |
|---|---|
| 01-order | Reserve 5 kg Rice |
| 02-invoice | Receive 20 kg Rice at ₹40, invoice total ₹800 |
| 03-payment | Verify ₹250 against the local mock settlement |
| 04-stock | Set absolute Rice count to 65 kg, preserving reservations |
| 05-credit | Debit Meena’s account ₹350 |
| 06-byte-duplicate | Same bytes as 03 |
| 07-suspicious | Review injected instructions and ₹900 versus ₹400 arithmetic |
| 08-unmatched | Record ₹700 pending verification |
| 09-reference-repeat | Different image with the same receipt reference as 03 |

The fixture manifest is trusted application code/data. Uploaded manifests and image metadata are never used as commands. To regenerate the synthetic images and fixture mapping together: `python -c "from backend.seed import fixtures; fixtures()"`. Seed is repeatable. The fixture generator replaces the bundled samples.

## Permissions, figures and review

The owner can view reports, reserve and fulfil orders, submit documents and request reconciliation. Owner-only operations include catalog edits, absolute stock counts, new customer debt, purchase orders, approval-limit changes and review decisions. Invoices within the configured limit can be received automatically. Above-limit screenshot invoices enter owner review. Purchase orders are internal requests for procurement and do not alter stock until a supplier invoice is received.

Money in SQLite uses integer paise. UI amounts use INR. Orders use catalog selling prices. Sales use fulfilment date in India. Inventory value is on-hand stock at catalog buying cost. Pending payments count unmatched receipt amounts. Customer balance tracks explicit credit debits less verified payments. A negative balance represents a customer credit. Matching uses case-insensitive exact catalog names and matching units. An invoice number is unique store-wide per document type in this prototype. Reused numbers across suppliers are conservatively blocked.

The application treats every model field as a proposal and ignores image instructions. Schema constraints, known tools, caller role, stock availability, invoice totals, uniqueness and transaction boundaries restrict mutations. Model confidence is a review signal and is not independent evidence of document authenticity. Images are size-limited, decoded and stored under SHA-256 names outside the public frontend. Rendered strings use React escaping. Only an authenticated store user can view evidence.

### WhatsApp Business Cloud API

Expose the **backend** through a public HTTPS origin suitable for your test number. Keep the local demo bound to loopback otherwise. Set WA_APP_SECRET, WA_VERIFY_TOKEN (choose a secret you also enter in Meta), WA_ACCESS_TOKEN, WA_PHONE_ID, WA_GRAPH_VERSION (your supported version, e.g. vXX.X), and WA_SENDERS (comma-separated optional sender IDs including country code, digits only; leave empty for all senders). Restart. In Meta configure the callback path `/webhook/whatsapp`, verify the token and subscribe to messages for the registered number. Send an image from an approved sender; inspect Screenshot Center and audit. The receiver verifies the raw-body HMAC, expected receiving number, sender allowlist, media type and downloaded bytes. Text, grocery lists, links and image captions appear in Shop inbox. Grocery lists can reserve inventory. Links are recorded for review. Outgoing owner replies currently reach the simulator only. Set HTTPS_ONLY=true when the frontend is served over HTTPS.

### Payment provider extension

`backend/business.py` defines the Provider protocol and selection function. Implement matches(ref, party, amount_paise) against an authenticated, independently obtained merchant settlement. Bind the merchant account, currency, payer and settled status. Return false for missing or mismatched records. Keep credentials and records outside image extraction. If deploying with real customers, turn off the development mock.

## Development and tests

The ZIP includes the frontend production build. To modify React, install Node.js 22 LTS, start FastAPI on port 8000, then use a second PowerShell window:

~~~powershell
cd frontend
npm ci
npm run dev
# Open the Vite URL printed in this terminal. /api proxies to FastAPI.
npm run build
~~~

Restart FastAPI after rebuilding to use the bundled UI. Interactive REST docs are at http://127.0.0.1:8000/docs. Authenticated requests use the session cookie from /api/login. API operations and role checks live in backend/api.py. SQLAlchemy Core manages the SQLite unit of work in backend/store.py.

From the project root:

~~~powershell
.\.venv\Scripts\python.exe -m backend.test_e2e
~~~

The test creates an isolated temporary store. It logs in, submits all nine images through multipart HTTP, waits for the worker, checks database-derived totals, fulfils an order, invokes all eight assistant tools, retries a confirmed mutation, checks invoice rollback and staff restrictions, rejects an invalid file and checks folder ingestion. It does not require external credentials. For a browser pass, follow the judge demo, verify that only the owner can sign in. Live Sarvam, Gemini, WhatsApp and a future bank adapter require separate credentialed acceptance tests. This release targets a single-store local hackathon demo.

## WhatsApp simulation

Open the owner dashboard and select **Kirana AI** inside Shop inbox. Open **Open customer simulator** in a second tab. It opens a demo chat as Meena without a form or account. Send "Rice 5 kg, Tea 1 pack", or attach samples/01-order.png. Customer messages appear automatically in the owner inbox. The offline parser accepts both quantity-first and product-first lists. With CHAT_MODE=sarvam or gemini, a worker extracts proposed line items from free-form text. VISION_MODE selects the screenshot extractor. Received links are preserved for owner review; arbitrary linked pages are not downloaded. Screenshots of receipts still require provider reconciliation. Attachments both from the simulator and the Meta webhook enter the same pipeline.

Run python -m backend.test_whatsapp and python -m backend.test_messaging to test inbound webhook delivery, replay protection, ordering, attachments and conversation isolation.

To upgrade your existing Windows installation, stop the server, extract this release into a separate folder, and copy its backend and frontend directories into your existing project, allowing file replacement. Keep the existing .env and data directory. Restart with Start-Windows.ps1. New conversation tables are created on startup.

## Payment holds and rejected-receipt demo

For orders placed in the customer chat, fulfilment requires a linked verified receipt. A receipt sent in that same chat automatically links when exactly one open unpaid order matches its amount. If multiple orders match, the customer can send "Link RECEIPT-REF to ORDER-REF" in the shop conversation. The backend checks both belong to that conversation. A pending receipt holds fulfilment and prompts the customer to recheck their details. A provider-confirmed fraudulent receipt cancels the linked order, releases its reservation and posts a reorder message to the customer's KiranaConnect Business conversation. Reordering creates a new reference. An owner-uploaded receipt without a chat association cannot automatically cancel a customer order. Previously recorded payments are not retroactively assigned to orders. Existing completed orders are preserved.

To demo in connected simulator mode, use Meena's shop chat, send "Order 3 kg Rice" at the seeded selling price of ₹50/kg, then attach samples/payment-demo/10-rejected.png. Use the bundled fixture and mock provider settings. The independent mock ledger explicitly rejects DEMO-REJECT-150 for ₹150. In Orders check cancelled, in Inventory check released stock, and in the same customer chat read the notification. The ₹700 sample 08-unmatched.png remains pending. This release delivers notifications in the simulator; outbound messages to an actual WhatsApp number need a Meta sender integration.

For an existing installation, stop the store and copy the updated backend, frontend and samples directories into its project folder. Leave data, .env and .venv in place. Restart Start-Windows.ps1. The simulator can continue using port 8000 without reinstalling it. Automated checks: python -m backend.test_payment_flow.
