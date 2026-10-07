"""Lõi agent: truy xuất kiến thức theo lĩnh vực rồi sinh câu trả lời."""
from collections import defaultdict

from . import config, llm, store

_sessions: dict[tuple[str, str], list[dict]] = defaultdict(list)

RULES = """
QUY TẮC BẮT BUỘC VÀ SÁNG TẠO:
1. Ưu tiên sử dụng phần "KIẾN THỨC" được cung cấp để trả lời các câu hỏi về thông tin riêng, quy định, hoặc dữ liệu của tổ chức.
2. NẾU "KIẾN THỨC" KHÔNG CÓ CÂU TRẢ LỜI, hoặc khách hỏi các kiến thức phổ thông, trò chuyện ngoài lề, bạn HÃY SÁNG TẠO và sử dụng vốn hiểu biết chung của mình để trả lời thật thông minh, nhiệt tình và phù hợp với vai trò của mình.
3. Luôn nhập vai xuất sắc, giọng văn tự nhiên, thân thiện như một người thật đang trò chuyện.
4. KHÔNG BAO GIỜ nói câu: "{fallback}" trừ khi hệ thống của bạn bị lỗi không thể lấy được thông tin.
5. Tuyệt đối không nhắc đến việc bạn là AI hay bạn đang đọc từ "tài liệu", "kiến thức được cung cấp". Không dùng các cụm từ như "Dựa trên thông tin được cung cấp...".
"""


def _system_prompt(cfg: dict) -> str:
    return cfg["persona"].strip() + "\n" + RULES.format(fallback=cfg["fallback"])


def reply(domain: str, session_id: str, message: str) -> dict:
    cfg = store.get_config(domain)
    tokens_left = cfg.get("tokens", 0)
    if tokens_left <= 0:
        return {"answer": "Hệ thống AI đang tạm ngưng do hết hạn mức (tokens). Vui lòng liên hệ quản trị viên để nạp thêm.", "sources": []}

    history = _sessions[(domain, session_id)]

    query = message
    if len(message) < 25 and history:
        prev_user = next((h["text"] for h in reversed(history) if h["role"] == "user"), "")
        query = f"{prev_user}\n{message}"

    hits = store.search(domain, llm.embed_query(query), config.TOP_K, config.MIN_SCORE)
    knowledge = "\n".join(f"- {h['text']}" for h in hits) or "(không có thông tin liên quan)"
    prompt = f"KIẾN THỨC:\n{knowledge}\n\nTIN NHẮN CỦA KHÁCH:\n{message}"

    max_tok = cfg.get("max_tokens", 150)
    timeout_sec = cfg.get("timeout", 15)
    
    try:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            # LLM trả lời với độ dài bị giới hạn để tăng tốc
            future = executor.submit(llm.generate, _system_prompt(cfg), history[-config.HISTORY_TURNS * 2 :], prompt, max_tok)
            answer = future.result(timeout=timeout_sec)
        
        if not answer:
            answer = cfg["fallback"]
    except concurrent.futures.TimeoutError:
        answer = cfg["fallback"]
    except Exception as e:
        # Xử lý khi LLM lỗi
        answer = cfg["fallback"]
        
    # Trừ tokens (1 ký tự = ~0.25 token, nhưng để đơn giản ta tính 1 token = 1 ký tự text + answer)
    # hoặc cứ gọi token là đơn vị ký tự cho dễ kinh doanh
    cost = len(message) + len(answer)
    store.deduct_tokens(domain, cost)

    # Lưu lịch sử với tin nhắn gốc (không kèm kiến thức) để prompt gọn
    history += [{"role": "user", "text": message}, {"role": "model", "text": answer}]
    del history[: -config.HISTORY_TURNS * 2]
    return {"answer": answer, "sources": sorted({h["source"] for h in hits})}


def reset(domain: str, session_id: str) -> None:
    _sessions.pop((domain, session_id), None)

def reply_stream(domain: str, session_id: str, message: str):
    cfg = store.get_config(domain)
    tokens_left = cfg.get("tokens", 0)
    if tokens_left <= 0:
        yield "Hệ thống AI đang tạm ngưng do hết hạn mức (tokens). Vui lòng liên hệ quản trị viên để nạp thêm."
        return

    history = _sessions[(domain, session_id)]
    query = message
    if len(message) < 25 and history:
        prev_user = next((h["text"] for h in reversed(history) if h["role"] == "user"), "")
        query = f"{prev_user}\n{message}"

    hits = store.search(domain, llm.embed_query(query), config.TOP_K, config.MIN_SCORE)
    knowledge = "\n".join(f"- {h['text']}" for h in hits) or "(không có thông tin liên quan)"
    prompt = f"KIẾN THỨC:\n{knowledge}\n\nTIN NHẮN CỦA KHÁCH:\n{message}"

    max_tok = cfg.get("max_tokens", 150)
    
    full_answer = ""
    try:
        for chunk in llm.generate_stream(_system_prompt(cfg), history[-config.HISTORY_TURNS * 2 :], prompt, max_tok):
            full_answer += chunk
            yield chunk
    except Exception as e:
        if not full_answer:
            yield cfg["fallback"]
            full_answer = cfg["fallback"]
        else:
            yield "\n[Lỗi kết nối bị ngắt]"

    cost = len(message) + len(full_answer)
    store.deduct_tokens(domain, cost)

    history += [{"role": "user", "text": message}, {"role": "model", "text": full_answer}]
    del history[: -config.HISTORY_TURNS * 2]
