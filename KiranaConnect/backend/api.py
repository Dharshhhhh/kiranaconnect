from contextlib import asynccontextmanager
from threading import Thread, Event
import hmac, secrets, time
from fastapi import FastAPI, Depends, HTTPException, Request, Response, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse, PlainTextResponse
from sqlalchemy.exc import IntegrityError
from .assistant import tool, route
from .automation import *
from .summary import metrics, customers


def digest(password, salt):
    return hashlib.scrypt(
        password.encode(), salt=salt.encode(), n=2**14, r=8, p=1
    ).hex()


def bootstrap():
    init()
    with tx() as c:
        for role in ("owner",):
            if one(c, "select name from users where name=:r", r=role):
                continue
            pw = os.getenv(role.upper() + "_PASSWORD", "")
            if len(pw) < 10:
                raise RuntimeError(
                    "Set "
                    + role.upper()
                    + "_PASSWORD (at least 10 characters) before first launch."
                )
            salt = secrets.token_hex(16)
            run(
                c,
                "insert into users values(:r,:r,:hash)",
                r=role,
                hash=salt + "$" + digest(pw, salt),
            )


@asynccontextmanager
async def lifespan(app):
    bootstrap()
    stop = Event()
    thread = Thread(target=worker, args=(stop,), daemon=True)
    thread.start()
    yield
    stop.set()
    thread.join(timeout=50)


app = FastAPI(title="KiranaConnect Business", lifespan=lifespan)


from .limits import RequestLimits

app.add_middleware(RequestLimits)


@app.exception_handler(ValueError)
async def invalid(req, e):
    return JSONResponse({"detail": str(e)[:1500]}, 422)


@app.exception_handler(PermissionError)
async def forbidden(req, e):
    return JSONResponse({"detail": str(e)}, 403)


@app.exception_handler(IntegrityError)
async def conflict(req, e):
    return JSONResponse({"detail": "A record with that key already exists."}, 409)


@app.exception_handler(httpx.HTTPError)
async def upstream(req, e):
    return JSONResponse(
        {"detail": "External service unavailable. Check credentials and retry."}, 502
    )


def token_hash(t):
    return hashlib.sha256(t.encode()).hexdigest()


def current(req: Request):
    with engine.connect() as c:
        u = one(
            c,
            "select u.name,u.role from sessions s join users u on u.name=s.name where s.token=:t and s.expires>:n and u.role='owner'",
            t=token_hash(req.cookies.get("kc", "")),
            n=int(time.time()),
        )
    if not u:
        raise HTTPException(401, "Please sign in")
    return u


class Login(Strict):
    name: str = Field(max_length=64)
    password: str = Field(max_length=256)


@app.post("/api/login")
def login(d: Login, response: Response):
    with tx() as c:
        u = one(c, "select * from users where name=:n", n=d.name)
        if (
            not u
            or u["role"] != "owner"
            or not hmac.compare_digest(
                digest(d.password, u["digest"].split("$")[0]), u["digest"].split("$")[1]
            )
        ):
            raise HTTPException(401, "Invalid login")
        t = secrets.token_urlsafe(32)
        run(c, "delete from sessions where expires<=:n", n=int(time.time()))
        run(
            c,
            "insert into sessions values(:t,:n,:e)",
            t=token_hash(t),
            n=d.name,
            e=int(time.time()) + 28800,
        )
        response.set_cookie(
            "kc",
            t,
            httponly=True,
            samesite="strict",
            secure=os.getenv("HTTPS_ONLY") == "true",
            max_age=28800,
        )
        audit(c, d.name, "session.login", u["role"])
        return {"name": d.name, "role": u["role"]}


@app.post("/api/logout")
def logout(req: Request, response: Response, u=Depends(current)):
    with tx() as c:
        run(c, "delete from sessions where token=:t", t=token_hash(req.cookies["kc"]))
    response.delete_cookie("kc")
    return {"ok": True}


@app.get("/api/me")
def me(u=Depends(current)):
    return u


@app.get("/api/state")
def state(u=Depends(current)):
    with engine.begin() as c:
        return dict(
            dashboard=metrics(c),
            products=rows(c, "select * from products where active=1 order by name"),
            records=rows(c, "select * from records order by id desc"),
            jobs=rows(
                c,
                "select id,name,source,status,reason,payload,at from jobs order by id desc",
            ),
            audit=rows(c, "select * from audit order by id desc limit 500"),
            movements=rows(c, "select * from movements order by id desc limit 500"),
            customers=customers(c),
            settings={
                "invoice_limit": one(c, "select invoice_limit from settings")[
                    "invoice_limit"
                ]
                / 100,
                "vision": os.getenv("VISION_MODE", "fixtures"),
                "chat": os.getenv("CHAT_MODE", "offline"),
                "payments": os.getenv("PAYMENT_PROVIDER", "disabled"),
            },
        )


