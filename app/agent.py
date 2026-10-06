"""Lõi agent: truy xuất kiến thức theo lĩnh vực rồi sinh câu trả lời."""
from collections import defaultdict

from . import config, llm, store

_sessions: dict[tuple[str, str], list[dict]] = defaultdict(list)

RULES = """
QUY TẮC BẮT BUỘC:
- Chỉ trả lời dựa trên phần "KIẾN THỨC" được cung cấp. Tuyệt đối không bịa giá, chính sách, số liệu hay thông tin không có trong đó.
- Nếu KIẾN THỨC không đủ để trả lời, hãy dùng đúng nội dung dự phòng sau, không nói gì thêm: "{fallback}"
- Với lời chào, cảm ơn, xã giao thì đáp tự nhiên, ngắn gọn.
- Trả lời bằng ngôn ngữ của khách (mặc định tiếng Việt), ngắn gọn, đúng trọng tâm, giọng văn như đang nhắn tin.
- Không nhắc đến việc bạn là AI đọc từ "tài liệu" hay "kiến thức được cung cấp".
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
