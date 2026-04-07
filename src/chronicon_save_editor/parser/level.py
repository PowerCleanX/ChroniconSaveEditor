from __future__ import annotations

from dataclasses import dataclass
import struct

from chronicon_save_editor.models import SaveContainer
from chronicon_save_editor.parser.json_container import parse_save_text, patch_hex_bytes


LEVEL_SECTION_KEY = "c"
LEVEL_BYTE_OFFSET = 24
LEVEL_BYTE_LENGTH = 8
LEVEL_MIN = 1
LEVEL_MAX = 300


class LevelEditError(ValueError):
    """Raised when character-level detection or patch validation fails."""


@dataclass(frozen=True)
class CharacterLevelField:
    value: int
    section_key: str = LEVEL_SECTION_KEY
    byte_offset: int = LEVEL_BYTE_OFFSET
    byte_length: int = LEVEL_BYTE_LENGTH


@dataclass(frozen=True)
class LevelPatchResult:
    original_level: int
    updated_level: int
    section_key: str
    byte_offset: int
    byte_length: int
    changed_keys: tuple[str, ...]
    changed_byte_offsets: tuple[int, ...]
    patched_text: str
    patched_container: SaveContainer


def detect_character_level(container: SaveContainer) -> CharacterLevelField:
    entry = container.entry_by_key(LEVEL_SECTION_KEY)
    if entry is None or entry.kind != "hex_section" or entry.decoded_bytes is None:
        raise LevelEditError("Character metadata section 'c' is missing or not decodable.")

    if len(entry.decoded_bytes) < LEVEL_BYTE_OFFSET + LEVEL_BYTE_LENGTH:
        raise LevelEditError("Character metadata section is too short to contain a level field.")

    raw_level = struct.unpack(
        "<d",
        entry.decoded_bytes[LEVEL_BYTE_OFFSET : LEVEL_BYTE_OFFSET + LEVEL_BYTE_LENGTH],
    )[0]

    if not raw_level.is_integer():
        raise LevelEditError(f"Detected character level is not an integer: {raw_level!r}")

    level = int(raw_level)
    if not LEVEL_MIN <= level <= LEVEL_MAX:
        raise LevelEditError(
            f"Detected character level {level} is outside the supported range "
            f"{LEVEL_MIN}..{LEVEL_MAX}."
        )

    return CharacterLevelField(value=level)


def apply_character_level_patch(container: SaveContainer, new_level: int) -> LevelPatchResult:
    field = detect_character_level(container)

    if not LEVEL_MIN <= new_level <= LEVEL_MAX:
        raise LevelEditError(f"Character level must be between {LEVEL_MIN} and {LEVEL_MAX}.")

    replacement_bytes = struct.pack("<d", float(new_level))
    patched_text = patch_hex_bytes(
        container=container,
        entry_key=field.section_key,
        byte_offset=field.byte_offset,
        new_bytes=replacement_bytes,
    )
    return validate_character_level_patch(
        original_container=container,
        patched_text=patched_text,
        expected_level=new_level,
    )


def validate_character_level_patch(
    original_container: SaveContainer,
    patched_text: str,
    expected_level: int,
) -> LevelPatchResult:
    original_field = detect_character_level(original_container)
    patched_container = parse_save_text(
        raw_text=patched_text,
        source_path=original_container.source_path,
    )
    patched_field = detect_character_level(patched_container)

    if patched_field.value != expected_level:
        raise LevelEditError(
            f"Patched level validation failed. Expected {expected_level}, got {patched_field.value}."
        )

    changed_keys = tuple(
        key
        for key in original_container.decoded_json
        if original_container.decoded_json[key] != patched_container.decoded_json.get(key)
    )
    if changed_keys != (original_field.section_key,):
        raise LevelEditError(
            "Validation failed because more than the intended top-level section changed: "
            f"{changed_keys!r}"
        )

    original_entry = original_container.entry_by_key(original_field.section_key)
    patched_entry = patched_container.entry_by_key(original_field.section_key)
    if original_entry is None or patched_entry is None:
        raise LevelEditError("Patched container is missing the intended level section.")
    if original_entry.decoded_bytes is None or patched_entry.decoded_bytes is None:
        raise LevelEditError("Patched level section could not be decoded for validation.")
    if len(original_entry.decoded_bytes) != len(patched_entry.decoded_bytes):
        raise LevelEditError("Patched level section changed length unexpectedly.")

    changed_byte_offsets = tuple(
        offset
        for offset, (before, after) in enumerate(
            zip(original_entry.decoded_bytes, patched_entry.decoded_bytes)
        )
        if before != after
    )

    allowed_offsets = range(original_field.byte_offset, original_field.byte_offset + original_field.byte_length)
    if any(offset not in allowed_offsets for offset in changed_byte_offsets):
        raise LevelEditError(
            "Validation failed because bytes outside the intended level range changed: "
            f"{changed_byte_offsets!r}"
        )

    return LevelPatchResult(
        original_level=original_field.value,
        updated_level=patched_field.value,
        section_key=original_field.section_key,
        byte_offset=original_field.byte_offset,
        byte_length=original_field.byte_length,
        changed_keys=changed_keys,
        changed_byte_offsets=changed_byte_offsets,
        patched_text=patched_text,
        patched_container=patched_container,
    )
