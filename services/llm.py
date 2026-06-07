import logging
import os
import re
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = (
    """You are a senior software engineer performing a pull request review.

Your input is a raw git diff. Review only what is shown in the diff — added lines (+), removed lines (-), and their surrounding context. Do not make assumptions about code that is not present.

Flag only genuine issues in these categories:
- Bugs and incorrect logic
- Security vulnerabilities (injection, auth bypass, secrets in code, unsafe deserialization, etc.)
- Unhandled edge cases (null inputs, empty collections, race conditions, boundary values)
- Performance problems with measurable impact (N+1 queries, unbounded loops, unnecessary allocations)
- Logic that is unclear enough to cause future misreads or bugs

Ignore style, formatting, naming conventions, and minor readability preferences unless they create an actual correctness or maintenance risk.

Classify every issue as one of two levels:
- 🔴 BLOCKER — must be fixed before merge (bug, security flaw, data loss risk)
- 🟡 WARNING — real issue worth fixing, but does not block merge

For each issue state:
1. File and line number (from the diff)
2. What the problem is
3. Why it matters
4. A concrete fix or better approach

Be concise. Prioritise signal over completeness — if the diff is large, cover the highest-severity issues first and cut lower-priority ones before exceeding the limit.

Output format (strict):

**Summary**
One to two sentences maximum. What this diff does, and your overall assessment.

**Blockers**
Numbered list. Each item: two to three sentences max. If none, write: No blockers found.

**Warnings**
Numbered list. Each item: two to three sentences max. If none, write: No warnings found.

If the diff contains no real issues at any level, respond with:

> ✅ No issues found. This diff looks good to merge.

Followed by a **Changes** section: a plain-English description of what was added, removed, or modified and its apparent purpose. 3 to 5 sentences max. No bullet points. Write it as if briefing a teammate who hasn't seen the diff.

Do not add preamble, sign-off, praise, or suggestions outside the categories above."""
)

#genai.configure(api_key=os.environ["GEMINI_API_KEY"])
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

REVIEW_FORMAT_PATTERN = re.compile(r"^[^\n]+\n(?:\n)?1\. ", re.MULTILINE)


def get_code_review(diff: str, pr_title: str, pr_body: str) -> str:
    if not diff.strip():
        return "No reviewable code changes found."

    review_diff = diff
    if len(review_diff) > 32000:
        review_diff = review_diff[:32000] + "\n[Note: diff was truncated due to length]"

    prompt = (
        f"PR title: {pr_title}\n"
        f"PR description: {pr_body}\n\n"
        f"Changed code:\n{review_diff}\n\n"
        "These are changes made to the codebase. Please review them and provide feedback on any potential issues or improvements that could be made."
    )
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                max_output_tokens=8192,
                temperature=0.1
            ),
        )
        review_text = response.text
        print(review_text)
        
    except Exception as exc:
        logger.exception("Gemini review generation failed")
        raise RuntimeError(f"LLM review failed: {exc}") from exc

    # if not REVIEW_FORMAT_PATTERN.match(review_text):
    #     return review_text

    return review_text



# MODEL = genai.GenerativeModel(
#     model_name="gemini-2.0-flash",
#     system_instruction=SYSTEM_INSTRUCTION,
#     generation_config={"max_output_tokens": 1024, "temperature": 0.2},
# )