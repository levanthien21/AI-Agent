"""Loi agent: truy xu?t ki?n th?c theo linh v?c r?i sinh cu tr? l?i."""
from collections import defaultdict

from . import config, llm, store

_sessions: dict[tuple[str, str], list[dict]] = defaultdict(list)

RULES = """
QUY T?C B?T BU?C VA SANG T?O:
1. Uu tin s? d?ng ph?n "KI?N TH?C" du?c cung c?p d? tr? l?i cc cu h?i v? thng tin ring, quy d?nh, ho?c d? li?u c?a t? ch?c.
2. N?U "KI?N TH?C" KHONG CO CAU TR? L?I, ho?c khch h?i cc ki?n th?c ph? thng, tr chuy?n ngoi l?, b?n HAY SANG T?O v s? d?ng v?n hi?u bi?t chung c?a mnh d? tr? l?i th?t thng minh, nhi?t tnh v ph h?p v?i vai tr c?a mnh.
3. Lun nh?p vai xu?t s?c, gi?ng van t? nhin, thn thi?n nhu m?t ngu?i th?t dang tr chuy?n.
4. KHONG BAO GI? ni cu: "{fallback}" tr? khi h? th?ng c?a b?n b? l?i khng th? l?y du?c thng tin.
5. Tuy?t d?i khng nh?c d?n vi?c b?n l AI hay b?n dang d?c t? "ti li?u", "ki?n th?c du?c cung c?p". Khng dng cc c?m t? nhu "D?a trn thng tin du?c cung c?p...".
"""


def _system_prompt(cfg: dict) -> str:
    return cfg["persona"].strip() + "\n" + RULES.format(fallback=cfg["fallback"])


def reply(domain: str, session_id: str, message: str) -> dict:
    cfg = store.get_config(domain)
    tokens_left = cfg.get("tokens", 0)
    if tokens_left <= 0:
        return {"answer": "H? th?ng AI dang t?m ngung do h?t h?n m?c (tokens). Vui lng lin h? qu?n tr? vin d? n?p thm.", "sources": []}

    history = _sessions[(domain, session_id)]

    query = message
    if len(message) < 25 and history:
        prev_user = next((h["text"] for h in reversed(history) if h["role"] == "user"), "")
        query = f"{prev_user}\n{message}"

    try:
        hits = store.search(domain, llm.embed_query(query), config.TOP_K, config.MIN_SCORE)
    except Exception as e:
        print("Embedding failed, skipping RAG:", e)
        hits = []

    knowledge = "\n".join(f"- {h['text']}" for h in hits) or "(khng c thng tin lin quan)"
    prompt = f"KI?N TH?C:\n{knowledge}\n\nTIN NH?N C?A KHACH:\n{message}"

    max_tok = cfg.get("max_tokens", 150)
    timeout_sec = cfg.get("timeout", 15)
    
    try:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            # LLM tr? l?i v?i d? di b? gi?i h?n d? tang t?c
            future = executor.submit(llm.generate, _system_prompt(cfg), history[-config.HISTORY_TURNS * 2 :], prompt, max_tok)
            answer = future.result(timeout=timeout_sec)
        
        if not answer:
            answer = cfg["fallback"]
    except concurrent.futures.TimeoutError:
        answer = cfg["fallback"]
    except Exception as e:
        # X? ly khi LLM l?i
        answer = cfg["fallback"]
        
    # Tr? tokens (1 ky t? = ~0.25 token, nhung d? don gi?n ta tnh 1 token = 1 ky t? text + answer)
    # ho?c c? g?i token l don v? ky t? cho d? kinh doanh
    cost = len(message) + len(answer)
    store.deduct_tokens(domain, cost)

    # Luu l?ch s? v?i tin nh?n g?c (khng km ki?n th?c) d? prompt g?n
    history += [{"role": "user", "text": message}, {"role": "model", "text": answer}]
    del history[: -config.HISTORY_TURNS * 2]
    return {"answer": answer, "sources": sorted({h["source"] for h in hits})}


def reset(domain: str, session_id: str) -> None:
    _sessions.pop((domain, session_id), None)

def reply_stream(domain: str, session_id: str, message: str):
    cfg = store.get_config(domain)
    tokens_left = cfg.get("tokens", 0)
    if tokens_left <= 0:
        yield "H? th?ng AI dang t?m ngung do h?t h?n m?c (tokens). Vui lng lin h? qu?n tr? vin d? n?p thm."
        return

    history = _sessions[(domain, session_id)]
    full_answer = ""
    try:
        query = message
        if len(message) < 25 and history:
            prev_user = next((h["text"] for h in reversed(history) if h["role"] == "user"), "")
            query = f"{prev_user}\n{message}"

        try:
            hits = store.search(domain, llm.embed_query(query), config.TOP_K, config.MIN_SCORE)
        except Exception as e:
            print("Embedding failed, skipping RAG:", e)
            hits = []

        knowledge = "\n".join(f"- {h['text']}" for h in hits) or "(khng c thng tin lin quan)"
        prompt = f"KI?N TH?C:\n{knowledge}\n\nTIN NH?N C?A KHACH:\n{message}"

        max_tok = cfg.get("max_tokens", 150)
        
        for chunk in llm.generate_stream(_system_prompt(cfg), history[-config.HISTORY_TURNS * 2 :], prompt, max_tok):
            full_answer += chunk
            yield chunk
    except Exception as e:
        if not full_answer:
            yield (cfg.get("fallback") or "H? th?ng dang b?n, vui lng th? l?i sau t pht.")
            full_answer = (cfg.get("fallback") or "H? th?ng dang b?n.")
        else:
            yield "\n[L?i k?t n?i b? ng?t]"

    if full_answer:
        cost = len(message) + len(full_answer)
        store.deduct_tokens(domain, cost)
        history += [{"role": "user", "text": message}, {"role": "model", "text": full_answer}]
        del history[: -config.HISTORY_TURNS * 2]
