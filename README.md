# Mem0 Lite

A local-first, consent-gated memory store for BILLI R-20. Uses Python's built-in SQLite; no hosted DB, embedding service or API key required.

## Privacy and safety
- Writes are blocked until explicit user consent is granted.
- No automatic conversation capture: the host must call `remember()` deliberately.
- Revoking consent deletes that user's saved memories by default.
- Credential-like text and payment-card-shaped numbers are rejected.
- User-scoped search, individual deletion, forget-all and optional expiry.
- Protect the SQLite file and its backups. Avoid storing sensitive personal data.

## Install
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
```

## Library
```python
from mem0_lite import MemoryStore
with MemoryStore("billi-memory.sqlite3") as memory:
    memory.grant_consent("local-user")
    memory.remember("local-user", "Prefers answers in Tamil", category="preference")
    print(memory.search("local-user", "Tamil"))
    memory.forget_all("local-user")
```

## Optional API
```bash
uvicorn mem0_lite.api:app --host 127.0.0.1 --port 8782
```
- `GET /health`
- `POST /v1/consent` body: `{"user_id":"local-user","granted":true}`
- `POST /v1/memories` body: `{"user_id":"local-user","content":"...","category":"preference"}`
- `GET /v1/memories/search?user_id=local-user&q=Tamil`
- `DELETE /v1/memories/{memory_id}?user_id=local-user`
- `DELETE /v1/memories?user_id=local-user`

The API has no built-in authentication and is for localhost/private-network use. Add authentication, TLS, rate limits and per-user authorization before exposing it publicly.

## Tests
```bash
pytest
```
