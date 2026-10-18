"""Lõi agent: truy xuất kiến thức theo lĩnh vực rồi sinh câu trả lời."""
from collections import defaultdict
import time
from . import config, llm, store, autosurvey_knowledge

_sessions: dict[tuple[str, str], list[dict]] = defaultdict(list)
_synced_domains: set[str] = set()

def sync_autosurvey_to_firestore():
    if "SPSS Khảo Sát" in _synced_domains:
        return
    try:
        store.db().collection("domains").document("SPSS Khảo Sát").set({
            "config": {
                "display_name": "AutoSurvey VN - Trợ Lý Khảo Sát & SPSS",
                "greeting": "Dạ AutoSurvey VN chào bạn! 🚀 Bạn đang cần chạy gấp deadline khảo sát đúng không ạ? Bạn gửi link form để em kiểm tra cấu trúc câu hỏi và tư vấn gói báo giá nhanh nhất cho mình nhé! 📊",
                "persona": autosurvey_knowledge.AUTOSURVEY_PERSONA,
                "tokens": 999999999,
                "max_tokens": 600,
                "active": True
            }
        }, merge=True)
        _synced_domains.add("SPSS Khảo Sát")
    except Exception:
        pass

RULES = """
QUY TẮC BẮT BUỘC VÀ SÁNG TẠO:
1. Ưu tiên sử dụng phần "KIẾN THỨC" được cung cấp để trả lời các câu hỏi về thông tin riêng, quy định, gói cước, hoặc dữ liệu của tổ chức.
2. NẾU "KIẾN THỨC" KHÔNG CÓ CÂU TRẢ LỜI, hoặc khách hỏi các kiến thức phổ thông, trò chuyện ngoài lề, bạn HÃY SÁNG TẠO và sử dụng vốn hiểu biết chung của mình để trả lời thật thông minh, nhiệt tình và phù hợp với vai trò của mình.
3. Luôn nhập vai xuất sắc, giọng văn tự nhiên, thân thiện, đồng cảm với áp lực deadline.
4. KHÔNG BAO GIỜ nói câu: "{fallback}" trừ khi hệ thống của bạn bị lỗi không thể lấy được thông tin.
5. Tuyệt đối không nhắc đến việc bạn là AI hay bạn đang đọc từ "tài liệu", "kiến thức được cung cấp". Không dùng các cụm từ như "Dựa trên thông tin được cung cấp...".
"""

def _system_prompt(cfg: dict, domain: str = "") -> str:
    if domain == "SPSS Khảo Sát":
        return autosurvey_knowledge.AUTOSURVEY_PERSONA + "\n" + RULES.format(fallback=cfg.get("fallback", ""))
    return cfg["persona"].strip() + "\n" + RULES.format(fallback=cfg["fallback"])

