import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ADMIN_KEY = os.getenv("ADMIN_KEY", "")
FIREBASE_BASE64 = os.getenv("FIREBASE_BASE64", "")
CHAT_MODEL = os.getenv("CHAT_MODEL", "deepseek-chat")
# Thứ tự thử model: lite (ổn định nhất) -> flash thường. Đổi bằng biến môi trường CHAT_MODELS (cách nhau bởi dấu phẩy).
CHAT_MODELS = [m.strip() for m in os.getenv(
    "CHAT_MODELS",
    f"{CHAT_MODEL},deepseek-reasoner",
).split(",") if m.strip()]
EMBED_MODEL = os.getenv("EMBED_MODEL", "gemini-embedding-001")
EMBED_DIM = 768
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]

TOP_K = 5            # số đoạn kiến thức đưa vào prompt
MIN_SCORE = 0.35     # dưới ngưỡng này coi như không liên quan
HISTORY_TURNS = 8    # số lượt hội thoại nhớ trong mỗi phiên
