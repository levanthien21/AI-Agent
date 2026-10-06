"""Bọc Gemini API: tạo embedding và sinh câu trả lời."""
import numpy as np
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


def embed(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> np.ndarray:
    """Trả về ma trận (n, dim) đã chuẩn hoá để dùng cosine = tích vô hướng."""
    out: list[list[float]] = []
    for i in range(0, len(texts), 100):
        batch = texts[i : i + 100]
        res = client().models.embed_content(
            model=config.EMBED_MODEL,
            contents=batch,
            config=types.EmbedContentConfig(
                task_type=task_type, output_dimensionality=config.EMBED_DIM
            ),
        )
        out.extend(e.values for e in res.embeddings)
    arr = np.asarray(out, dtype=np.float32)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    return arr / np.clip(norms, 1e-9, None)


def embed_query(text: str) -> np.ndarray:
    return embed([text], task_type="RETRIEVAL_QUERY")[0]


def generate(system: str, history: list[dict], user_message: str) -> str:
    """history: [{'role': 'user'|'model', 'text': str}, ...]"""
    contents = [
        types.Content(role=h["role"], parts=[types.Part(text=h["text"])]) for h in history
    ]
    contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))
    res = client().models.generate_content(
        model=config.CHAT_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(system_instruction=system, temperature=0.3),
    )
    return (res.text or "").strip()