@app.post("/api/products")
def product(d: Product, u=Depends(current)):
    with tx() as c:
        return {"id": save_product(c, u["role"], u["name"], d)}


@app.put("/api/products/{pid}")
def edit(pid: int, d: Product, u=Depends(current)):
    with tx() as c:
        return {"id": save_product(c, u["role"], u["name"], d, pid)}


@app.delete("/api/products/{pid}")
def archive(pid: int, u=Depends(current)):
    owner(u["role"])
    with tx() as c:
        if not run(
            c,
            "update products set active=0 where id=:i and reserved=0 and active=1",
            i=pid,
        ).rowcount:
            raise Rule("Missing product or active reservations")
        audit(c, u["name"], "catalog.archived", pid)
    return {"ok": True}


@app.post("/api/records")
def record(d: Proposal, u=Depends(current)):
    with tx() as c:
        return execute(c, d, u["role"], u["name"])


@app.post("/api/records/{rid}/advance")
def advance(rid: int, u=Depends(current)):
    with tx() as c:
        r = one(c, "select * from records where id=:i", i=rid)
        if not r:
            raise Rule("Missing record")
        if r["kind"] == "order" and r["status"] == "reserved":
            from .payment_flow import paid

            if one(c, "select id from messages where record=:i", i=rid) and not paid(
                c, rid
            ):
                raise Rule("Awaiting a verified payment for this chat order.")
            for item in json.loads(r["items"]):
                p = one(c, "select * from products where name=:n", n=item["product"])
                q = float(item["qty"])
                if not p or p["reserved"] < q or p["stock"] < q:
                    raise Rule("Reservation mismatch")
                move(c, p, -q, -q, r["ref"])
            run(
                c,
                "update records set status='fulfilled',fulfilled_at=:t where id=:i",
                t=now(),
                i=rid,
            )
        elif r["kind"] == "payment" and r["status"] == "pending verification":
            from .payment_flow import apply_result

            decision = provider().status(r["ref"], r["party"], r["amount"])
            if decision == "pending verification":
                audit(c, u["name"], "reconciliation.pending", r["ref"])
                return {"status": decision}
            run(c, "update records set status=:s where id=:i", s=decision, i=rid)
            apply_result(c, rid)
        else:
            raise Rule("No permitted transition")
        audit(c, u["name"], "record.updated", r["ref"])
        return {
            "status": one(c, "select status from records where id=:i", i=rid)["status"]
        }


@app.post("/api/uploads")
def upload(file: UploadFile = File(...), u=Depends(current)):
    return {
        "id": enqueue(
            file.file.read(MAX + 1),
            file.filename or "image",
            "upload",
            u["name"],
            u["role"],
        )
    }


@app.get("/api/jobs/{jid}/image")
def evidence(jid: int, u=Depends(current)):
    with engine.connect() as c:
        j = one(c, "select hash from jobs where id=:i", i=jid)
    if not j:
        raise HTTPException(404)
    path = DATA / j["hash"]
    with Image.open(path) as im:
        mime = Image.MIME[im.format]
    return FileResponse(
        path, media_type=mime, headers={"X-Content-Type-Options": "nosniff"}
    )


@app.post("/api/jobs/{jid}/review")
def review(jid: int, d: dict, u=Depends(current)):
    owner(u["role"])
    with tx() as c:
        j = one(c, "select * from jobs where id=:i and status='review'", i=jid)
        if not j:
            raise Rule("Job is no longer in review")
        audit(
            c,
            u["name"],
            "owner.review",
            json.dumps({"original": json.loads(j["payload"]), "decision": d})[:1500],
            jid,
        )
        if d.get("reject") is True:
            run(
                c,
                "update jobs set status='rejected',reason='Rejected by owner' where id=:i",
                i=jid,
            )
            return {"status": "rejected"}
        return finish_job(c, j, d, u["name"], u["role"], True)


class Policy(Strict):
    invoice_limit: Decimal = Field(ge=0, le=100000000, decimal_places=2)


@app.put("/api/settings")
def settings(d: Policy, u=Depends(current)):
    owner(u["role"])
    with tx() as c:
        run(c, "update settings set invoice_limit=:v", v=cents(d.invoice_limit))
        audit(c, u["name"], "policy.updated", d.invoice_limit)
    return {"ok": True}


class Message(Strict):
    message: str = Field(min_length=1, max_length=1000)


