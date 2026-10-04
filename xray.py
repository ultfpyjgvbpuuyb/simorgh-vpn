import asyncio, json, shutil
from urllib.parse import quote
from . import config as C

_proc = None

def build_config(users):
    clients = [{"id": u["uuid"], "email": u["username"], "flow": "xtls-rprx-vision"} for u in users]
    return {
        "log": {"loglevel": "warning"},
        "stats": {},
        "api": {"tag": "api", "services": ["StatsService"]},
        "policy": {"levels": {"0": {"statsUserUplink": True, "statsUserDownlink": True}}},
        "inbounds": [
            {"tag": "api-in", "listen": "127.0.0.1", "port": C.API_PORT, "protocol": "dokodemo-door",
             "settings": {"address": "127.0.0.1"}},
            {"tag": "vless-in", "port": C.XRAY_PORT, "protocol": "vless",
             "settings": {"clients": clients, "decryption": "none"},
             "streamSettings": {"network": "tcp", "security": "reality", "realitySettings": {
                 "dest": f"{C.SNI}:443", "serverNames": [C.SNI],
                 "privateKey": C.PRIV, "shortIds": [C.SID]}},
             "sniffing": {"enabled": True, "destOverride": ["http", "tls", "quic"]}},
        ],
        "outbounds": [{"protocol": "freedom", "tag": "direct"}, {"protocol": "blackhole", "tag": "block"}],
        "routing": {"rules": [{"type": "field", "inboundTag": ["api-in"], "outboundTag": "api"}]},
    }

async def apply(users):
    """Write config and (re)start Xray."""
    global _proc
    C.XRAY_CONFIG.write_text(json.dumps(build_config(users), indent=2))
    if not shutil.which(C.XRAY_BIN):
        print("[xray] binary not found, config written only")
        return
    if _proc and _proc.returncode is None:
        _proc.terminate()
        try:
            await asyncio.wait_for(_proc.wait(), 5)
        except asyncio.TimeoutError:
            _proc.kill()
    _proc = await asyncio.create_subprocess_exec(C.XRAY_BIN, "run", "-c", str(C.XRAY_CONFIG))

async def stop():
    if _proc and _proc.returncode is None:
        _proc.terminate()

async def query_stats():
    """Return {username: bytes since last call} and reset counters."""
    if not shutil.which(C.XRAY_BIN):
        return {}
    p = await asyncio.create_subprocess_exec(
        C.XRAY_BIN, "api", "statsquery", f"--server=127.0.0.1:{C.API_PORT}", "-pattern", "user>>>", "-reset",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    out, _ = await p.communicate()
    try:
        items = json.loads(out or b"{}").get("stat", [])
    except json.JSONDecodeError:
        return {}
    res = {}
    for s in items:
        parts = s["name"].split(">>>")  # user>>>NAME>>>traffic>>>uplink
        if len(parts) == 4:
            res[parts[1]] = res.get(parts[1], 0) + int(s.get("value", 0))
    return res

def vless_link(u):
    q = (f"encryption=none&flow=xtls-rprx-vision&security=reality&sni={C.SNI}&fp=chrome"
         f"&pbk={C.PUB}&sid={C.SID}&type=tcp")
    return f"vless://{u['uuid']}@{C.HOST}:{C.XRAY_PORT}?{q}#{quote('Simorgh-' + u['username'])}"
