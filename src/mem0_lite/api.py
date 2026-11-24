"""Optional localhost API. Add authentication before network exposure."""
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .memory import ConsentRequiredError, MemoryStore, UnsafeMemoryError

app = FastAPI(title="Mem0 Lite", version="0.1.0")
_store = MemoryStore(os.getenv("MEM0_LITE_DB_PATH", "mem0-lite.sqlite3"))


class ConsentRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    granted: bool


class MemoryRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    content: str = Field(min_length=1, max_length=2000)
    category: str = Field(default="general", max_length=64)
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)


@app.get("/health")
def health():
    return {"service": "mem0-lite", "status": "ok", "storage": "sqlite", "consent_required": True}


@app.post("/v1/consent")
def consent(request: ConsentRequest):
    if request.granted:
        _store.grant_consent(request.user_id)
    else:
        _store.revoke_consent(request.user_id, delete_existing=True)
    return {"user_id": request.user_id, "granted": request.granted}


@app.post("/v1/memories")
def create_memory(request: MemoryRequest):
    try:
        memory_id = _store.remember(
            request.user_id, request.content, request.category, request.expires_in_days
        )
        return {"id": memory_id, "saved": True}
    except ConsentRequiredError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except UnsafeMemoryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/v1/memories/search")
def search_memories(user_id: str, q: str = "", limit: int = 10):
    return {"items": _store.search(user_id, q, limit)}


@app.delete("/v1/memories/{memory_id}")
def delete_memory(memory_id: int, user_id: str):
    return {"deleted": _store.forget(user_id, memory_id)}


@app.delete("/v1/memories")
def delete_all(user_id: str):
    return {"deleted_count": _store.forget_all(user_id)}
