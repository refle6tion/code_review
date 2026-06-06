# Local Server

Minimal FastAPI server with:

- `GET /health` (health check)
- `POST /webhook` (GitHub webhook receiver, intended for `pull_request` events)

## Prereqs

- A working virtualenv at `./.venv`
- Packages installed in the venv: `fastapi`, `uvicorn`

## Run Locally

PowerShell:

```powershell
./run.ps1
```

Or directly:

```powershell
./.venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Open:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`

## Endpoints

- `GET http://127.0.0.1:8000/health` -> `{ "status": "ok" }`
- `POST http://127.0.0.1:8000/webhook` -> `{ "ok": true }`

## GitHub Webhook Setup (Using ngrok)

GitHub can’t call `http://127.0.0.1:8000` directly. Use ngrok to temporarily expose your local server.

### 1) Start the server

Optional (recommended): if you set a webhook secret in GitHub, set the same secret locally before starting the server.

```powershell
$env:GITHUB_WEBHOOK_SECRET = "your-secret"
./run.ps1
```

If you did not set a secret in GitHub, do not set `GITHUB_WEBHOOK_SECRET`.

### 2) Start ngrok

In a separate terminal:

```powershell
ngrok http 8000
```

Copy the forwarding URL that looks like:

- `https://<something>.ngrok-free.dev`

### 3) Create a test GitHub repo

On GitHub: create a new repository (any name).

If the repo is empty, create an initial commit (for example add a `README.md`).

### 4) Add the webhook

Repo -> Settings -> Webhooks -> Add webhook:

- Payload URL: `https://<your-ngrok-domain>/webhook`
- Content type: `application/json`
- Secret: set one (recommended). If you do, it must match `GITHUB_WEBHOOK_SECRET` locally.
- Events: Let me select individual events -> check **Pull requests** only
- Active: checked

### 5) Trigger a pull request event

You need at least two branches with different commits.

From your repo folder:

```powershell
git checkout -b test-pr
"test" | Out-File -Encoding ascii test.txt
git add test.txt
git commit -m "Test PR"
git push -u origin test-pr
```

Then on GitHub:

- Pull requests -> New pull request -> base: `main`, compare: `test-pr` -> Create pull request

### 6) Verify delivery

- In GitHub: Settings -> Webhooks -> (your webhook) -> Recent Deliveries
  - Expect HTTP `200`
- In your server terminal: expect a log line like:
  - `github_webhook event='pull_request' action='opened' repo='owner/repo' pr_number=... pr_title=...`

## How `main.py` Works

- Creates a FastAPI app: `app = FastAPI(...)`
- `GET /health` returns a simple JSON body used for basic liveness checks.

### Webhook signature verification

- GitHub signs webhook payloads with `X-Hub-Signature-256` when you configure a webhook **secret**.
- If `GITHUB_WEBHOOK_SECRET` is set in your environment, the server will:
  1. Read the raw request bytes (`await request.body()`) because signatures must be computed on the raw body.
  2. Compute `HMAC-SHA256(secret, body)`.
  3. Compare it to the incoming `X-Hub-Signature-256` header using `hmac.compare_digest`.
  4. Reject with `401` if the header is missing/invalid.

### `POST /webhook`

- Reads and optionally verifies the signature.
- Parses JSON (`await request.json()`).
- Extracts a few fields (`action`, `repository.full_name`, `pull_request.number`, `pull_request.title`).
- Prints a compact summary to stdout.
- Returns `{ "ok": true }` quickly so GitHub doesn’t time out.
