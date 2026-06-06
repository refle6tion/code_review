import logging
import os
import re
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = (
    """Act as a senior engineer doing a pull request review. 
    Flag only genuine issues: bugs, security vulnerabilities, unhandled edge cases, performance problems, unclear logic. 
    Ignore style and formatting unless it seriously impacts readability. 
    Be direct and specific - state the problem, why it matters, a better approach. 
    Respond in plain markdown: short summary at top, numbered list of issues below. 
    If no real issues exist, say so briefly. "
    Base your response only on the provided code. Do not extrapolate beyond what is shown."""
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
                max_output_tokens=1024,
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