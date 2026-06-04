# AI code review bot - local webhook server

Day 2 setup for a FastAPI pipeline that handles GitHub webhooks. It checks signatures, pulls PR diffs, and cleans up the output.

## Project structure
- `main.py`: app setup and routing
- `routes/webhook.py`: the main webhook logic
- `services/github.py`: signature checks and fetching diffs
- `models/events.py`: data models for PR events
- `utils/diff.py`: diff cleanup logic
- `.env`: secrets and tokens

## Prereqs
- Python venv at `./.venv`
- Installed: `fastapi`, `uvicorn`, `httpx`, `python-dotenv`

If you're missing anything, run:
```powershell
./.venv/Scripts/python.exe -m pip install httpx python-dotenv
```

## Environment variables
Put these in a `.env` file in the root:
```env
WEBHOOK_SECRET=your_secret
GITHUB_TOKEN=your_token
```
`WEBHOOK_SECRET` must match your GitHub settings. `GITHUB_TOKEN` lets the app download the diffs.

## Run it
```powershell
./run.ps1
```
Or manually:
```powershell
./.venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

## Endpoints
- `GET /health`: simple status check
- `POST /webhook`: handles incoming PR events

## GitHub webhook setup (ngrok)
Since your server is local, you need ngrok to expose it.

1. Start the server (`./run.ps1`)
2. Start ngrok: `ngrok http 8000`
3. Copy the URL (like `https://xxxx.ngrok-free.dev`)
4. In GitHub (Repo -> Settings -> Webhooks):
   - **Payload URL**: your-ngrok-url/webhook
   - **Content type**: application/json
   - **Secret**: same as your `.env`
   - **Events**: Pull requests only

## How the webhook works
The `POST /webhook` route follows these steps:
1. Reads the raw body to check the signature.
2. Logs the incoming request.
3. Checks the signature against your secret.
4. Ignores any action that isn't `opened` or `synchronize`.
5. Downloads the PR diff from GitHub.
6. Cleans up the diff (removes git metadata) and logs it.

## Common issues
- **400 Invalid signature**: your secrets don't match.
- **500 errors**: check your `.env` file.
- **502 errors**: usually a bad GitHub token or URL.
- **ngrok 404**: check your Payload URL path (it must end in `/webhook`).
