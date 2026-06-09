import hashlib
import hmac
import httpx
import google.generativeai as genai
from urllib.parse import quote


def validate_signature(raw_body: bytes, secret: str, signature_header: str) -> bool:
    if not signature_header.startswith("sha256="):
        return False

    expected = hmac.new(
        secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    received = signature_header.split("=", 1)[1]
    return hmac.compare_digest(expected, received)


async def fetch_pr_diff(diff_url: str, github_token: str) -> str:
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3.diff",
    }

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(diff_url, headers=headers)

    if response.status_code != 200:
        raise ValueError(f"Failed to fetch diff: status={response.status_code} url={diff_url}")

    return response.text


async def fetch_file_content(repo: str, file_path: str, ref: str, github_token: str) -> str | None:
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.raw+json",
    }
    encoded_path = quote(file_path, safe="/")
    content_url = f"https://api.github.com/repos/{repo}/contents/{encoded_path}?ref={ref}"

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(content_url, headers=headers)

    if response.status_code == 404:
        return None

    if response.status_code != 200:
        raise ValueError(
            f"Failed to fetch file content: status={response.status_code} repo={repo} path={file_path} ref={ref}"
        )

    return response.text


async def post_review_comment(repo: str, pr_number: int, review_text: str, github_token: str) -> None:
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
    }
    comment_url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.post(comment_url, headers=headers, json={"body": review_text})

    if response.status_code != 201:
        raise ValueError(
            f"Failed to post review comment: status={response.status_code} repo={repo} pr={pr_number}"
        )