@app.post("/api/chat")
def chat(d: Message, u=Depends(current)):
    name, args = route(d.message)
    with tx() as c:
        result = tool(c, name, args, u)
        audit(c, u["name"], "chat.tool", name)
        return result


class Confirmation(Strict):
    tool: Literal["order", "purchase"]
    args: dict
    request_id: str = Field(pattern=r"^[a-f0-9-]{36}$")


@app.post("/api/chat/confirm")
def confirm(d: Confirmation, u=Depends(current)):
    with tx() as c:
        key = u["name"] + ":" + d.request_id
        prior = one(c, "select result from confirmations where key=:k", k=key)
        if prior:
            return json.loads(prior["result"])
        result = tool(c, d.tool, d.args, u, True)
        run(c, "insert into confirmations values(:k,:r)", k=key, r=json.dumps(result))
        return result


def wa_env():
    keys = [
        "WA_APP_SECRET",
        "WA_VERIFY_TOKEN",
        "WA_ACCESS_TOKEN",
        "WA_PHONE_ID",
        "WA_GRAPH_VERSION",
    ]
    if not all(os.getenv(k) for k in keys):
        raise HTTPException(503, "WhatsApp is disabled")


@app.get("/webhook/whatsapp")
def verify(req: Request):
    wa_env()
    q = req.query_params
    if q.get("hub.mode") != "subscribe" or not hmac.compare_digest(
        q.get("hub.verify_token", ""), os.environ["WA_VERIFY_TOKEN"]
    ):
        raise HTTPException(403)
    return PlainTextResponse(q.get("hub.challenge", ""))


@app.post("/webhook/whatsapp")
async def webhook(req: Request):
    wa_env()
    body = await req.body()
    signature = (
        "sha256="
        + hmac.new(
            os.environ["WA_APP_SECRET"].encode(), body, hashlib.sha256
        ).hexdigest()
    )
    if not hmac.compare_digest(signature, req.headers.get("x-hub-signature-256", "")):
        raise HTTPException(403)
    headers = {"Authorization": "Bearer " + os.environ["WA_ACCESS_TOKEN"]}
    async with httpx.AsyncClient(timeout=25, trust_env=False) as client:
        for entry in json.loads(body).get("entry", []):
            for change in entry.get("changes", []):
                v = change["value"]
                if (
                    v.get("metadata", {}).get("phone_number_id")
                    != os.environ["WA_PHONE_ID"]
                ):
                    continue
                for msg in v.get("messages", []):
                    sender = msg["from"]
                    allowed = os.getenv("WA_SENDERS", "").strip()
                    if allowed and sender not in {
                        x.strip() for x in allowed.split(",")
                    }:
                        continue
                    name = (
                        next(
                            (
                                v.get("profile", {}).get("name")
                                for v in v.get("contacts", [])
                                if v.get("wa_id") == sender
                            ),
                            None,
                        )
                        or sender
                    )
                    if msg["type"] not in ("text", "image"):
                        continue
                    with tx() as c:
                        person = whatsapp_person(c, sender, name)
                        if msg["type"] == "text":
                            incoming(c, person, msg["text"]["body"], msg["id"])
                            continue
                    mid = msg["image"]["id"]
                    if not mid.isdigit():
                        raise Rule("Invalid media ID")
                    meta = await client.get(
                        f"https://graph.facebook.com/{os.environ['WA_GRAPH_VERSION']}/{mid}",
                        headers=headers,
                    )
                    meta.raise_for_status()
                    url = httpx.URL(meta.json()["url"])
                    if url.scheme != "https" or not (
                        url.host == "lookaside.fbsbx.com"
                        or url.host.endswith(".fbcdn.net")
                    ):
                        raise Rule("Untrusted media host")
                    async with client.stream("GET", url, headers=headers) as response:
                        response.raise_for_status()
                        data = bytearray()
                        async for chunk in response.aiter_bytes():
                            data.extend(chunk)
                            if len(data) > MAX:
                                raise Rule("Media too large")
                    with tx() as c:
                        incoming(
                            c,
                            person,
                            msg["image"].get("caption", "Screenshot"),
                            msg["id"],
                            bytes(data),
                            mid + ".image",
                        )
    return {"received": True}


from .messaging import register_chat, whatsapp_person, incoming

register_chat(app, current)

# Serve the prebuilt frontend from the authenticated API origin.
from fastapi.staticfiles import StaticFiles

if (ROOT / "frontend/dist/index.html").exists():
    app.mount(
        "/", StaticFiles(directory=ROOT / "frontend/dist", html=True), name="workspace"
    )
