import hmac
import logging

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel, Field

from . import agent, config, ingest, store

log = logging.getLogger("agent")
app = FastAPI(title="AI Auto-Reply Agent")
app.add_middleware(
    CORSMiddleware, allow_origins=config.ALLOWED_ORIGINS, allow_methods=["*"], allow_headers=["*"]
)
STATIC = config.BASE_DIR / "static"


def admin(x_admin_key: str = Header(default="")):
    if not config.ADMIN_KEY or not hmac.compare_digest(x_admin_key, config.ADMIN_KEY):
        raise HTTPException(401, "Sai hoặc chưa cấu hình ADMIN_KEY")


@app.exception_handler(Exception)
async def _global_error(request: Request, exc: Exception):
    import traceback
    return JSONResponse({"detail": f"Server Error: {traceback.format_exc()}"}, status_code=500)

@app.exception_handler(store.DomainError)
async def _domain_error(request: Request, exc: store.DomainError):
    from fastapi.responses import JSONResponse

    return JSONResponse({"detail": str(exc)}, status_code=400)


# ---------- Công khai: chat widget gọi vào đây ----------
class ChatIn(BaseModel):
    domain: str
    session_id: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=2000)


@app.post("/api/chat")
def chat(body: ChatIn):
    try:
        return agent.reply(body.domain, body.session_id, body.message)
    except store.DomainError:
        raise
    except Exception:
        log.exception("chat failed")
        raise HTTPException(500, "Hệ thống đang bận, vui lòng thử lại sau ít phút.")

@app.post("/api/chat/stream")
def chat_stream(body: ChatIn):
    try:
        from fastapi.responses import StreamingResponse
        headers = {
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
        return StreamingResponse(
            agent.reply_stream(body.domain, body.session_id, body.message), 
            media_type="text/plain",
            headers=headers
        )
    except store.DomainError:
        raise
    except Exception:
        log.exception("chat failed")
        raise HTTPException(500, "Hệ thống đang bận, vui lòng thử lại sau ít phút.")

@app.get("/api/debug_ai")
def debug_ai():
    try:
        from app import llm
        vec = llm.embed_query("test")
        out = ""
        for c in llm.generate_stream("system", [], "hello", 50):
            out += c
        return {"ok": True, "vec_len": len(vec), "out": out}
    except Exception as e:
        import traceback
        return {"ok": False, "error": str(e), "trace": traceback.format_exc()}


@app.get("/api/domains/{name}/public")
def public_info(name: str):
    cfg = store.get_config(name)
    return {"display_name": cfg["display_name"] or name, "greeting": cfg["greeting"]}


# ---------- Quản trị: nạp kiến thức, cấu hình ----------
class DomainIn(BaseModel):
    name: str
    display_name: str | None = None
    persona: str | None = None
    greeting: str | None = None
    fallback: str | None = None
    timeout: int | None = None
    max_tokens: int | None = None
    fb_page_token: str | None = None


class DomainUpdate(BaseModel):
    display_name: str | None = None
    persona: str | None = None
    greeting: str | None = None
    fallback: str | None = None
    timeout: int | None = None
    max_tokens: int | None = None
    fb_page_token: str | None = None


class TextIn(BaseModel):
    source: str = "ghi-chu"
    text: str


@app.get("/api/domains", dependencies=[Depends(admin)])
def domains():
    return store.list_domains()


@app.post("/api/domains", dependencies=[Depends(admin)])
def create_domain(body: DomainIn):
    return store.create_domain(body.name, **body.model_dump(exclude={"name"}))


@app.get("/api/domains/{name}", dependencies=[Depends(admin)])
def domain_detail(name: str):
    return {"config": store.get_config(name), "sources": store.list_sources(name)}


@app.put("/api/domains/{name}", dependencies=[Depends(admin)])
def update_domain(name: str, body: DomainUpdate):
    return store.save_config(name, body.model_dump())


@app.delete("/api/domains/{name}", dependencies=[Depends(admin)])
def delete_domain(name: str):
    store.delete_domain(name)
    return {"ok": True}


@app.post("/api/domains/{name}/upload", dependencies=[Depends(admin)])
async def upload(name: str, file: UploadFile = File(...)):
    store.get_config(name)
    data = await file.read()
    try:
        n = ingest.ingest_file(name, file.filename or "upload", data)
    except Exception as e:
        if "429" in str(e) or "quota" in str(e).lower() or "exhausted" in str(e).lower():
            raise HTTPException(status_code=429, detail="Hệ thống nhúng tài liệu (Gemini) đang bị quá tải hoặc hết hạn mức. Vui lòng thử lại sau 1-2 phút hoặc nâng cấp tài khoản Gemini.")
        raise HTTPException(status_code=500, detail=f"Lỗi khi xử lý file: {str(e)}")
    return {"source": file.filename, "chunks": n}


@app.post("/api/domains/{name}/text", dependencies=[Depends(admin)])
def add_text(name: str, body: TextIn):
    return {"chunks": ingest.ingest_text(name, body.source, body.text)}


@app.delete("/api/domains/{name}/sources/{source:path}", dependencies=[Depends(admin)])
def delete_source(name: str, source: str):
    return {"removed": store.delete_source(name, source)}

class TokenIn(BaseModel):
    amount: int

@app.post("/api/domains/{name}/tokens", dependencies=[Depends(admin)])
def add_tokens(name: str, body: TokenIn):
    new_balance = store.add_tokens(name, body.amount)
    return {"tokens": new_balance}

@app.get("/api/domains/{name}/knowledge", dependencies=[Depends(admin)])
def get_main_knowledge(name: str):
    return {"text": store.get_main_knowledge(name)}

class KnowledgeIn(BaseModel):
    text: str

@app.put("/api/domains/{name}/knowledge", dependencies=[Depends(admin)])
def set_main_knowledge(name: str, body: KnowledgeIn):
    # First delete existing main knowledge
    store.delete_source(name, "main-knowledge")
    # Add new if not empty
    chunks = 0
    if body.text.strip():
        try:
            chunks = ingest.ingest_text(name, "main-knowledge", body.text)
        except Exception as e:
            if any(k in str(e).lower() for k in ["429", "quota", "exhausted", "timeout"]):
                raise HTTPException(status_code=429, detail="API nhúng tài liệu (Google Gemini) đang quá tải, hết hạn mức hoặc bị treo (Timeout). Vui lòng nâng cấp tài khoản hoặc thử lại sau.")
            raise HTTPException(status_code=500, detail=f"Lỗi khi huấn luyện: {str(e)}")
    return {"chunks": chunks, "ok": True}


# ---------- Giao diện ----------
@app.get("/")
def index():
    return RedirectResponse("/admin")


@app.get("/static/{filename}")
def serve_static(filename: str):
    path = STATIC / filename
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path)

