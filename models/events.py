from pydantic import BaseModel


class PREvent(BaseModel):
    repo: str
    pr_number: int
    diff_url: str
    title: str
    body: str = ""
    sha: str
    action: str
