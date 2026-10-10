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


from firebase_admin import auth

def admin(x_admin_key: str = Header(default=""), authorization: str = Header(default="")):
    store.db() # <-- Đảm bảo Firebase đã được khởi tạo
    uid = None
    auth_err = None
    if authorization and authorization.startswith("Bearer "): 
        token = authorization.split("Bearer ")[1]
        try:
            decoded = auth.verify_id_token(token)
            return decoded["uid"]
        except Exception as e:
            auth_err = str(e)
            
    if config.ADMIN_KEY and hmac.compare_digest(x_admin_key, config.ADMIN_KEY):
        return None
        
    if auth_err:
        raise HTTPException(status_code=401, detail=f"Firebase Auth Error: {auth_err}")
    raise HTTPException(status_code=401, detail="Unauthorized")
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


@app.get("/api/domains")
def domains(uid: str = Depends(admin)):
    return store.list_domains(uid)


@app.post("/api/domains")
def create_domain(body: DomainIn, uid: str = Depends(admin)):
    return store.create_domain(body.name, owner_uid=uid, **body.model_dump(exclude={"name"}))


@app.get("/api/domains/{name}")
def domain_detail(name: str, uid: str = Depends(admin)):
    return {"config": store.get_config(name), "sources": store.list_sources(name)}


@app.put("/api/domains/{name}")
def update_domain(name: str, body: DomainUpdate, uid: str = Depends(admin)):
    return store.save_config(name, body.model_dump())


@app.delete("/api/domains/{name}")
def delete_domain(name: str, uid: str = Depends(admin)):
    store.delete_domain(name)
    return {"ok": True}


@app.post("/api/domains/{name}/upload")
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


@app.post("/api/domains/{name}/text")
def add_text(name: str, body: TextIn, uid: str = Depends(admin)):
    return {"chunks": ingest.ingest_text(name, body.source, body.text)}


@app.delete("/api/domains/{name}/sources/{source:path}")
def delete_source(name: str, source: str, uid: str = Depends(admin)):
    return {"removed": store.delete_source(name, source)}

class TokenIn(BaseModel):
    amount: int

@app.post("/api/domains/{name}/tokens")
def add_tokens(name: str, body: TokenIn, uid: str = Depends(admin)):
    new_balance = store.add_tokens(name, body.amount)
    return {"tokens": new_balance}

@app.get("/api/domains/{name}/knowledge")
def get_main_knowledge(name: str, uid: str = Depends(admin)):
    return {"text": store.get_main_knowledge(name)}

class KnowledgeIn(BaseModel):
    text: str

@app.put("/api/domains/{name}/knowledge")
def set_main_knowledge(name: str, body: KnowledgeIn, uid: str = Depends(admin)):
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

@app.get("/saas")
def saas_page():
    return FileResponse(STATIC / "saas.html")

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

def send_telegram_message(domain: str, chat_id: str, text: str):
    cfg = store.get_config(domain)
    token = cfg.get("telegram_token")
    if not token: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={"Content-Type": "application/json"}, method='POST')
    try:
        with urllib.request.urlopen(req): pass
    except Exception as e:
        print(f"Lỗi gửi Telegram: {e}")

def process_telegram_message(domain: str, chat_id: str, message: str):
    try:
        store.save_chat_history(domain, "tg_" + chat_id, message, "", 0, source="telegram", debug_log="Đã nhận tin nhắn Telegram")
        res = agent.reply(domain, "tg_" + chat_id, message)
        if res.get("paused"): return
        answer = res.get("answer", "Xin lỗi, hệ thống đang bận.")
        send_telegram_message(domain, chat_id, answer)
    except Exception as e:
        print("Lỗi Telegram processing:", e)

def send_zalo_message(domain: str, user_id: str, text: str):
    cfg = store.get_config(domain)
    token = cfg.get("zalo_oa_token")
    if not token: return
    url = "https://openapi.zalo.me/v3.0/oa/message/cs"
    headers = {"Content-Type": "application/json", "access_token": token}
    data = {"recipient": {"user_id": user_id}, "message": {"text": text}}
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req): pass
    except Exception as e:
        print(f"Lỗi gửi Zalo: {e}")

def process_zalo_message(domain: str, user_id: str, message: str):
    try:
        store.save_chat_history(domain, "zl_" + user_id, message, "", 0, source="zalo", debug_log="Đã nhận tin nhắn Zalo")
        res = agent.reply(domain, "zl_" + user_id, message)
        if res.get("paused"): return
        answer = res.get("answer", "Xin lỗi, hệ thống đang bận.")
        send_zalo_message(domain, user_id, answer)
    except Exception as e:
        print("Lỗi Zalo processing:", e)

def process_fb_message(domain: str, sender_id: str, message_data):
    try:
        res = agent.reply(domain, "fb_" + sender_id, message_data)
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
                msg_obj = event.get("message", {})
                text_content = msg_obj.get("text", "")
                
                attachments = msg_obj.get("attachments", [])
                image_urls = []
                has_sticker = False
                
                for att in attachments:
                    if att.get("type") == "image":
                        payload = att.get("payload", {})
                        if "sticker_id" in payload:
                            has_sticker = True
                        elif "url" in payload:
                            image_urls.append(payload["url"])
                
                if not text_content and not image_urls and not has_sticker:
                    continue
                    
                if has_sticker and not text_content and not image_urls:
                    text_content = "[Khách gửi một Sticker/Icon]"
                
                if sender_id:
                    background_tasks.add_task(process_fb_message, domain, sender_id, {"text": text_content, "images": image_urls})
        return "EVENT_RECEIVED"
    raise HTTPException(status_code=404)

