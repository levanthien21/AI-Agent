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
    cfg = store.get_config(domain)  # ném DomainError nếu domain không tồn tại
    history = _sessions[(domain, session_id)]

    # Câu hỏi ngắn kiểu "còn size L không?" cần ngữ cảnh câu trước để tìm đúng
    query = message
    if len(message) < 25 and history:
        prev_user = next((h["text"] for h in reversed(history) if h["role"] == "user"), "")
        query = f"{prev_user}\n{message}"

    hits = store.search(domain, llm.embed_query(query), config.TOP_K, config.MIN_SCORE)
    knowledge = "\n".join(f"- {h['text']}" for h in hits) or "(không có thông tin liên quan)"
    prompt = f"KIẾN THỨC:\n{knowledge}\n\nTIN NHẮN CỦA KHÁCH:\n{message}"

    answer = llm.generate(_system_prompt(cfg), history[-config.HISTORY_TURNS * 2 :], prompt) or cfg["fallback"]

    # Lưu lịch sử với tin nhắn gốc (không kèm kiến thức) để prompt gọn
    history += [{"role": "user", "text": message}, {"role": "model", "text": answer}]
    del history[: -config.HISTORY_TURNS * 2]
    return {"answer": answer, "sources": sorted({h["source"] for h in hits})}


def reset(domain: str, session_id: str) -> None:
    _sessions.pop((domain, session_id), None)
