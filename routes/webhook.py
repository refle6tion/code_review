import json
import logging
import os

from dotenv import load_dotenv
from fastapi import APIRouter, Header, HTTPException, Request

from models.events import PREvent
from services.github import fetch_pr_diff, validate_signature
from utils.diff import clean_diff

load_dotenv()

logger = logging.getLogger(__name__)
router = APIRouter()


def _log(event: str, **data: object) -> None:
    logger.info(json.dumps({"event": event, **data}, default=str))


def parse_pr_event(payload: dict) -> PREvent:
    pull_request = payload["pull_request"]
    repository = payload["repository"]
    head = pull_request["head"]
    return PREvent(
        repo=repository["full_name"],
        pr_number=pull_request["number"],
        diff_url=pull_request["diff_url"],
        title=pull_request["title"],
        body=pull_request.get("body") or "",
        sha=head["sha"],
        action=payload["action"],
    )


@router.post("/webhook")
async def webhook_handler(
    request: Request,
    x_hub_signature_256: str = Header(default="", alias="X-Hub-Signature-256"),
) -> dict:
    raw_body = await request.body()
    _log("webhook_received", content_length=len(raw_body))

    webhook_secret = os.getenv("WEBHOOK_SECRET", "")
    github_token = os.getenv("GITHUB_TOKEN", "")

    if not webhook_secret:
        _log("error", reason="missing_webhook_secret")
        raise HTTPException(status_code=500, detail="WEBHOOK_SECRET is not configured")

    if not github_token:
        _log("error", reason="missing_github_token")
        raise HTTPException(status_code=500, detail="GITHUB_TOKEN is not configured")

    if not validate_signature(raw_body=raw_body, secret=webhook_secret, signature_header=x_hub_signature_256):
        _log("error", reason="invalid_signature")
        raise HTTPException(status_code=400, detail="Invalid signature")

    payload = json.loads(raw_body)
    action = payload.get("action", "")

    if action not in ["opened", "synchronize"]:
        _log("event_ignored", action=action, reason="action_not_handled")
        return {"status": "ignored", "reason": "action not handled"}

    try:
        pr_event = parse_pr_event(payload)
    except Exception as exc:
        _log("error", reason="payload_parse_failed", error=str(exc))
        raise HTTPException(status_code=400, detail="Invalid pull request payload")

    try:
        raw_diff = await fetch_pr_diff(diff_url=pr_event.diff_url, github_token=github_token)
    except ValueError as exc:
        _log("error", reason="diff_fetch_failed", error=str(exc), diff_url=pr_event.diff_url)
        raise HTTPException(status_code=502, detail=str(exc))

    _log("diff_fetched", chars=len(raw_diff), pr=pr_event.pr_number)

    cleaned_diff = clean_diff(raw_diff)
    logger.info(cleaned_diff)

    return {"status": "ok", "pr": pr_event.pr_number}
