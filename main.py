import asyncio, base64, hmac, json, re, secrets, time, uuid as uuidlib
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import jwt
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from . import config as C, xray
from .db import db, init, is_active

GB = 1024 ** 3
STATIC = Path(__file__).parent / "static"
CLIENT_UA = re.compile(r"v2ray|hiddify|streisand|sing-?box|clash|happ|nekobox|nekoray|shadowrocket|v2box|foxray|karing|husi", re.I)
_applied = None

def active_clients():
    with db() as c:
        return [u for u in c.execute("SELECT * FROM users") if is_active(u)]

async def sync(force=False):
    """Restart Xray only when the set of active users changed."""
    global _applied
    users = active_clients()
    key = sorted((u["uuid"], u["username"]) for u in users)
    if force or key != _applied:
        await xray.apply(users)
        _applied = key

async def tick():
    stats = await xray.query_stats()
    if stats:
        today = date.today().isoformat()
        with db() as c:
            for name, b in stats.items():
                c.execute("UPDATE users SET used_bytes=used_bytes+? WHERE username=?", (b, name))
                c.execute("INSERT INTO usage_daily(username,day,bytes) VALUES(?,?,?) "
                          "ON CONFLICT(username,day) DO UPDATE SET bytes=bytes+?", (name, today, b, b))
    await sync()

async def loop():
    while True:
        await asyncio.sleep(30)
        try:
            await tick()
        except Exception as e:
            print("[loop]", e)

@asynccontextmanager
async def lifespan(app):
    if not C.ADMIN_PASS or not C.SECRET:
        raise RuntimeError("ADMIN_PASS and PANEL_SECRET must be set in .env")
    init()
    await sync(force=True)
    task = asyncio.create_task(loop())
    yield
    task.cancel()
    await xray.stop()

app = FastAPI(title="Simorgh", lifespan=lifespan, docs_url=None, redoc_url=None)
bearer = HTTPBearer(auto_error=False)

def admin(cred: Optional[HTTPAuthorizationCredentials] = Depends(bearer)):
    try:
        jwt.decode(cred.credentials, C.SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "نشست منقضی شده")

class Login(BaseModel):
    username: str
    password: str

class NewUser(BaseModel):
    username: str = Field(pattern=r"^[A-Za-z0-9_]{3,32}$")
    total_gb: float = Field(gt=0, le=100000)
    days: int = Field(gt=0, le=3650)

class Patch(BaseModel):
    total_gb: Optional[float] = Field(None, gt=0, le=100000)
    days: Optional[int] = Field(None, gt=0, le=3650)
    enabled: Optional[bool] = None

def view(u):
    return {"username": u["username"], "used_gb": round(u["used_bytes"] / GB, 2),
            "total_gb": round(u["total_bytes"] / GB, 2), "expire": u["expire_ts"],
            "enabled": bool(u["enabled"]), "active": is_active(u),
            "sub_url": f"{C.BASE_URL}/sub/{u['token']}"}

@app.post("/api/login")
def login(b: Login):
    ok = hmac.compare_digest(b.username, C.ADMIN_USER) & hmac.compare_digest(b.password, C.ADMIN_PASS)
    if not ok:
        time.sleep(1)  # slow down brute force
        raise HTTPException(401, "نام کاربری یا رمز اشتباه است")
    return {"token": jwt.encode({"exp": int(time.time()) + 12 * 3600}, C.SECRET, algorithm="HS256")}

@app.get("/api/users", dependencies=[Depends(admin)])
def users():
    with db() as c:
        return [view(u) for u in c.execute("SELECT * FROM users ORDER BY created_ts DESC")]

@app.post("/api/users", dependencies=[Depends(admin)])
async def create(b: NewUser):
    now = int(time.time())
    with db() as c:
        if c.execute("SELECT 1 FROM users WHERE username=?", (b.username,)).fetchone():
            raise HTTPException(409, "این نام قبلاً استفاده شده")
        c.execute("INSERT INTO users VALUES(?,?,?,?,0,?,1,?)",
                  (b.username, str(uuidlib.uuid4()), secrets.token_urlsafe(24),
                   int(b.total_gb * GB), now + b.days * 86400, now))
    await sync()
    return {"ok": True}

@app.patch("/api/users/{name}", dependencies=[Depends(admin)])
async def patch(name: str, b: Patch):
    with db() as c:
        if not c.execute("SELECT 1 FROM users WHERE username=?", (name,)).fetchone():
            raise HTTPException(404, "کاربر پیدا نشد")
        if b.total_gb is not None:
            c.execute("UPDATE users SET total_bytes=? WHERE username=?", (int(b.total_gb * GB), name))
        if b.days is not None:
            c.execute("UPDATE users SET expire_ts=? WHERE username=?", (int(time.time()) + b.days * 86400, name))
        if b.enabled is not None:
            c.execute("UPDATE users SET enabled=? WHERE username=?", (int(b.enabled), name))
    await sync()
    return {"ok": True}

@app.post("/api/users/{name}/reset", dependencies=[Depends(admin)])
async def reset(name: str):
    with db() as c:
        c.execute("UPDATE users SET used_bytes=0 WHERE username=?", (name,))
        c.execute("DELETE FROM usage_daily WHERE username=?", (name,))
    await sync()
    return {"ok": True}

@app.delete("/api/users/{name}", dependencies=[Depends(admin)])
async def remove(name: str):
    with db() as c:
        c.execute("DELETE FROM users WHERE username=?", (name,))
        c.execute("DELETE FROM usage_daily WHERE username=?", (name,))
    await sync()
    return {"ok": True}

@app.get("/sub/{token}")
def sub(token: str, request: Request):
    with db() as c:
        u = c.execute("SELECT * FROM users WHERE token=?", (token,)).fetchone()
        if not u:
            raise HTTPException(404)
        ua = request.headers.get("user-agent", "")
        wants_page = ("text/html" in request.headers.get("accept", "")
                      and not CLIENT_UA.search(ua) and "raw" not in request.query_params)
        if wants_page:
            days = [(date.today() - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
            rows = {r["day"]: r["bytes"] for r in c.execute("SELECT day,bytes FROM usage_daily WHERE username=?", (u["username"],))}
            data = {"name": u["username"], "sub_url": f"{C.BASE_URL}/sub/{token}",
                    "total_gb": round(u["total_bytes"] / GB, 2), "used_gb": round(u["used_bytes"] / GB, 2),
                    "expire": u["expire_ts"], "daily_gb": [round(rows.get(d, 0) / GB, 2) for d in days],
                    "support_url": C.SUPPORT_URL}
            html = (STATIC / "sub.html").read_text(encoding="utf-8")
            inject = "<script>window.SIMORGH_DATA=" + json.dumps(data).replace("</", "<\\/") + "</script></head>"
            return HTMLResponse(html.replace("</head>", inject, 1))
    body = base64.b64encode(xray.vless_link(u).encode()).decode() if is_active(u) else ""
    h = {"subscription-userinfo": f"upload=0; download={u['used_bytes']}; total={u['total_bytes']}; expire={u['expire_ts']}",
         "profile-title": "Simorgh", "profile-update-interval": "6", "support-url": C.SUPPORT_URL}
    return PlainTextResponse(body, headers=h)

@app.get("/admin")
def admin_page():
    return FileResponse(STATIC / "admin.html")

@app.get("/")
def root():
    return RedirectResponse("/admin")