class AdminMessage(BaseModel):
    text: str

@app.post("/api/domains/{name}/sessions/{session_id}/pause")
def toggle_pause_session(name: str, session_id: str, body: dict, uid: str = Depends(admin)):
    cfg = store.get_config(name)
    paused_sessions = cfg.get("paused_sessions", [])
    
    should_pause = body.get("paused", True)
    if should_pause and session_id not in paused_sessions:
        paused_sessions.append(session_id)
    elif not should_pause and session_id in paused_sessions:
        paused_sessions.remove(session_id)
        
    store.update_config(name, {"paused_sessions": paused_sessions})
    return {"paused": should_pause}

@app.post("/api/domains/{name}/sessions/{session_id}/send")
def admin_send_message(name: str, session_id: str, body: AdminMessage, uid: str = Depends(admin)):
    # 1. Send to correct channel
    if session_id.startswith("fb_"):
        send_fb_message(name, session_id.replace("fb_", ""), body.text)
    elif session_id.startswith("tg_"):
        send_telegram_message(name, session_id.replace("tg_", ""), body.text)
    elif session_id.startswith("zl_"):
        send_zalo_message(name, session_id.replace("zl_", ""), body.text)
        
    # 2. Save to history (mark source as admin)
    store.save_chat_history(name, session_id, "", body.text, 0, source="admin", debug_log="Nhân viên tư vấn (Admin) gửi tin nhắn")
    
    return {"ok": True}


@app.post("/api/webhook/telegram/{domain}")
async def telegram_webhook(domain: str, request: Request, background_tasks: BackgroundTasks):
    try:
        body = await request.json()
        if "message" in body:
            chat_id = str(body["message"]["chat"]["id"])
            text = body["message"].get("text", "")
            if text:
                background_tasks.add_task(process_telegram_message, domain, chat_id, text)
        return {"ok": True}
    except Exception:
        return {"ok": False}

@app.post("/api/webhook/zalo/{domain}")
async def zalo_webhook(domain: str, request: Request, background_tasks: BackgroundTasks):
    try:
        body = await request.json()
        event_name = body.get("event_name")
        if event_name == "user_send_text":
            user_id = body.get("sender", {}).get("id")
            text = body.get("message", {}).get("text", "")
            if user_id and text:
                background_tasks.add_task(process_zalo_message, domain, user_id, text)
        return {"ok": True}
    except Exception:
        return {"ok": False}


class WidgetChat(BaseModel):
    session_id: str
    message: str

@app.post("/api/widget/{domain}/chat")
def widget_chat(domain: str, body: WidgetChat, background_tasks: BackgroundTasks):
    try:
        res = agent.reply(domain, body.session_id, body.message)
        if res.get("paused"):
            return {"answer": "Hệ thống đang chuyển kết nối đến nhân viên hỗ trợ. Vui lòng đợi trong giây lát..."}
        
        return {"answer": res.get("answer", "Xin lỗi, hệ thống đang bận.")}
    except Exception as e:
        return {"answer": f"Lỗi hệ thống: {e}"}


class ChannelToken(BaseModel):
    token: str

@app.post("/api/domains/{name}/channels/telegram")
def connect_telegram(name: str, body: ChannelToken, request: Request, uid: str = Depends(admin)):
    token = body.token.strip()
    if not token:
        store.get_config(name) # Check if domain exists
        cfg = store.get_config(name)
        cfg["telegram_token"] = ""
        store.db().collection("domains").document(name).update({"config": cfg})
        return {"ok": True, "msg": "Đã ngắt kết nối"}
        
    webhook_url = f"https://{request.url.netloc}/api/webhook/telegram/{name}"
    # Auto set webhook
    try:
        url = f"https://api.telegram.org/bot{token}/setWebhook?url={webhook_url}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as res:
            data = json.loads(res.read())
            if not data.get("ok"):
                raise Exception(data.get("description"))
    except Exception as e:
        raise HTTPException(400, f"Token không hợp lệ hoặc lỗi Telegram: {e}")
        
    cfg = store.get_config(name)
    cfg["telegram_token"] = token
    store.db().collection("domains").document(name).update({"config": cfg})
    return {"ok": True}

@app.post("/api/domains/{name}/channels/facebook")
def connect_facebook(name: str, body: ChannelToken, uid: str = Depends(admin)):
    token = body.token.strip()
    cfg = store.get_config(name)
    cfg["fb_page_token"] = token
    store.db().collection("domains").document(name).update({"config": cfg})
    return {"ok": True}

@app.post("/api/domains/{name}/channels/zalo")
def connect_zalo(name: str, body: ChannelToken, uid: str = Depends(admin)):
    token = body.token.strip()
    cfg = store.get_config(name)
    cfg["zalo_oa_token"] = token
    store.db().collection("domains").document(name).update({"config": cfg})
    return {"ok": True}

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
def get_history(domain: str, limit: int = 50, uid: str = Depends(admin)):
    try:
        return store.get_chat_history(domain, limit)
    except Exception as e:
        raise HTTPException(500, str(e))
