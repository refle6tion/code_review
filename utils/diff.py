def clean_diff(raw_diff: str) -> str:
    cleaned_lines: list[str] = []

    for line in raw_diff.splitlines():
        if line.startswith("index "):
            continue
        if line.startswith(("+++", "---", "@@", "+", "-", "diff --git", " ")):
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)
