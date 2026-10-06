"""Biến file Excel/CSV/TXT/MD thành các đoạn kiến thức."""
import io
import re

import pandas as pd

from . import llm, store

MAX_CHARS = 900


def _rows_to_chunks(df: pd.DataFrame, sheet: str | None = None) -> list[str]:
    df = df.dropna(how="all")
    out = []
    for _, row in df.iterrows():
        parts = [
            f"{str(col).strip()}: {str(val).strip()}"
            for col, val in row.items()
            if pd.notna(val) and str(val).strip()
        ]
        if parts:
            prefix = f"[{sheet}] " if sheet else ""
            out.append(prefix + " | ".join(parts))
    return out


def _text_to_chunks(text: str) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks, buf = [], ""
    for p in paragraphs:
        while len(p) > MAX_CHARS:  # đoạn quá dài: cắt theo câu
            cut = p.rfind(". ", 0, MAX_CHARS)
            cut = cut + 1 if cut > 200 else MAX_CHARS
            if buf:
                chunks.append(buf)
                buf = ""
            chunks.append(p[:cut].strip())
            p = p[cut:].strip()
        if len(buf) + len(p) + 2 > MAX_CHARS and buf:
            chunks.append(buf)
            buf = ""
        buf = f"{buf}\n\n{p}".strip()
    if buf:
        chunks.append(buf)
    return chunks


def parse(filename: str, data: bytes) -> list[str]:
    ext = filename.lower().rsplit(".", 1)[-1]
    if ext == "csv":
        try:
            df = pd.read_csv(io.BytesIO(data), encoding="utf-8-sig", dtype=str)
        except UnicodeDecodeError:
            df = pd.read_csv(io.BytesIO(data), encoding="cp1258", dtype=str)
        return _rows_to_chunks(df)
    if ext in ("xlsx", "xls"):
        sheets = pd.read_excel(io.BytesIO(data), sheet_name=None, dtype=str)
        multi = len(sheets) > 1
        return [c for name, df in sheets.items() for c in _rows_to_chunks(df, name if multi else None)]
    if ext in ("txt", "md"):
        return _text_to_chunks(data.decode("utf-8-sig", errors="replace"))
    raise store.DomainError("Chỉ hỗ trợ file .csv, .xlsx, .xls, .txt, .md")


def ingest_file(domain: str, filename: str, data: bytes) -> int:
    texts = parse(filename, data)
    if not texts:
        raise store.DomainError("File không có dữ liệu")
    vectors = llm.embed(texts)
    return store.add_chunks(domain, filename, texts, vectors)


def ingest_text(domain: str, source: str, text: str) -> int:
    """Nạp nhanh một đoạn kiến thức gõ tay (ví dụ một cặp hỏi - đáp)."""
    texts = _text_to_chunks(text)
    if not texts:
        raise store.DomainError("Nội dung trống")
    return store.add_chunks(domain, source, texts, llm.embed(texts))
