"""Loi agent: truy xu?t ki?n th?c theo linh v?c r?i sinh cu tr? l?i."""
from collections import defaultdict
import time
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

def reply(domain: str, session_id: str, message_data) -> dict:
    t0 = time.time()
    cfg = store.get_config(domain)
    tokens_left = cfg.get("tokens", 0)
    if tokens_left <= 0:
        return {"answer": "H? th?ng AI dang t?m ngung do h?t h?n m?c (tokens). Vui lng lin h? qu?n tr? vin d? n?p thm.", "sources": []}

    history = _sessions[(domain, session_id)]
    
    text_content = ""
    image_urls = []
    
    if isinstance(message_data, dict):
        text_content = message_data.get("text", "")
        image_urls = message_data.get("images", [])
    else:
        text_content = str(message_data)
        
    query = text_content
    if len(text_content) < 25 and history:
        prev_user = next((h["text"] for h in reversed(history) if h["role"] == "user"), "")
        query = f"{prev_user}\n{text_content}"

    all_text = store.get_all_knowledge(domain)
    if len(all_text) > 50000:
        all_text = all_text[:50000] + "\n...(cn ti?p)"
    knowledge = all_text or "(khng c thng tin lin quan)"

    prompt_text = f"KI?N TH?C:\n{knowledge}\n\nTIN NH?N C?A KHACH:\n{text_content}"
    
    # Construct llm payload
    if image_urls:
        prompt_payload = [{"type": "text", "text": prompt_text}]
        for url in image_urls:
            prompt_payload.append({"type": "image_url", "image_url": {"url": url}})
    else:
        prompt_payload = prompt_text

    max_tok = cfg.get("max_tokens", 150)
    timeout_sec = cfg.get("timeout", 15)
    
    log_messages = []
    log_messages.append(f"Nh?n tin nh?n t? {session_id}. Lo?i: {'C Hnh ?nh' if image_urls else 'Text'}")
    log_messages.append(f"Context stuff length: {len(all_text)} chars")
    
    try:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(llm.generate, _system_prompt(cfg), history[-config.HISTORY_TURNS * 2 :], prompt_payload, max_tok)
            answer = future.result(timeout=timeout_sec)
        
        if not answer:
            answer = cfg["fallback"]
    except concurrent.futures.TimeoutError:
        log_messages.append("L?i: Timeout API")
        answer = cfg["fallback"]
    except Exception as e:
        log_messages.append(f"L?i API: {e}")
        answer = cfg["fallback"]
        
    t1 = time.time()
    log_messages.append(f"Th?i gian x? l: {round(t1-t0, 2)}s")
    
    cost = len(text_content) + len(answer) + (500 * len(image_urls)) # approximation for images
    store.deduct_tokens(domain, cost)
    
    debug_log = "\n".join(log_messages)
    
    # save_chat_history needs to support debug_log. We will add it to kwargs.
    store.save_chat_history(domain, session_id, text_content if text_content else "[Hnh ?nh]", answer, cost, source="facebook" if "fb" in session_id else "web", debug_log=debug_log)

    history += [{"role": "user", "text": text_content if text_content else "[Hnh ?nh]"}, {"role": "model", "text": answer}]
    del history[: -config.HISTORY_TURNS * 2]
    return {"answer": answer, "sources": []}

def reset(domain: str, session_id: str) -> None:
    _sessions.pop((domain, session_id), None)

def reply_stream(domain: str, session_id: str, message: str):
    t0 = time.time()
    cfg = store.get_config(domain)
    tokens_left = cfg.get("tokens", 0)
    if tokens_left <= 0:
        yield "H? th?ng AI dang t?m ngung do h?t h?n m?c (tokens). Vui lng lin h? qu?n tr? vin d? n?p thm."
        return

    history = _sessions[(domain, session_id)]
    full_answer = ""
    log_messages = [f"Nh?n tin nh?n t? {session_id}. Lo?i: Text"]
    try:
        query = message
        if len(message) < 25 and history:
            prev_user = next((h["text"] for h in reversed(history) if h["role"] == "user"), "")
            query = f"{prev_user}\n{message}"

        all_text = store.get_all_knowledge(domain)
        if len(all_text) > 50000:
            all_text = all_text[:50000] + "\n...(cn ti?p)"
        knowledge = all_text or "(khng c thng tin lin quan)"
        log_messages.append(f"Context stuff length: {len(all_text)} chars")

        prompt = f"KI?N TH?C:\n{knowledge}\n\nTIN NH?N C?A KHACH:\n{message}"

        max_tok = cfg.get("max_tokens", 150)
        
        for chunk in llm.generate_stream(_system_prompt(cfg), history[-config.HISTORY_TURNS * 2 :], prompt, max_tok):
            full_answer += chunk
            yield chunk
    except Exception as e:
        log_messages.append(f"L?i API: {e}")
        if not full_answer:
            yield (cfg.get("fallback") or "H? th?ng dang b?n, vui lng th? l?i sau t pht.")
            full_answer = (cfg.get("fallback") or "H? th?ng dang b?n.")
        else:
            yield "\n[L?i k?t n?i b? ng?t]"

    if full_answer:
        t1 = time.time()
        log_messages.append(f"Th?i gian x? l: {round(t1-t0, 2)}s")
        cost = len(message) + len(full_answer)
        store.deduct_tokens(domain, cost)
        debug_log = "\n".join(log_messages)
        store.save_chat_history(domain, session_id, message, full_answer, cost, source="web", debug_log=debug_log)
        history += [{"role": "user", "text": message}, {"role": "model", "text": full_answer}]
        del history[: -config.HISTORY_TURNS * 2]
