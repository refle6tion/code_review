import hashlib
import hmac

import httpx


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
