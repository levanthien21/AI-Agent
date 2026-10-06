"""Bọc Gemini API: tạo embedding và sinh câu trả lời."""
import math
from google import genai
from google.genai import types

from . import config

_client = None

def client() -> genai.Client:
    global _client
    if _client is None:
        if not config.GEMINI_API_KEY:
            raise RuntimeError("Chưa cấu hình GEMINI_API_KEY trong file .env")
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client

def embed(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    """Trả về mảng 2 chiều các vector đã chuẩn hoá để dùng cosine = tích vô hướng."""
    out = []
    for i in range(0, len(texts), 100):
        batch = texts[i : i + 100]
        res = client().models.embed_content(
            model=config.EMBED_MODEL,
            contents=batch,
            config=types.EmbedContentConfig(
                task_type=task_type, output_dimensionality=config.EMBED_DIM
            ),
        )
        for e in res.embeddings:
            vec = e.values
            norm = math.sqrt(sum(x * x for x in vec))
            if norm > 1e-9:
                vec = [x / norm for x in vec]
            out.append(vec)
    return out

def embed_query(text: str) -> list[float]:
    return embed([text], task_type="RETRIEVAL_QUERY")[0]

def generate(system: str, history: list[dict], user_message: str) -> str:
    """history: [{'role': 'user'|'model', 'text': str}, ...]"""
    contents = [
        types.Content(role=h["role"], parts=[types.Part(text=h["text"])]) for h in history
    ]
    contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))
    
    try:
        res = client().models.generate_content(
            model=config.CHAT_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=system, temperature=0.3),
        )
        return (res.text or "").strip()
    except Exception as e:
        raise e
