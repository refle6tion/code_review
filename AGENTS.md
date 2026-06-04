# Agent notes

## Scope and entry points
- FastAPI app entrypoint is `main.py`.
- Health route is in `main.py` (`GET /health`).
- Webhook logic is in `routes/webhook.py` (`POST /webhook`).

## Day 2 webhook pipeline
- We read the raw request body (`await request.body()`) before parsing JSON to validate the signature.
- Signature checks happen in `services/github.py::validate_signature` using the `X-Hub-Signature-256` header.
- We only care about `opened` and `synchronize` PR actions; anything else gets ignored.
- The PR diff is fetched asynchronously with `httpx` in `services/github.py::fetch_pr_diff`.
- `utils/diff.py::clean_diff` strips out the git metadata we don't need.

## Required environment
- `.env` is loaded in `routes/webhook.py`.
- You need `WEBHOOK_SECRET` and `GITHUB_TOKEN`.
- Heads up: keep `.env` values in `KEY=value` format. Avoid extra spaces around the equals sign.

## Run and verify
- Start it: `./run.ps1`
- Or manually: `./.venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload`
- Health check: `http://127.0.0.1:8000/health`
- Syntax check: `./.venv/Scripts/python.exe -m py_compile main.py routes/webhook.py services/github.py models/events.py utils/diff.py`

## Webhook testing
- Use ngrok to expose localhost: `ngrok http 8000`.
- Your GitHub webhook URL should be the current ngrok domain plus `/webhook`.
- If you restart ngrok, you'll need to update that URL on GitHub.

## Change management
- Prepend a new entry to `CHANGELOG.md` after any real change (features, fixes, refactors).
- If there's no `CHANGELOG.md`, create one.
- Keep the format consistent:

---
## [YYYY-MM-DD] — <short title>

**What changed:**
- <specific file/function and change>

**Functionality impact:**
<1-3 sentences on what this means for the user>

**How to run / test:**
<copy-pasteable commands>
---
