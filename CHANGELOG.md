## [2026-06-07] — Fix webhook timeout by moving review to background task

**What changed:**
- Moved slow processing (diff fetch, LLM call, comment post) from the request handler into a `BackgroundTask` function `routes/webhook.py::run_review`.
- Added `BackgroundTasks` parameter to `webhook_handler` so the function returns `200 OK` immediately after validation, before the review pipeline runs.
- Errors in the background task are now logged instead of raising `HTTPException` (since the response has already been sent).

**Functionality impact:**
GitHub webhooks were timing out (~30s) because the handler waited for the LLM and GitHub API calls before responding. Now the handler acknowledges the event within milliseconds, while the review pipeline runs asynchronously behind the scenes and still posts the comment to the PR.

**How to run / test:**
```powershell
./.venv/Scripts/python.exe -m py_compile main.py routes/webhook.py services/github.py services/llm.py models/events.py utils/diff.py
./run.ps1
# Push a commit or open a PR — the webhook should return 200 instantly,
# and the review comment will appear on the PR after a few seconds.
```

## [2026-06-07] — Fix truncated Gemini reviews caused by thinking tokens

**What changed:**
- Updated `services/llm.py::get_code_review` to disable Gemini 2.5 Flash thinking (`thinking_config=types.ThinkingConfig(thinking_budget=0)`) and raise `max_output_tokens` from 1024 to 8192.
- Added finish-reason logging in `services/llm.py` so future `MAX_TOKENS` truncations are visible in the server log.

**Functionality impact:**
Gemini 2.5 Flash's default "thinking" mode was consuming the entire `max_output_tokens=1024` budget, causing reviews to be cut off after roughly the first issue (e.g. only "1. Hardcoded Credentials..." was posted). Disabling thinking frees the full token budget for the actual review text, and bumping the cap gives the model headroom for long diffs. The full numbered list of issues will now reach the PR comment.

**How to run / test:**
```powershell
./.venv/Scripts/python.exe -m py_compile main.py routes/webhook.py services/github.py services/llm.py models/events.py utils/diff.py
./run.ps1
# Push a new commit to the test PR; the review comment should now include all numbered issues,
# and the log should show "llm_finish_reason=FinishReason.STOP" (not MAX_TOKENS).
```

## [2026-06-04] — Add Gemini-based PR review generation

**What changed:**
- Added `services/llm.py::get_code_review` to generate structured PR reviews with the `google-generativeai` SDK and `gemini-2.0-flash`.
- Updated `routes/webhook.py` to send cleaned diffs to Gemini, log review generation details, and post the returned review back to the PR.
- Added `services/github.py::post_review_comment` to publish review output as a GitHub pull request comment.

**Functionality impact:**
Webhook processing now continues past diff cleaning into AI review generation and posts the resulting review text back onto the pull request. Empty cleaned diffs still avoid an unnecessary model call and return a fallback review message.

**How to run / test:**
```powershell
./.venv/Scripts/python.exe -m pip install google-generativeai
./.venv/Scripts/python.exe -m py_compile main.py routes/webhook.py services/github.py services/llm.py models/events.py utils/diff.py
./run.ps1
```

## [2026-06-03] — Enable redirect following for diff fetching

**What changed:**
- Updated `services/github.py::fetch_pr_diff` to use `follow_redirects=True` in the `httpx.AsyncClient`.

**Functionality impact:**
Fixed a `502 Bad Gateway` error that occurred during `synchronize` events. The server can now correctly follow GitHub's internal redirects when fetching pull request diffs.

**How to run / test:**
1. Push a new commit to an existing Pull Request (triggering a `synchronize` event).
2. Check server logs for `diff_fetched` and the cleaned diff output.

## [2026-06-02] — Fix server hang and add logging

**What changed:**
- Identified and killed hung python processes blocking port 8000.
- Added basic logging configuration to `main.py` to ensure log output is visible.
- Verified local connectivity via fresh test on alternative port.

**Functionality impact:**
Resolved the "timed out" error caused by a hung server process. Logs will now correctly appear in the terminal when requests are received.

**How to run / test:**
```powershell
./run.ps1
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health"
```

## [2026-06-02] — Add agent workflow guidance

**What changed:**
- Added `AGENTS.md` at repo root with verified entrypoints, Day 2 webhook pipeline details, environment requirements, run/verify commands, and ngrok webhook testing notes.
- Added a mandatory change-management rule in `AGENTS.md` requiring prepended `CHANGELOG.md` entries for significant behavior changes.

**Functionality impact:**
Future agent sessions now have a concise, repo-specific operating guide, which reduces setup mistakes and preserves the expected webhook implementation flow. This improves consistency of edits and validation steps across sessions.

**How to run / test:**
```powershell
Get-Content .\AGENTS.md
./.venv/Scripts/python.exe -m py_compile main.py routes/webhook.py services/github.py models/events.py utils/diff.py
```