def reply(domain: str, session_id: str, message_data, draft_only: bool = False) -> dict:
    t0 = time.time()
    cfg = store.get_config(domain)
    
    # Sync AutoSurvey persona to Firestore in background
    if domain == "SPSS Khảo Sát":
        sync_autosurvey_to_firestore()
    
    if session_id in cfg.get("paused_sessions", []):
        text_content = ""
        if isinstance(message_data, dict):
            text_content = message_data.get("text", "")
        else:
            text_content = str(message_data)
        store.save_chat_history(domain, session_id, text_content if text_content else "[Hình ảnh]", "", 0, source="facebook" if "fb" in session_id else "web", debug_log="AI đã bị tắt (Chế độ Người thật can thiệp)")
        
        # update history array too so context isn't lost
        _sessions[(domain, session_id)].append({"role": "user", "text": text_content if text_content else "[Hình ảnh]"})
        del _sessions[(domain, session_id)][: -config.HISTORY_TURNS * 2]
        
        return {"answer": "", "sources": [], "paused": True}
        
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

    if domain == "SPSS Khảo Sát":
        knowledge = autosurvey_knowledge.AUTOSURVEY_PERSONA
    else:
        all_text = store.get_all_knowledge(domain)
        if len(all_text) > 50000:
            all_text = all_text[:50000] + "\n...(còn tiếp)"
        knowledge = all_text or "(không có thông tin liên quan)"

    prompt_text = f"KIẾN THỨC:\n{knowledge}\n\nTIN NHẮN CỦA KHÁCH:\n{text_content}"
    
    # Construct llm payload
    if image_urls:
        prompt_payload = [{"type": "text", "text": prompt_text}]
        for url in image_urls:
            prompt_payload.append({"type": "image_url", "image_url": {"url": url}})
    else:
        prompt_payload = prompt_text

    max_tok = max(cfg.get("max_tokens", 600), 600)
    timeout_sec = cfg.get("timeout", 20)
    
    log_messages = []
    log_messages.append(f"Nhận tin nhắn từ {session_id}. Loại: {'Có Hình ảnh' if image_urls else 'Text'}")
    log_messages.append(f"Context stuff length: {len(knowledge)} chars")
    
    try:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(llm.generate, _system_prompt(cfg, domain), history[-config.HISTORY_TURNS * 2 :], prompt_payload, max_tok)
            answer = future.result(timeout=timeout_sec)
        
        if not answer:
            answer = cfg["fallback"]
    except concurrent.futures.TimeoutError:
        log_messages.append("Lỗi: Timeout API")
        answer = cfg["fallback"]
    except Exception as e:
        log_messages.append(f"Lỗi API: {e}")
        answer = cfg["fallback"]
        
    t1 = time.time()
    log_messages.append(f"Thời gian xử lý: {round(t1-t0, 2)}s")
    
    cost = len(text_content) + len(answer) + (500 * len(image_urls)) # approximation for images
    store.deduct_tokens(domain, cost)
    
    debug_log = "\n".join(log_messages)
    
    store.save_chat_history(domain, session_id, text_content if text_content else "[Hình ảnh]", answer, cost, source="facebook" if "fb" in session_id else "web", debug_log=debug_log)

    history += [{"role": "user", "text": text_content if text_content else "[Hình ảnh]"}, {"role": "model", "text": answer}]
    del history[: -config.HISTORY_TURNS * 2]
    return {"answer": answer, "sources": []}

def reset(domain: str, session_id: str) -> None:
    _sessions.pop((domain, session_id), None)

def reply_stream(domain: str, session_id: str, message: str):
    t0 = time.time()
    cfg = store.get_config(domain)
    
    if domain == "SPSS Khảo Sát":
        sync_autosurvey_to_firestore()
    
    if session_id in cfg.get("paused_sessions", []):
        yield ""
        return

    history = _sessions[(domain, session_id)]
    full_answer = ""
    log_messages = [f"Nhận tin nhắn từ {session_id}. Loại: Text"]
    try:
        query = message
        if len(message) < 25 and history:
            prev_user = next((h["text"] for h in reversed(history) if h["role"] == "user"), "")
            query = f"{prev_user}\n{message}"

        if domain == "SPSS Khảo Sát":
            knowledge = autosurvey_knowledge.AUTOSURVEY_PERSONA
        else:
            all_text = store.get_all_knowledge(domain)
            if len(all_text) > 50000:
                all_text = all_text[:50000] + "\n...(còn tiếp)"
            knowledge = all_text or "(không có thông tin liên quan)"
        log_messages.append(f"Context stuff length: {len(knowledge)} chars")

        prompt = f"KIẾN THỨC:\n{knowledge}\n\nTIN NHẮN CỦA KHÁCH:\n{message}"

        max_tok = max(cfg.get("max_tokens", 600), 600)
        
        for chunk in llm.generate_stream(_system_prompt(cfg, domain), history[-config.HISTORY_TURNS * 2 :], prompt, max_tok):
            full_answer += chunk
            yield chunk
    except Exception as e:
        log_messages.append(f"Lỗi API: {e}")
        if not full_answer:
            yield (cfg.get("fallback") or "Hệ thống đang bận, vui lòng thử lại sau ít phút.")
            full_answer = (cfg.get("fallback") or "Hệ thống đang bận.")
        else:
            yield "\n[Lỗi kết nối bị ngắt]"

    if full_answer:
        t1 = time.time()
        log_messages.append(f"Thời gian xử lý: {round(t1-t0, 2)}s")
        cost = len(message) + len(full_answer)
        store.deduct_tokens(domain, cost)
        debug_log = "\n".join(log_messages)
        store.save_chat_history(domain, session_id, message, full_answer, cost, source="web", debug_log=debug_log)
        history += [{"role": "user", "text": message}, {"role": "model", "text": full_answer}]
        del history[: -config.HISTORY_TURNS * 2]
