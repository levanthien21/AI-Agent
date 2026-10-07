"""B?c Gemini API cho embedding v DeepSeek API sinh cu tr? l?i."""
import math
import time
from google import genai
from google.genai import types
from openai import OpenAI

from . import config

_client = None
_ds_client = None

def client() -> genai.Client:
    global _client
    if _client is None:
        if not config.GEMINI_API_KEY:
            raise RuntimeError("Chua c?u hnh GEMINI_API_KEY trong file .env")
        _client = genai.Client(api_key=config.GEMINI_API_KEY, http_options={"timeout": 8.0})
    return _client

def ds_client() -> OpenAI:
    global _ds_client
    if _ds_client is None:
        if not config.DEEPSEEK_API_KEY:
            raise RuntimeError("Chua c?u hnh DEEPSEEK_API_KEY trong file .env")
        _ds_client = OpenAI(api_key=config.DEEPSEEK_API_KEY, base_url="https://api.deepseek.com", timeout=8.0)
    return _ds_client

def embed(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    """Tr? v? m?ng 2 chi?u cc vector da chu?n ho d? dng cosine = tch v hu?ng."""
    out = []
    for i in range(0, len(texts), 100):
        batch = texts[i : i + 100]
        for attempt in range(3):
            try:
                res = client().models.embed_content(
                    model=config.EMBED_MODEL,
                    contents=batch,
                    config=types.EmbedContentConfig(
                        task_type=task_type, output_dimensionality=config.EMBED_DIM
                    ),
                )
                break
            except Exception as e:
                msg = str(e)
                transient = any(c in msg for c in ("429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE"))
                if not transient or attempt == 2:
                    raise
                time.sleep(0.5 * (attempt + 1))
        for e in res.embeddings:
            vec = e.values
            norm = math.sqrt(sum(x * x for x in vec))
            if norm > 1e-9:
                vec = [x / norm for x in vec]
            out.append(vec)
    return out

def embed_query(text: str) -> list[float]:
    return embed([text], task_type="RETRIEVAL_QUERY")[0]

def generate_stream(system: str, history: list[dict], user_message: str, max_tokens: int = 150):
    messages = [{"role": "system", "content": system}]
    for h in history:
        messages.append({"role": "assistant" if h["role"] == "model" else "user", "content": h["text"]})
    messages.append({"role": "user", "content": user_message})
    
    last_err = None
    for model in config.CHAT_MODELS:
        try:
            res = ds_client().chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.3,
                stream=True
            )
            for chunk in res:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
            return
        except Exception as e:
            last_err = e
            msg = str(e)
            if any(c in msg for c in ("503", "429", "404", "Rate limit", "timeout")):
                continue
            raise
    raise last_err

def generate(system: str, history: list[dict], user_message: str, max_tokens: int = 150) -> str:
    return "".join(generate_stream(system, history, user_message, max_tokens)).strip()
