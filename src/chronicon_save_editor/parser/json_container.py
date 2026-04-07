from __future__ import annotations

import binascii
import json
import string
from pathlib import Path

from chronicon_save_editor.models import RawValueSpan, SaveContainer, SaveEntry
from chronicon_save_editor.parser.community_map import load_community_map


class SaveFormatError(ValueError):
    """Raised when a save file does not match the expected JSON container shape."""


def load_save_container(path: Path) -> SaveContainer:
    raw_text = path.read_text(encoding="utf-8")
    return parse_save_text(raw_text=raw_text, source_path=path)


def parse_save_text(raw_text: str, source_path: Path | None = None) -> SaveContainer:
    try:
        decoded_json = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise SaveFormatError(f"Save file is not valid JSON: {exc}") from exc

    if not isinstance(decoded_json, dict):
        raise SaveFormatError("Top-level save container must be a JSON object.")

    spans = _index_top_level_entries(raw_text)
    community_map = load_community_map()

    entries: list[SaveEntry] = []
    for key, raw_value in decoded_json.items():
        span = spans.get(key)
        if span is None:
            raise SaveFormatError(f"Could not locate raw JSON span for top-level key '{key}'.")

        mapping = community_map.sections.get(key)
        entry = SaveEntry(
            key=key,
            raw_value=raw_value,
            span=span,
            kind="primitive",
            decoded_bytes=None,
            mapping=mapping,
        )

        if isinstance(raw_value, str) and _is_hex_string(raw_value):
            try:
                decoded_bytes = binascii.unhexlify(raw_value)
            except binascii.Error as exc:
                raise SaveFormatError(f"Key '{key}' looks like hex but failed to decode.") from exc

            entry.kind = "hex_section"
            entry.decoded_bytes = decoded_bytes
            entry.printable_strings = _extract_printable_strings(decoded_bytes)
            if mapping is None:
                entry.notes.append("Unmapped section")
            else:
                entry.notes.append(mapping.description)
        elif mapping is not None:
            entry.notes.append(mapping.description)

        entries.append(entry)

    return SaveContainer(
        source_path=source_path or Path("<memory>"),
        raw_text=raw_text,
        decoded_json=decoded_json,
        entries=entries,
        community_map=community_map,
    )


def patch_hex_bytes(container: SaveContainer, entry_key: str, byte_offset: int, new_bytes: bytes) -> str:
    entry = container.entry_by_key(entry_key)
    if entry is None:
        raise KeyError(f"Unknown entry key '{entry_key}'.")
    if entry.kind != "hex_section" or entry.decoded_bytes is None:
        raise ValueError(f"Entry '{entry_key}' is not a hex section.")
    if entry.span.string_content_start is None or entry.span.string_content_end is None:
        raise ValueError(f"Entry '{entry_key}' does not expose string content offsets.")
    if byte_offset < 0:
        raise ValueError("byte_offset must be non-negative.")

    replacement_start = entry.span.string_content_start + (byte_offset * 2)
    replacement_text = new_bytes.hex().upper()
    replacement_end = replacement_start + len(replacement_text)

    if replacement_end > entry.span.string_content_end:
        raise ValueError("Replacement would extend past the original hex payload.")

    return (
        container.raw_text[:replacement_start]
        + replacement_text
        + container.raw_text[replacement_end:]
    )


def format_hex_dump(payload: bytes | None, max_bytes: int = 256) -> str:
    if not payload:
        return "(empty)"

    window = payload[:max_bytes]
    lines: list[str] = []
    for offset in range(0, len(window), 16):
        chunk = window[offset : offset + 16]
        hex_part = " ".join(f"{byte:02X}" for byte in chunk)
        ascii_part = "".join(chr(byte) if chr(byte) in string.printable[:-5] else "." for byte in chunk)
        lines.append(f"{offset:08X}  {hex_part:<47}  {ascii_part}")

    if len(payload) > max_bytes:
        lines.append(f"... truncated, showing {max_bytes} of {len(payload)} bytes")

    return "\n".join(lines)


def _index_top_level_entries(raw_text: str) -> dict[str, RawValueSpan]:
    index = 0
    length = len(raw_text)
    spans: dict[str, RawValueSpan] = {}

    index = _skip_whitespace(raw_text, index)
    if index >= length or raw_text[index] != "{":
        raise SaveFormatError("Save file must begin with a JSON object.")
    index += 1

    while True:
        index = _skip_whitespace(raw_text, index)
        if index >= length:
            raise SaveFormatError("Unexpected end of JSON object.")
        if raw_text[index] == "}":
            return spans

        key_token_start, key_token_end, _key_content_start, _key_content_end = _parse_json_string(raw_text, index)
        key = json.loads(raw_text[key_token_start:key_token_end])
        index = _skip_whitespace(raw_text, key_token_end)

        if index >= length or raw_text[index] != ":":
            raise SaveFormatError(f"Expected ':' after key '{key}'.")
        index += 1
        index = _skip_whitespace(raw_text, index)

        value_start = index
        if index >= length:
            raise SaveFormatError(f"Missing value for key '{key}'.")

        if raw_text[index] == '"':
            token_start, token_end, content_start, content_end = _parse_json_string(raw_text, index)
            spans[key] = RawValueSpan(
                key=key,
                token_start=token_start,
                token_end=token_end,
                value_start=token_start,
                value_end=token_end,
                string_content_start=content_start,
                string_content_end=content_end,
            )
            index = token_end
        else:
            token_end = _parse_primitive_end(raw_text, index)
            spans[key] = RawValueSpan(
                key=key,
                token_start=value_start,
                token_end=token_end,
                value_start=value_start,
                value_end=token_end,
            )
            index = token_end

        index = _skip_whitespace(raw_text, index)
        if index >= length:
            raise SaveFormatError("Unexpected end of JSON object after value.")
        if raw_text[index] == ",":
            index += 1
            continue
        if raw_text[index] == "}":
            return spans
        raise SaveFormatError("Expected ',' or '}' after top-level value.")


def _parse_json_string(raw_text: str, start: int) -> tuple[int, int, int, int]:
    if raw_text[start] != '"':
        raise SaveFormatError("Expected JSON string.")

    index = start + 1
    while index < len(raw_text):
        character = raw_text[index]
        if character == "\\":
            index += 2
            continue
        if character == '"':
            return start, index + 1, start + 1, index
        index += 1

    raise SaveFormatError("Unterminated JSON string.")


def _parse_primitive_end(raw_text: str, start: int) -> int:
    index = start
    while index < len(raw_text) and raw_text[index] not in ",}":
        index += 1

    token = raw_text[start:index].rstrip()
    if not token:
        raise SaveFormatError("Expected primitive JSON value.")
    return start + len(token)


def _skip_whitespace(raw_text: str, start: int) -> int:
    index = start
    while index < len(raw_text) and raw_text[index].isspace():
        index += 1
    return index


def _is_hex_string(value: str) -> bool:
    if len(value) == 0 or len(value) % 2 != 0:
        return False
    return all(character in string.hexdigits for character in value)


def _extract_printable_strings(payload: bytes, min_length: int = 4, limit: int = 16) -> list[str]:
    matches: list[str] = []
    current: list[str] = []

    for byte in payload:
        character = chr(byte)
        if 32 <= byte <= 126:
            current.append(character)
            continue

        if len(current) >= min_length:
            matches.append("".join(current))
            if len(matches) >= limit:
                return matches
        current = []

    if len(current) >= min_length and len(matches) < limit:
        matches.append("".join(current))

    return matches
