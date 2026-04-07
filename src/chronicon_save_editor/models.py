from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RawValueSpan:
    key: str
    token_start: int
    token_end: int
    value_start: int
    value_end: int
    string_content_start: int | None = None
    string_content_end: int | None = None

    @property
    def is_string(self) -> bool:
        return self.string_content_start is not None and self.string_content_end is not None


@dataclass(frozen=True)
class SectionMapping:
    key: str
    label: str
    description: str
    confidence: str = "unknown"


@dataclass(frozen=True)
class CommunityMap:
    sections: dict[str, SectionMapping] = field(default_factory=dict)
    fields: dict[str, Any] = field(default_factory=dict)
    affixes: dict[str, Any] = field(default_factory=dict)


@dataclass
class SaveEntry:
    key: str
    raw_value: Any
    span: RawValueSpan
    kind: str
    decoded_bytes: bytes | None = None
    mapping: SectionMapping | None = None
    notes: list[str] = field(default_factory=list)
    printable_strings: list[str] = field(default_factory=list)

    @property
    def size_text(self) -> str:
        if self.kind == "hex_section" and self.decoded_bytes is not None:
            return f"{len(self.decoded_bytes)} bytes"
        if isinstance(self.raw_value, str):
            return f"{len(self.raw_value)} chars"
        return type(self.raw_value).__name__


@dataclass
class SaveContainer:
    source_path: Path
    raw_text: str
    decoded_json: dict[str, Any]
    entries: list[SaveEntry]
    community_map: CommunityMap

    @property
    def entry_count(self) -> int:
        return len(self.entries)

    @property
    def hex_section_count(self) -> int:
        return sum(1 for entry in self.entries if entry.kind == "hex_section")

    @property
    def primitive_count(self) -> int:
        return self.entry_count - self.hex_section_count

    def entry_by_key(self, key: str) -> SaveEntry | None:
        for entry in self.entries:
            if entry.key == key:
                return entry
        return None


@dataclass(frozen=True)
class BackupRecord:
    source_path: Path
    backup_path: Path

