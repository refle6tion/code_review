import re
from dataclasses import dataclass, field


@dataclass
class DiffLine:
    kind: str
    content: str
    old_line: int | None
    new_line: int | None


@dataclass
class DiffHunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    header: str
    lines: list[DiffLine] = field(default_factory=list)


@dataclass
class ChangedFile:
    old_path: str | None
    new_path: str | None
    status: str
    hunks: list[DiffHunk] = field(default_factory=list)


HUNK_HEADER_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def parse_diff(raw_diff: str) -> list[ChangedFile]:
    files: list[ChangedFile] = []
    current_file: ChangedFile | None = None
    current_hunk: DiffHunk | None = None
    old_line_number = 0
    new_line_number = 0

    for line in raw_diff.splitlines():
        if line.startswith("diff --git "):
            current_file = _parse_file_header(line)
            current_hunk = None
            files.append(current_file)
            continue

        if current_file is None:
            continue

        if line.startswith("new file mode "):
            current_file.status = "added"
            continue

        if line.startswith("deleted file mode "):
            current_file.status = "deleted"
            continue

        if line.startswith("rename from "):
            current_file.status = "renamed"
            current_file.old_path = line.removeprefix("rename from ")
            continue

        if line.startswith("rename to "):
            current_file.status = "renamed"
            current_file.new_path = line.removeprefix("rename to ")
            continue

        if line.startswith("--- "):
            path = _parse_marker_path(line, "--- ")
            if path is None:
                current_file.status = "added"
            else:
                current_file.old_path = path
            continue

        if line.startswith("+++ "):
            path = _parse_marker_path(line, "+++ ")
            if path is None:
                current_file.status = "deleted"
            else:
                current_file.new_path = path
            continue

        hunk_match = HUNK_HEADER_RE.match(line)
        if hunk_match:
            old_start = int(hunk_match.group(1))
            old_count = int(hunk_match.group(2) or "1")
            new_start = int(hunk_match.group(3))
            new_count = int(hunk_match.group(4) or "1")
            current_hunk = DiffHunk(
                old_start=old_start,
                old_count=old_count,
                new_start=new_start,
                new_count=new_count,
                header=line,
            )
            current_file.hunks.append(current_hunk)
            old_line_number = old_start
            new_line_number = new_start
            continue

        if current_hunk is None or line.startswith("\\ No newline at end of file"):
            continue

        if line.startswith("+"):
            current_hunk.lines.append(DiffLine("added", line[1:], None, new_line_number))
            new_line_number += 1
        elif line.startswith("-"):
            current_hunk.lines.append(DiffLine("removed", line[1:], old_line_number, None))
            old_line_number += 1
        elif line.startswith(" "):
            current_hunk.lines.append(DiffLine("context", line[1:], old_line_number, new_line_number))
            old_line_number += 1
            new_line_number += 1

    return files


def format_diff_for_prompt(changed_files: list[ChangedFile]) -> str:
    sections: list[str] = []

    for changed_file in changed_files:
        path = changed_file.new_path or changed_file.old_path or "unknown"
        sections.append(f"File: {path}")
        sections.append(f"Status: {changed_file.status}")

        for hunk in changed_file.hunks:
            sections.append(hunk.header)
            for diff_line in hunk.lines:
                prefix = _line_prefix(diff_line.kind)
                line_number = diff_line.new_line if diff_line.new_line is not None else diff_line.old_line
                sections.append(f"{prefix}{line_number}: {diff_line.content}")

        sections.append("")

    return "\n".join(sections).strip()


def clean_diff(raw_diff: str) -> str:
    return format_diff_for_prompt(parse_diff(raw_diff))


def changed_new_lines(changed_file: ChangedFile) -> list[int]:
    lines: list[int] = []
    for hunk in changed_file.hunks:
        for diff_line in hunk.lines:
            if diff_line.kind == "added" and diff_line.new_line is not None:
                lines.append(diff_line.new_line)
    return lines


def _parse_file_header(line: str) -> ChangedFile:
    parts = line.split()
    old_path = _strip_git_prefix(parts[2]) if len(parts) > 2 else None
    new_path = _strip_git_prefix(parts[3]) if len(parts) > 3 else None
    return ChangedFile(old_path=old_path, new_path=new_path, status="modified")


def _parse_marker_path(line: str, marker: str) -> str | None:
    path = line.removeprefix(marker).split("\t", 1)[0]
    if path == "/dev/null":
        return None
    return _strip_git_prefix(path)


def _strip_git_prefix(path: str) -> str:
    if path.startswith(("a/", "b/")):
        return path[2:]
    return path


def _line_prefix(kind: str) -> str:
    if kind == "added":
        return "+"
    if kind == "removed":
        return "-"
    return " "
