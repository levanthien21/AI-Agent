import re

def _chunk_text(text: str, max_words: int = 400, overlap: int = 50) -> list[str]:
    """Smart chunking that respects paragraphs and sentences."""
    # Split by double newline (paragraphs)
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    
    chunks = []
    current_chunk = []
    current_len = 0
    
    for p in paragraphs:
        p_words = p.split()
        p_len = len(p_words)
        
        # If a single paragraph is too long, split it by sentences (approx)
        if p_len > max_words:
            sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', p) if s.strip()]
            for s in sentences:
                s_words = s.split()
                s_len = len(s_words)
                
                if current_len + s_len > max_words and current_chunk:
                    chunks.append(" ".join(current_chunk))
                    # Keep overlap
                    overlap_words = current_chunk[-overlap:] if overlap > 0 else []
                    current_chunk = overlap_words + s_words
                    current_len = len(current_chunk)
                else:
                    current_chunk.extend(s_words)
                    current_len += s_len
        else:
            if current_len + p_len > max_words and current_chunk:
                chunks.append(" ".join(current_chunk))
                overlap_words = current_chunk[-overlap:] if overlap > 0 else []
                current_chunk = overlap_words + p_words
                current_len = len(current_chunk)
            else:
                current_chunk.extend(p_words)
                current_len += p_len
                
    if current_chunk:
        chunks.append(" ".join(current_chunk))
        
    return chunks

import tempfile
from . import llm, store

def ingest_text(domain: str, source_name: str, text: str) -> int:
    chunks = _chunk_text(text)
    if not chunks:
        return 0
    vecs = llm.embed(chunks, task_type="RETRIEVAL_DOCUMENT")
    store.save_chunks(domain, source_name, chunks, vecs)
    return len(chunks)

def ingest_file(domain: str, filename: str, data: bytes) -> int:
    ext = filename.split(".")[-1].lower()
    text = ""
    if ext in ("txt", "md", "csv"):
        text = data.decode("utf-8", errors="ignore")
    elif ext == "pdf":
        import PyPDF2
        import io
        reader = PyPDF2.PdfReader(io.BytesIO(data))
        text = "\n".join(p.extract_text() for p in reader.pages if p.extract_text())
    elif ext == "docx":
        import docx
        import io
        doc = docx.Document(io.BytesIO(data))
        text = "\n".join(p.text for p in doc.paragraphs)
    else:
        text = data.decode("utf-8", errors="ignore")
    
    if not text.strip():
        return 0
    return ingest_text(domain, filename, text)
