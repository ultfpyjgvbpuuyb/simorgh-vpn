import os
from pathlib import Path

def env(k, d=""):
    return os.environ.get(k, d)

DATA_DIR = Path(env("DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "simorgh.db"
XRAY_CONFIG = DATA_DIR / "xray.json"
XRAY_BIN = env("XRAY_BIN", "xray")
API_PORT = 10085  # Xray stats API, bound to 127.0.0.1 only

ADMIN_USER = env("ADMIN_USER", "admin")
ADMIN_PASS = env("ADMIN_PASS")
SECRET = env("PANEL_SECRET")
BASE_URL = env("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
SUPPORT_URL = env("SUPPORT_URL", "#")

HOST = env("SERVER_HOST", "127.0.0.1")
XRAY_PORT = int(env("XRAY_PORT", "443"))
PRIV = env("REALITY_PRIVATE_KEY")
PUB = env("REALITY_PUBLIC_KEY")
SNI = env("REALITY_SNI", "www.cloudflare.com")
SID = env("REALITY_SHORT_ID")
