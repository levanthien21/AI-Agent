"""Kho kiến thức theo lĩnh vực (domain) lưu trên Supabase với pgvector."""
import re
import threading

from supabase import Client, create_client

from . import config

_NAME_RE = re.compile(r"^[a-z0-9_-]{1,40}$")
_lock = threading.Lock()

DEFAULT_CONFIG = {
    "display_name": "",
    "persona": "Bạn là trợ lý chăm sóc khách hàng thân thiện, lịch sự và chuyên nghiệp.",
    "greeting": "Xin chào! Mình có thể giúp gì cho bạn?",
    "fallback": "Xin lỗi, mình chưa có thông tin này. Bạn vui lòng để lại số điện thoại, nhân viên sẽ liên hệ hỗ trợ sớm nhất.",
}

class DomainError(Exception):
    pass

_sb_client = None

def _sb() -> Client:
    global _sb_client
    if _sb_client is None:
        if not config.SUPABASE_URL or not config.SUPABASE_KEY:
            raise RuntimeError("Chưa cấu hình SUPABASE_URL và SUPABASE_KEY")
        _sb_client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
    return _sb_client


def exists(name: str) -> bool:
    res = _sb().table("domains").select("name").eq("name", name).execute()
    return len(res.data) > 0


def list_domains() -> list[dict]:
    res = _sb().rpc("get_domain_stats", {}).execute()
    return [
        {
            "name": r["name"],
            "display_name": r["display_name"] or r["name"],
            "chunks": r["chunk_count"],
            "sources": r["source_count"],
        }
        for r in res.data
    ]


def create_domain(name: str, **cfg) -> dict:
    if not _NAME_RE.match(name):
        raise DomainError("Tên lĩnh vực chỉ gồm a-z, 0-9, '-' hoặc '_' (tối đa 40 ký tự)")
    if exists(name):
        raise DomainError("Lĩnh vực đã tồn tại")
    
    config_data = dict(DEFAULT_CONFIG)
    config_data.update({k: v for k, v in cfg.items() if v is not None and k in DEFAULT_CONFIG})
    
    _sb().table("domains").insert({"name": name, "config": config_data}).execute()
    return config_data


def delete_domain(name: str) -> None:
    _sb().table("domains").delete().eq("name", name).execute()


def get_config(name: str) -> dict:
    res = _sb().table("domains").select("config").eq("name", name).execute()
    if not res.data:
        raise DomainError("Không tìm thấy lĩnh vực")
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(res.data[0]["config"])
    return cfg


def save_config(name: str, updates: dict) -> dict:
    cfg = get_config(name)
    cfg.update({k: v for k, v in updates.items() if k in DEFAULT_CONFIG and v is not None})
    _sb().table("domains").update({"config": cfg}).eq("name", name).execute()
    return cfg


def add_chunks(name: str, source: str, texts: list[str], vectors) -> int:
    """Thêm kiến thức; nạp lại cùng tên file sẽ xoá bản cũ trên Supabase rồi thêm lại."""
    with _lock:
        if not exists(name):
            raise DomainError("Không tìm thấy lĩnh vực")
        
        # Xoá cũ
        _sb().table("chunks").delete().eq("domain_name", name).eq("source", source).execute()
        
        # Thêm mới theo batch (mỗi batch tối đa 500 dòng)
        vec_list = vectors.tolist()
        rows = [
            {"domain_name": name, "source": source, "text": t, "embedding": v}
            for t, v in zip(texts, vec_list)
        ]
        
        for i in range(0, len(rows), 500):
            _sb().table("chunks").insert(rows[i : i + 500]).execute()
            
    return len(rows)


def delete_source(name: str, source: str) -> int:
    with _lock:
        # Supabase API trả về dữ liệu đã xoá trong res.data
        res = _sb().table("chunks").delete().eq("domain_name", name).eq("source", source).execute()
        return len(res.data)


def list_sources(name: str) -> list[dict]:
    # Lấy nhanh tất cả sources của domain rồi đếm (hoặc dùng RPC, nhưng ở đây đếm dict cho nhanh)
    res = _sb().table("chunks").select("source").eq("domain_name", name).execute()
    counts = {}
    for r in res.data:
        counts[r["source"]] = counts.get(r["source"], 0) + 1
    return [{"source": s, "chunks": n} for s, n in counts.items()]


def search(name: str, qvec, k: int, min_score: float) -> list[dict]:
    res = _sb().rpc(
        "match_chunks",
        {
            "query_embedding": qvec.tolist(),
            "match_domain": name,
            "match_count": k,
            "match_threshold": min_score,
        },
    ).execute()
    
    return [
        {"text": r["text"], "source": r["source"], "score": r["similarity"]}
        for r in res.data
    ]
