from typing import Literal

from pydantic import BaseModel


class CodeChunk(BaseModel):
    text: str
    file_path: str
    chunk_type: Literal["function", "class", "method", "block"]
    language: str
    start_line: int
    end_line: int
    name: str | None = None
