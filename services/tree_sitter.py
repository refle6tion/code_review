from dataclasses import dataclass

from utils.diff import ChangedFile, changed_new_lines


PYTHON_SYMBOL_NODES = {"class_definition", "function_definition"}
PYTHON_CONTROL_NODES = {"if_statement", "for_statement", "while_statement", "try_statement", "with_statement"}


@dataclass
class ChangedSymbol:
    file_path: str
    language: str
    symbol_type: str
    symbol_name: str | None
    start_line: int
    end_line: int
    changed_lines: list[int]
    control_context: list[str]


def extract_python_context(changed_file: ChangedFile, source: str) -> list[ChangedSymbol]:
    if changed_file.status == "deleted" or not _is_python_file(changed_file.new_path):
        return []

    changed_lines = changed_new_lines(changed_file)
    if not changed_lines:
        return []

    parser = _get_python_parser()
    tree = parser.parse(source)
    source_bytes = source.encode("utf-8")
    symbols_by_range: dict[tuple[str, int, int, str | None], ChangedSymbol] = {}

    for line_number in changed_lines:
        node = _named_descendant_for_line(_root_node(tree), line_number)
        if node is None:
            continue

        symbol_node = _closest_ancestor(node, PYTHON_SYMBOL_NODES)
        if symbol_node is None:
            continue

        symbol_name = _node_name(symbol_node, source_bytes)
        start_line = _point_row(_node_start_point(symbol_node)) + 1
        end_line = _point_row(_node_end_point(symbol_node)) + 1
        key = (_node_type(symbol_node), start_line, end_line, symbol_name)

        if key not in symbols_by_range:
            symbols_by_range[key] = ChangedSymbol(
                file_path=changed_file.new_path or "unknown",
                language="python",
                symbol_type=_symbol_type(_node_type(symbol_node)),
                symbol_name=symbol_name,
                start_line=start_line,
                end_line=end_line,
                changed_lines=[],
                control_context=_control_context(node),
            )

        symbols_by_range[key].changed_lines.append(line_number)

    return list(symbols_by_range.values())


def format_ast_context_for_prompt(symbols: list[ChangedSymbol]) -> str:
    if not symbols:
        return ""

    lines = ["Python AST context:"]
    for symbol in symbols:
        name = symbol.symbol_name or "<anonymous>"
        changed_lines = ", ".join(str(line) for line in sorted(set(symbol.changed_lines)))
        lines.append(
            f"- {symbol.file_path}: changed line(s) {changed_lines} are inside "
            f"{symbol.symbol_type} `{name}` (lines {symbol.start_line}-{symbol.end_line})"
        )
        if symbol.control_context:
            lines.append(f"  Control context: {', '.join(symbol.control_context)}")

    return "\n".join(lines)


def _get_python_parser():
    try:
        from tree_sitter_language_pack import get_parser
    except ImportError as exc:
        raise RuntimeError(
            "Python AST context requires `tree-sitter-language-pack`. "
            "Install it with `./.venv/Scripts/python.exe -m pip install tree-sitter-language-pack`."
        ) from exc

    return get_parser("python")


def _is_python_file(path: str | None) -> bool:
    return bool(path and path.endswith(".py"))


def _named_descendant_for_line(node, line_number: int):
    zero_based_line = line_number - 1
    if not (_point_row(_node_start_point(node)) <= zero_based_line <= _point_row(_node_end_point(node))):
        return None

    for child in _named_children(node):
        descendant = _named_descendant_for_line(child, line_number)
        if descendant is not None:
            return descendant

    return node


def _closest_ancestor(node, allowed_types: set[str]):
    current = node
    while current is not None:
        if _node_type(current) in allowed_types:
            return current
        current = _parent(current)
    return None


def _control_context(node) -> list[str]:
    context: list[str] = []
    current = _parent(node)
    while current is not None:
        node_type = _node_type(current)
        if node_type in PYTHON_CONTROL_NODES:
            context.append(node_type)
        current = _parent(current)
    return list(reversed(context))


def _node_name(node, source_bytes: bytes) -> str | None:
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return None
    return source_bytes[_node_start_byte(name_node):_node_end_byte(name_node)].decode("utf-8")


def _symbol_type(node_type: str) -> str:
    if node_type == "class_definition":
        return "class"
    return "function"


def _point_row(point) -> int:
    if callable(point):
        point = point()
    if hasattr(point, "row"):
        return point.row
    return point[0]


def _root_node(tree):
    return tree.root_node() if callable(tree.root_node) else tree.root_node


def _node_start_point(node):
    if hasattr(node, "start_point"):
        return node.start_point() if callable(node.start_point) else node.start_point
    return node.start_position() if callable(node.start_position) else node.start_position


def _node_end_point(node):
    if hasattr(node, "end_point"):
        return node.end_point() if callable(node.end_point) else node.end_point
    return node.end_position() if callable(node.end_position) else node.end_position


def _named_children(node):
    if hasattr(node, "named_children"):
        return node.named_children() if callable(node.named_children) else node.named_children
    count = node.named_child_count() if callable(node.named_child_count) else node.named_child_count
    return [node.named_child(index) for index in range(count)]


def _node_type(node) -> str:
    if hasattr(node, "type"):
        return node.type() if callable(node.type) else node.type
    return node.kind() if callable(node.kind) else node.kind


def _parent(node):
    return node.parent() if callable(node.parent) else node.parent


def _node_start_byte(node) -> int:
    return node.start_byte() if callable(node.start_byte) else node.start_byte


def _node_end_byte(node) -> int:
    return node.end_byte() if callable(node.end_byte) else node.end_byte
