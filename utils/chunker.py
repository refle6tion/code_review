import logging
import os
from pathlib import Path

from tree_sitter import Language, Parser

from models.chunks import CodeChunk

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tree-sitter language map — graceful fallback on missing bindings
# ---------------------------------------------------------------------------

LANGUAGE_MAP: dict[str, Language] = {}

try:
    import tree_sitter_python as ts_python
    LANGUAGE_MAP["python"] = Language(ts_python.language())
except ImportError:
    logger.warning("tree-sitter-python not installed — Python parsing disabled")

try:
    import tree_sitter_javascript as ts_javascript
    LANGUAGE_MAP["javascript"] = Language(ts_javascript.language())
except ImportError:
    logger.warning("tree-sitter-javascript not installed — JavaScript parsing disabled")

try:
    import tree_sitter_typescript as ts_typescript
    LANGUAGE_MAP["typescript"] = Language(ts_typescript.language_typescript())
except ImportError:
    logger.warning("tree-sitter-typescript not installed — TypeScript parsing disabled")

try:
    import tree_sitter_go as ts_go
    LANGUAGE_MAP["go"] = Language(ts_go.language())
except ImportError:
    logger.warning("tree-sitter-go not installed — Go parsing disabled")

try:
    import tree_sitter_java as ts_java
    LANGUAGE_MAP["java"] = Language(ts_java.language())
except ImportError:
    logger.warning("tree-sitter-java not installed — Java parsing disabled")

try:
    import tree_sitter_ruby as ts_ruby
    LANGUAGE_MAP["ruby"] = Language(ts_ruby.language())
except ImportError:
    logger.warning("tree-sitter-ruby not installed — Ruby parsing disabled")

try:
    import tree_sitter_rust as ts_rust
    LANGUAGE_MAP["rust"] = Language(ts_rust.language())
except ImportError:
    logger.warning("tree-sitter-rust not installed — Rust parsing disabled")

# ---------------------------------------------------------------------------
# Node types to extract per language
# ---------------------------------------------------------------------------

LANGUAGE_NODE_TYPES: dict[str, list[str]] = {
    "python": ["function_definition", "class_definition"],
    "javascript": [
        "function_declaration",
        "arrow_function",
        "class_declaration",
        "method_definition",
    ],
    "typescript": [
        "function_declaration",
        "arrow_function",
        "class_declaration",
        "method_definition",
        "interface_declaration",
    ],
    "go": ["function_declaration", "method_declaration", "type_declaration"],
    "java": ["method_declaration", "class_declaration", "interface_declaration"],
    "ruby": ["method", "class", "module"],
    "rust": ["function_item", "impl_item", "struct_item", "trait_item"],
}


# ---------------------------------------------------------------------------
# Tree-sitter chunker
# ---------------------------------------------------------------------------

def chunk_with_treesitter(
    source: str, relative_path: str, language: str
) -> list[CodeChunk]:
    if language not in LANGUAGE_MAP:
        logger.warning("Language '%s' not in LANGUAGE_MAP — skipping %s", language, relative_path)
        return []

    try:
        lang_obj = LANGUAGE_MAP[language]
        parser = Parser()
        try:
            parser.language = lang_obj
        except AttributeError:
            parser.set_language(lang_obj)
        source_bytes = source.encode("utf-8")
        tree = parser.parse(source_bytes)

        node_types = LANGUAGE_NODE_TYPES.get(language, [])
        chunks: list[CodeChunk] = []

        def _classify(node_type: str) -> str:
            if any(k in node_type for k in ("function", "method", "arrow")):
                return "function"
            if any(k in node_type for k in ("class", "interface", "impl", "struct", "trait", "module")):
                return "class"
            return "block"

        def _extract_name(node) -> str | None:
            for child in node.children:
                if child.type == "identifier":
                    return source_bytes[child.start_byte : child.end_byte].decode("utf-8")
            return None

        def visit(node):
            if node.type in node_types:
                text = source_bytes[node.start_byte : node.end_byte].decode("utf-8")
                chunk_type = _classify(node.type)
                name = _extract_name(node)
                chunks.append(
                    CodeChunk(
                        text=text,
                        file_path=relative_path,
                        chunk_type=chunk_type,
                        language=language,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        name=name,
                    )
                )
                return  # do NOT recurse into matched nodes
            for child in node.children:
                visit(child)

        visit(tree.root_node)
        return chunks

    except Exception:
        logger.warning("Tree-sitter parse failed for %s — falling back", relative_path, exc_info=True)
        return []


# ---------------------------------------------------------------------------
# Generic file chunker (markdown, yaml, json, toml, fallback)
# ---------------------------------------------------------------------------

def chunk_generic_file(
    file_path: str, relative_path: str, language: str
) -> list[CodeChunk]:
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace", newline="") as f:
            text = f.read()
    except Exception:
        logger.warning("Cannot read %s", file_path, exc_info=True)
        return []

    if text == "":
        return []

    lines = text.splitlines(keepends=True)
    chunk_size = 40
    overlap = 10
    step = chunk_size - overlap
    chunks: list[CodeChunk] = []

    for i in range(0, len(lines), step):
        chunk_lines = lines[i : i + chunk_size]
        start_line = i + 1
        end_line = start_line + len(chunk_lines) - 1
        chunks.append(
            CodeChunk(
                text="".join(chunk_lines),
                file_path=relative_path,
                chunk_type="block",
                language=language,
                start_line=start_line,
                end_line=end_line,
                name=None,
            )
        )

    return chunks


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

_EXT_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".go": "go",
    ".java": "java",
    ".rb": "ruby",
    ".rs": "rust",
    ".md": "markdown",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".json": "json",
    ".toml": "toml",
}


def detect_language(file_path: str) -> str | None:
    ext = Path(file_path).suffix.lower()
    return _EXT_MAP.get(ext)


# ---------------------------------------------------------------------------
# Noise filter
# ---------------------------------------------------------------------------

_SKIP_FILENAMES: set[str] = {
    "package-lock.json",
    "yarn.lock",
    "poetry.lock",
    "Pipfile.lock",
    "composer.lock",
    "Gemfile.lock",
    ".DS_Store",
}

_SKIP_EXTENSIONS: set[str] = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".pdf", ".zip", ".tar", ".gz", ".exe", ".bin", ".wasm",
}

_SKIP_PATH_FRAGMENTS: tuple[str, ...] = (
    "node_modules/",
    ".git/",
    "__pycache__/",
    ".pytest_cache/",
    "dist/",
    "build/",
    ".venv/",
    "venv/",
)

_MAX_FILE_SIZE = 100 * 1024  # 100 KB


def should_skip_file(file_path: str) -> bool:
    name = Path(file_path).name
    if name in _SKIP_FILENAMES:
        return True

    ext = Path(file_path).suffix.lower()
    if ext in _SKIP_EXTENSIONS:
        return True

    normalized = file_path.replace("\\", "/")
    for frag in _SKIP_PATH_FRAGMENTS:
        if frag in normalized:
            return True

    try:
        if os.path.getsize(file_path) > _MAX_FILE_SIZE:
            return True
    except OSError:
        return False

    return False
