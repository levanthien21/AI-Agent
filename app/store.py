"""Kho kiến thức theo lĩnh vực (domain). Mỗi domain là một thư mục độc lập:

data/domains/<name>/config.json   - persona, lời chào, câu trả lời dự phòng
data/domains/<name>/chunks.json   - các đoạn kiến thức [{id, text, source}]
data/domains/<name>/vectors.npy   - embedding tương ứng
"""
import json
import re
import shutil
import threading
import uuid

import numpy as np

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


def _dir(name: str):
    if not _NAME_RE.match(name):
        raise DomainError("Tên lĩnh vực chỉ gồm a-z, 0-9, '-' hoặc '_' (tối đa 40 ký tự)")
    return config.DATA_DIR / name


def exists(name: str) -> bool:
    return _dir(name).is_dir()


def list_domains() -> list[dict]:
    result = []
    for d in sorted(p for p in config.DATA_DIR.iterdir() if p.is_dir()):
        chunks = _load_chunks(d.name)
        result.append(
            {
                "name": d.name,
                "display_name": get_config(d.name).get("display_name") or d.name,
                "chunks": len(chunks),
                "sources": len({c["source"] for c in chunks}),
            }
        )
    return result


def create_domain(name: str, **cfg) -> dict:
    d = _dir(name)
    if d.exists():
        raise DomainError("Lĩnh vực đã tồn tại")
    d.mkdir(parents=True)
    return save_config(name, cfg)


def delete_domain(name: str) -> None:
    d = _dir(name)
    if not d.exists():
        raise DomainError("Không tìm thấy lĩnh vực")
    shutil.rmtree(d)


def get_config(name: str) -> dict:
    d = _dir(name)
    if not d.is_dir():
        raise DomainError("Không tìm thấy lĩnh vực")
    path = d / "config.json"
    cfg = dict(DEFAULT_CONFIG)
    if path.exists():
        cfg.update(json.loads(path.read_text(encoding="utf-8")))
    return cfg


def save_config(name: str, updates: dict) -> dict:
    cfg = get_config(name) if (_dir(name) / "config.json").exists() else dict(DEFAULT_CONFIG)
    cfg.update({k: v for k, v in updates.items() if k in DEFAULT_CONFIG and v is not None})
    (_dir(name) / "config.json").write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return cfg


def _load_chunks(name: str) -> list[dict]:
    p = _dir(name) / "chunks.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def _load_vectors(name: str) -> np.ndarray:
    p = _dir(name) / "vectors.npy"
    return np.load(p) if p.exists() else np.zeros((0, config.EMBED_DIM), dtype=np.float32)


def _save(name: str, chunks: list[dict], vectors: np.ndarray) -> None:
    d = _dir(name)
    (d / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
    np.save(d / "vectors.npy", vectors)


def add_chunks(name: str, source: str, texts: list[str], vectors: np.ndarray) -> int:
    """Thêm kiến thức; nạp lại cùng tên file sẽ thay thế bản cũ."""
    with _lock:
        if not exists(name):
            raise DomainError("Không tìm thấy lĩnh vực")
        chunks, vecs = _load_chunks(name), _load_vectors(name)
        keep = [i for i, c in enumerate(chunks) if c["source"] != source]
        chunks = [chunks[i] for i in keep]
        vecs = vecs[keep] if keep else vecs[:0]
        chunks += [{"id": uuid.uuid4().hex[:8], "text": t, "source": source} for t in texts]
        _save(name, chunks, np.vstack([vecs, vectors]))
    return len(texts)


def delete_source(name: str, source: str) -> int:
    with _lock:
        chunks, vecs = _load_chunks(name), _load_vectors(name)
        keep = [i for i, c in enumerate(chunks) if c["source"] != source]
        removed = len(chunks) - len(keep)
        _save(name, [chunks[i] for i in keep], vecs[keep] if keep else vecs[:0])
    return removed


def list_sources(name: str) -> list[dict]:
    counts: dict[str, int] = {}
    for c in _load_chunks(name):
        counts[c["source"]] = counts.get(c["source"], 0) + 1
    return [{"source": s, "chunks": n} for s, n in counts.items()]


def search(name: str, qvec: np.ndarray, k: int, min_score: float) -> list[dict]:
    chunks, vecs = _load_chunks(name), _load_vectors(name)
    if not chunks:
        return []
    scores = vecs @ qvec
    order = np.argsort(-scores)[:k]
    return [
        {**chunks[i], "score": float(scores[i])} for i in order if scores[i] >= min_score
    ]
