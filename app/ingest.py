"""Biến file Excel/CSV/TXT/MD thành các đoạn kiến thức."""
import csv
import io
import re

import openpyxl

from . import llm, store

MAX_CHARS = 900

def _rows_to_chunks(rows: list[dict], sheet: str | None = None) -> list[str]:
    out = []
    for row in rows:
        parts = [
            f"{str(col).strip()}: {str(val).strip()}"
            for col, val in row.items()
            if val is not None and str(val).strip()
        ]
        if parts:
            prefix = f"[{sheet}] " if sheet else ""
            out.append(prefix + " | ".join(parts))
    return out

def _text_to_chunks(text: str) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks, buf = [], ""
    for p in paragraphs:
        while len(p) > MAX_CHARS:
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
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("cp1258", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        return _rows_to_chunks(list(reader))
        
    if ext in ("xlsx", "xls"):
        wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
        multi = len(wb.sheetnames) > 1
        chunks = []
        for name in wb.sheetnames:
            sheet = wb[name]
            rows = list(sheet.iter_rows(values_only=True))
            if not rows or not rows[0]:
                continue
            headers = [str(h).strip() if h is not None else f"Col{i}" for i, h in enumerate(rows[0])]
            dict_rows = []
            for row in rows[1:]:
                if not any(row): continue
                dict_rows.append({headers[i]: v for i, v in enumerate(row)})
            chunks.extend(_rows_to_chunks(dict_rows, name if multi else None))
        return chunks
        
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
    texts = _text_to_chunks(text)
    if not texts:
        raise store.DomainError("Nội dung trống")
    return store.add_chunks(domain, source, texts, llm.embed(texts))
