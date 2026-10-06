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
        raise HTTPException(500, "Hệ thống đang bận, vui lòng thử lại sau.")


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


class DomainUpdate(BaseModel):
    display_name: str | None = None
    persona: str | None = None
    greeting: str | None = None
    fallback: str | None = None


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
    n = ingest.ingest_file(name, file.filename or "upload", data)
    return {"source": file.filename, "chunks": n}


@app.post("/api/domains/{name}/text", dependencies=[Depends(admin)])
def add_text(name: str, body: TextIn):
    return {"chunks": ingest.ingest_text(name, body.source, body.text)}


@app.delete("/api/domains/{name}/sources/{source:path}", dependencies=[Depends(admin)])
def delete_source(name: str, source: str):
    return {"removed": store.delete_source(name, source)}


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