@app.get("/admin")
def admin_page():
    return FileResponse(STATIC / "admin.html")


@app.get("/demo")
def demo_page():
    return FileResponse(STATIC / "demo.html")
import urllib.request
import json
import os
from fastapi import BackgroundTasks

FB_VERIFY_TOKEN = os.getenv("FB_VERIFY_TOKEN", "123456789")
FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN", "")

def send_fb_message(domain: str, sender_id: str, text: str):
    cfg = store.get_config(domain)
    # Uu tin l?y Token ri?ng c?a domain, n?u khng c thi l?y bi?n m?i tru?ng chung
    domain_token = cfg.get("fb_page_token", "")
    token_to_use = domain_token if domain_token else FB_PAGE_ACCESS_TOKEN
    
    if not token_to_use:
        print(f"Thi?u Token truy c?p Fanpage cho domain {domain}")
        return
        
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={token_to_use}"
    headers = {"Content-Type": "application/json"}
    data = {
        "recipient": {"id": sender_id},
        "message": {"text": text}
    }
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req) as response:
            pass
    except Exception as e:
        print(f"L?i g?i tin nh?n FB: {e}")

def process_fb_message(domain: str, sender_id: str, message: str):
    try:
        res = agent.reply(domain, "fb_" + sender_id, message)
        answer = res.get("answer", "Xin l?i, h? th?ng dang b?n.")
        send_fb_message(domain, sender_id, answer)
    except Exception as e:
        print("L?i x? ly FB message:", e)

@app.get("/api/webhook/facebook/{domain}")
def fb_webhook_verify(domain: str, request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    
    if mode == "subscribe" and token == FB_VERIFY_TOKEN:
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(content=challenge)
    raise HTTPException(status_code=403, detail="Invalid verification token")

@app.post("/api/webhook/facebook/{domain}")
async def fb_webhook_receive(domain: str, request: Request, background_tasks: BackgroundTasks):
    body = await request.json()
    if body.get("object") == "page":
        for entry in body.get("entry", []):
            for event in entry.get("messaging", []):
                sender_id = event.get("sender", {}).get("id")
                message = event.get("message", {}).get("text")
                if sender_id and message:
                    background_tasks.add_task(process_fb_message, domain, sender_id, message)
        return "EVENT_RECEIVED"
    raise HTTPException(status_code=404)
@app.get("/api/debug/spss_check")
def debug_spss():
    try:
        domains = store.list_domains()
        names = [d["name"] for d in domains]
        return {"names": names}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/debug/all_domains")
def debug_all():
    try:
        domains = store.list_domains()
        return {"names": [d["name"] for d in domains], "configs": [store.get_config(d["name"]) for d in domains]}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/domains/{domain}/history")
def get_history(domain: str, limit: int = 50, _=Depends(admin)):
    try:
        return store.get_chat_history(domain, limit)
    except Exception as e:
        raise HTTPException(500, str(e))
