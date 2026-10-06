import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
ADMIN_KEY = os.getenv("ADMIN_KEY", "")
FIREBASE_BASE64 = os.getenv("FIREBASE_BASE64", "")
CHAT_MODEL = os.getenv("CHAT_MODEL", "gemini-2.5-flash")
EMBED_MODEL = os.getenv("EMBED_MODEL", "gemini-embedding-001")
EMBED_DIM = 768
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]

DATA_DIR = BASE_DIR / "data" / "domains"
DATA_DIR.mkdir(parents=True, exist_ok=True)

TOP_K = 5            # số đoạn kiến thức đưa vào prompt
MIN_SCORE = 0.35     # dưới ngưỡng này coi như không liên quan
HISTORY_TURNS = 8    # số lượt hội thoại nhớ trong mỗi phiên
