"""Kho kiến thức theo lĩnh vực (domain) lưu trên Firebase Firestore."""
import base64
import json
import threading
import time
import uuid

import firebase_admin
from firebase_admin import credentials, firestore

from . import config

_lock = threading.Lock()

DEFAULT_CONFIG = {
    "display_name": "",
    "persona": "Bạn là trợ lý chăm sóc khách hàng thân thiện, lịch sự và chuyên nghiệp.",
    "greeting": "Xin chào! Mình có thể giúp gì cho bạn?",
    "fallback": "Xin lỗi, mình chưa có thông tin này. Bạn vui lòng để lại số điện thoại, nhân viên sẽ liên hệ hỗ trợ sớm nhất.",
    "tokens": 5000, # Số lượng token mặc định ban đầu
    "active": True,
    "timeout": 15, # Giây chờ tối đa
    "max_tokens": 150,
    "fb_page_token": "", # Số lượng token tối đa (càng ít càng nhanh)
}

class DomainError(Exception):
    pass

_db = None

def db() -> firestore.firestore.Client:
    global _db
    if _db is None:
        if not config.FIREBASE_BASE64:
            raise RuntimeError("Chưa cấu hình FIREBASE_BASE64")
        try:
            # Try raw JSON first
            try:
                cred_dict = json.loads(config.FIREBASE_BASE64)
            except ValueError:
                # If not JSON, assume Base64
                b64_str = config.FIREBASE_BASE64.strip()
                b64_str += "=" * ((4 - len(b64_str) % 4) % 4)
                cred_json = base64.b64decode(b64_str).decode("utf-8")
                cred_dict = json.loads(cred_json)
                
            cred = credentials.Certificate(cred_dict)
            if not firebase_admin._apps:
                firebase_admin.initialize_app(cred)
        except Exception as e:
            raise RuntimeError(f"Lỗi đọc Firebase credential: {e}")
        _db = firestore.client()
    return _db


# RAM Cache để tránh tốn quá nhiều lượt đọc (Reads) của Firebase mỗi khi chat
# Lưu trữ dạng: { name: (timestamp, chunks_list, numpy_matrix) }
_cache = {}
CACHE_TTL = 300  # 5 phút cache

def _load_cache(name: str):
    docs = db().collection("chunks").where("domain_name", "==", name).stream()
    chunks = []
    vecs = []
    for doc in docs:
        d = doc.to_dict()
        chunks.append({"text": d["text"], "source": d["source"]})
        vecs.append(d["embedding"])
    
    if not chunks:
        _cache[name] = (time.time(), [], [])
    else:
        _cache[name] = (time.time(), chunks, vecs)

def _get_cache(name: str):
    if name not in _cache or time.time() - _cache[name][0] > CACHE_TTL:
        _load_cache(name)
    return _cache[name][1], _cache[name][2]


def exists(name: str) -> bool:
    return db().collection("domains").document(name).get().exists

def list_domains() -> list[dict]:
    domains = []
    for doc in db().collection("domains").stream():
        d = doc.to_dict()
        name = doc.id
        
        # Đếm số lượng chunks cực nhanh nhờ Aggregate Query của Firestore (tốn 1 lượt đọc)
        chunks_ref = db().collection("chunks").where("domain_name", "==", name)
        count_query = chunks_ref.count().get()
        chunk_count = count_query[0][0].value if count_query else 0
        
        domains.append({
            "name": name,
            "display_name": d.get("config", {}).get("display_name") or name,
            "chunks": chunk_count,
            "sources": 0 # Giản lược ở màn danh sách để tiết kiệm reads
        })
    return domains

def create_domain(name: str, **cfg) -> dict:
    if exists(name):
        raise DomainError("Lĩnh vực đã tồn tại")
    
    config_data = dict(DEFAULT_CONFIG)
    config_data.update({k: v for k, v in cfg.items() if v is not None and k in DEFAULT_CONFIG})
    db().collection("domains").document(name).set({"config": config_data})
    return config_data

def delete_domain(name: str) -> None:
    db().collection("domains").document(name).delete()
    _cache.pop(name, None)

def get_config(name: str) -> dict:
    doc = db().collection("domains").document(name).get()
    if not doc.exists:
        raise DomainError("Không tìm thấy lĩnh vực")
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(doc.to_dict().get("config", {}))
    return cfg

