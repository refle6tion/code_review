import logging
import os

from models.chunks import CodeChunk
from utils.chunker import (
    LANGUAGE_MAP,
    chunk_generic_file,
    chunk_with_treesitter,
    detect_language,
    should_skip_file,
)

logger = logging.getLogger(__name__)


def crawl_repository(repo_path: str) -> list[CodeChunk]:
    chunks: list[CodeChunk] = []
    files_processed = 0
    files_skipped = 0

    for dirpath, _dirnames, filenames in os.walk(repo_path):
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            relative_path = os.path.relpath(file_path, repo_path)

            if should_skip_file(relative_path):
                logger.debug("Skipping %s", relative_path)
                files_skipped += 1
                continue

            try:
                if os.path.getsize(file_path) > 100 * 1024:
                    logger.debug("Skipping %s", relative_path)
                    files_skipped += 1
                    continue
            except OSError:
                logger.debug("Skipping %s", relative_path)
                files_skipped += 1
                continue

            language = detect_language(file_path)
            if language is None:
                continue

            if language in LANGUAGE_MAP:
                try:
                    with open(file_path, "r", encoding="utf-8", newline="") as f:
                        source = f.read()
                except Exception:
                    logger.warning("Cannot read %s", file_path, exc_info=True)
                    files_skipped += 1
                    continue
                file_chunks = chunk_with_treesitter(source, relative_path, language)
            else:
                file_chunks = chunk_generic_file(file_path, relative_path, language)

            chunks.extend(file_chunks)
            files_processed += 1

    logger.info(
        "Crawl complete: %d files processed, %d skipped, %d chunks produced",
        files_processed,
        files_skipped,
        len(chunks),
    )
    return chunks


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    chunks = crawl_repository(path)
    for chunk in chunks[:10]:
        print(
            f"{chunk.file_path} | {chunk.chunk_type} | {chunk.name or '—'} | "
            f"lines {chunk.start_line}-{chunk.end_line} | {len(chunk.text)} chars"
        )
    print(f"\nTotal chunks: {len(chunks)}")
