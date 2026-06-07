import json
import logging
import os

from dotenv import load_dotenv
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from models.events import PREvent
from services.github import fetch_pr_diff, post_review_comment, validate_signature
from services.llm import get_code_review
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


async def run_review(pr_event: PREvent, github_token: str) -> None:
    """Background task: fetch diff, run LLM review, post comment."""
    try:
        raw_diff = await fetch_pr_diff(diff_url=pr_event.diff_url, github_token=github_token)
        _log("diff_fetched", chars=len(raw_diff), pr=pr_event.pr_number)

        cleaned_diff = clean_diff(raw_diff)
        _log("review_requested", pr=pr_event.pr_number, diff_chars=len(cleaned_diff))

        if not cleaned_diff.strip():
            _log("review_skipped", pr=pr_event.pr_number, reason="empty_cleaned_diff")
            return

        review_text = get_code_review(cleaned_diff, pr_event.title, pr_event.body)
        _log("review_generated", pr=pr_event.pr_number, review_chars=len(review_text))

        await post_review_comment(pr_event.repo, pr_event.pr_number, review_text, github_token)
    except Exception as exc:
        _log("error", reason="review_background_failed", error=str(exc), pr=pr_event.pr_number)


@router.post("/webhook")
async def webhook_handler(
    request: Request,
    background_tasks: BackgroundTasks,
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

    background_tasks.add_task(run_review, pr_event, github_token)
    _log("review_dispatched", pr=pr_event.pr_number)
    return {"status": "ok", "pr": pr_event.pr_number}