def save_config(name: str, updates: dict) -> dict:
    cfg = get_config(name)
    cfg.update({k: v for k, v in updates.items() if k in DEFAULT_CONFIG and v is not None})
    db().collection("domains").document(name).update({"config": cfg})
    return cfg

def add_chunks(name: str, source: str, texts: list[str], vectors) -> int:
    with _lock:
        if not exists(name):
            raise DomainError("Không tìm thấy lĩnh vực")
        
        # Xoá cũ
        old_docs = db().collection("chunks").where("domain_name", "==", name).where("source", "==", source).stream()
        batch = db().batch()
        deletes = 0
        for doc in old_docs:
            batch.delete(doc.reference)
            deletes += 1
            if deletes == 500:
                batch.commit()
                batch = db().batch()
                deletes = 0
        if deletes > 0:
            batch.commit()
            
        # Thêm mới
        batch = db().batch()
        adds = 0
        for t, v in zip(texts, vectors):
            doc_ref = db().collection("chunks").document(uuid.uuid4().hex)
            batch.set(doc_ref, {
                "domain_name": name,
                "source": source,
                "text": t,
                "embedding": v
            })
            adds += 1
            if adds == 500:
                batch.commit()
                batch = db().batch()
                adds = 0
        if adds > 0:
            batch.commit()
            
        _cache.pop(name, None)  # Tuỳ ý invalidate cache
    return len(texts)

def delete_source(name: str, source: str) -> int:
    with _lock:
        old_docs = db().collection("chunks").where("domain_name", "==", name).where("source", "==", source).stream()
        batch = db().batch()
        count = 0
        for doc in old_docs:
            batch.delete(doc.reference)
            count += 1
            if count % 500 == 0:
                batch.commit()
                batch = db().batch()
        if count % 500 != 0:
            batch.commit()
            
        _cache.pop(name, None)
        return count

def list_sources(name: str) -> list[dict]:
    chunks, _ = _get_cache(name)
    counts = {}
    for c in chunks:
        counts[c["source"]] = counts.get(c["source"], 0) + 1
    return [{"source": s, "chunks": n} for s, n in counts.items()]

def get_all_knowledge(name: str) -> str:
    chunks, _ = _get_cache(name)
    texts = [doc["text"] for doc in chunks]
    return "\n\n".join(texts)

def search(name: str, qvec: list[float], k: int, min_score: float) -> list[dict]:
    chunks, vecs = _get_cache(name)
    if not chunks:
        return []
    
    results = []
    for i, v in enumerate(vecs):
        score = sum(a * b for a, b in zip(v, qvec))
        if score >= min_score:
            results.append({**chunks[i], "score": score})
            
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:k]

def deduct_tokens(name: str, amount: int) -> bool:
    try:
        db().collection("domains").document(name).set({
            "config": {
                "tokens": firestore.Increment(-amount)
            }
        }, merge=True)
        return True
    except Exception:
        return False

def add_tokens(name: str, amount: int) -> int:
    try:
        db().collection("domains").document(name).set({
            "config": {
                "tokens": firestore.Increment(amount),
                "active": True
            }
        }, merge=True)
        cfg = get_config(name)
        return cfg.get("tokens", 0)
    except Exception:
        return 0

def get_main_knowledge(name: str) -> str:
    chunks, _ = _get_cache(name)
    main_texts = [c["text"] for c in chunks if c["source"] == "main-knowledge"]
    return "\n\n".join(main_texts)

def save_chat_history(name: str, session_id: str, question: str, answer: str, tokens_used: int, source: str = "web"):
    try:
        doc_ref = db().collection("domains").document(name).collection("history").document()
        doc_ref.set({
            "session_id": session_id,
            "question": question,
            "answer": answer,
            "tokens_used": tokens_used,
            "source": source,
            "timestamp": firestore.SERVER_TIMESTAMP
        })
    except Exception as e:
        print("L?i luu l?ch s?:", e)

def get_chat_history(name: str, limit: int = 50) -> list[dict]:
    try:
        docs = db().collection("domains").document(name).collection("history").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit).stream()
        res = []
        for doc in docs:
            data = doc.to_dict()
            ts = data.get("timestamp")
            if ts:
                # convert datetime to string
                data["timestamp"] = ts.isoformat() if hasattr(ts, 'isoformat') else str(ts)
            res.append(data)
        return res
    except Exception as e:
        print("L?i l?y l?ch s?:", e)
        return []
