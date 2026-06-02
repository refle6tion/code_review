import hmac
import hashlib
import os

from fastapi import FastAPI, Header, HTTPException, Request

app = FastAPI(title="Local Health Server")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


def _verify_github_signature(secret: str, body: bytes, signature_header: str | None) -> None:
    """Verify GitHub webhook signature (X-Hub-Signature-256).

    GitHub sends: `X-Hub-Signature-256: sha256=<hex>`
    """

    if not signature_header:
        raise HTTPException(status_code=401, detail="Missing X-Hub-Signature-256")

    if not signature_header.startswith("sha256="):
        raise HTTPException(status_code=401, detail="Invalid X-Hub-Signature-256 format")

    sent = signature_header.split("=", 1)[1]
    mac = hmac.new(secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256)
    expected = mac.hexdigest()

    if not hmac.compare_digest(sent, expected):
        raise HTTPException(status_code=401, detail="Invalid signature")


@app.post("/webhook")
async def github_webhook(
    request: Request,
    x_github_event: str | None = Header(default=None, alias="X-GitHub-Event"),
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
) -> dict:
    body = await request.body()

    # Optional: set this to the same value you configured in GitHub webhook settings.
    # PowerShell:
    #   $env:GITHUB_WEBHOOK_SECRET = "your-secret"
    secret = os.getenv("GITHUB_WEBHOOK_SECRET")
    if secret:
        _verify_github_signature(secret=secret, body=body, signature_header=x_hub_signature_256)

    payload = await request.json()

    # We keep this minimal: log a compact summary and return 200 quickly.
    action = payload.get("action")
    pr = payload.get("pull_request") or {}
    pr_number = pr.get("number")
    pr_title = pr.get("title")
    repo = (payload.get("repository") or {}).get("full_name")

    print(
        f"github_webhook event={x_github_event!r} action={action!r} repo={repo!r} "
        f"pr_number={pr_number!r} pr_title={pr_title!r}"
    )

    return {"ok": True}
