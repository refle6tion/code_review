import subprocess

from utils.diff import parse_diff
from services.tree_sitter import extract_python_context, format_ast_context_for_prompt


def main() -> None:
    result = subprocess.run(
        ["git", "diff"],
        capture_output=True,
        text=True,
        check=True,
    )

    raw_diff = result.stdout
    if not raw_diff.strip():
        print("No local changes found.")
        return

    files = parse_diff(raw_diff)

    print("=== Parsed Diff ===")
    for file in files:
        print(f"\nFILE: {file.new_path or file.old_path}")
        print(f"STATUS: {file.status}")

        for hunk in file.hunks:
            print(f"  HUNK: {hunk.header}")

            for line in hunk.lines:
                print(
                    f"    {line.kind.upper():7} "
                    f"old={line.old_line} "
                    f"new={line.new_line} "
                    f"content={line.content}"
                )

    print("\n=== Python AST Context ===")
    for file in files:
        path = file.new_path
        if not path or not path.endswith(".py") or file.status == "deleted":
            continue

        try:
            with open(path, "r", encoding="utf-8") as source_file:
                source = source_file.read()
        except FileNotFoundError:
            continue

        symbols = extract_python_context(file, source)
        context = format_ast_context_for_prompt(symbols)

        if context:
            print()
            print(context)


if __name__ == "__main__":
    main()