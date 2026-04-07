from __future__ import annotations

from dataclasses import dataclass
import struct

from chronicon_save_editor.models import SaveContainer
from chronicon_save_editor.parser.json_container import parse_save_text, patch_hex_bytes
from chronicon_save_editor.parser.level import (
    LEVEL_MAX,
    LEVEL_MIN,
    detect_character_level,
)


CHARACTER_SECTION_KEY = "c"
DOUBLE_BYTE_LENGTH = 8
FREE_SKILL_POINTS_OFFSET = 48
FREE_MASTERY_POINTS_OFFSET = 204
SCALAR_MIN = 0
SCALAR_MAX = 1000000


class ProgressionEditError(ValueError):
    """Raised when a mapped progression field cannot be detected or patched safely."""


@dataclass(frozen=True)
class ProgressionField:
    field_id: str
    label: str
    value: int
    section_key: str = CHARACTER_SECTION_KEY
    byte_length: int = DOUBLE_BYTE_LENGTH
    byte_offset: int = 0


@dataclass(frozen=True)
class ProgressionPatchResult:
    field_id: str
    label: str
    original_value: int
    updated_value: int
    section_key: str
    byte_offset: int
    byte_length: int
    changed_keys: tuple[str, ...]
    changed_byte_offsets: tuple[int, ...]
    patched_text: str
    patched_container: SaveContainer


@dataclass(frozen=True)
class CharacterFieldChange:
    field_id: str
    label: str
    original_value: int
    updated_value: int
    section_key: str
    byte_offset: int
    byte_length: int


@dataclass(frozen=True)
class CharacterPatchResult:
    updated_fields: tuple[CharacterFieldChange, ...]
    changed_keys: tuple[str, ...]
    changed_byte_offsets: tuple[int, ...]
    patched_text: str
    patched_container: SaveContainer


def detect_free_skill_points(container: SaveContainer) -> ProgressionField:
    return _detect_integer_double(
        container=container,
        field_id="character.free_skill_points",
        label="Free skill points",
        byte_offset=FREE_SKILL_POINTS_OFFSET,
    )


def detect_free_mastery_points(container: SaveContainer) -> ProgressionField:
    return _detect_integer_double(
        container=container,
        field_id="character.free_mastery_points",
        label="Free mastery points",
        byte_offset=FREE_MASTERY_POINTS_OFFSET,
    )


def apply_free_skill_points_patch(
    container: SaveContainer,
    new_value: int,
) -> ProgressionPatchResult:
    return _apply_integer_double_patch(
        container=container,
        detect_field=detect_free_skill_points,
        new_value=new_value,
    )


def apply_free_mastery_points_patch(
    container: SaveContainer,
    new_value: int,
) -> ProgressionPatchResult:
    return _apply_integer_double_patch(
        container=container,
        detect_field=detect_free_mastery_points,
        new_value=new_value,
    )


def apply_character_field_changes(
    container: SaveContainer,
    *,
    new_level: int | None = None,
    new_free_skill_points: int | None = None,
    new_free_mastery_points: int | None = None,
) -> CharacterPatchResult:
    updates: list[CharacterFieldChange] = []

    level_field = detect_character_level(container)
    requested_level = level_field.value if new_level is None else new_level
    if not LEVEL_MIN <= requested_level <= LEVEL_MAX:
        raise ProgressionEditError(
            f"Character level must be between {LEVEL_MIN} and {LEVEL_MAX}."
        )
    if requested_level != level_field.value:
        updates.append(
            CharacterFieldChange(
                field_id="character.level",
                label="Character level",
                original_value=level_field.value,
                updated_value=requested_level,
                section_key=level_field.section_key,
                byte_offset=level_field.byte_offset,
                byte_length=level_field.byte_length,
            )
        )

    skill_field = detect_free_skill_points(container)
    requested_skill_points = (
        skill_field.value if new_free_skill_points is None else new_free_skill_points
    )
    if not SCALAR_MIN <= requested_skill_points <= SCALAR_MAX:
        raise ProgressionEditError(
            f"Free skill points must be between {SCALAR_MIN} and {SCALAR_MAX}."
        )
    if requested_skill_points != skill_field.value:
        updates.append(
            CharacterFieldChange(
                field_id=skill_field.field_id,
                label=skill_field.label,
                original_value=skill_field.value,
                updated_value=requested_skill_points,
                section_key=skill_field.section_key,
                byte_offset=skill_field.byte_offset,
                byte_length=skill_field.byte_length,
            )
        )

    mastery_field = detect_free_mastery_points(container)
    requested_mastery_points = (
        mastery_field.value
        if new_free_mastery_points is None
        else new_free_mastery_points
    )
    if not SCALAR_MIN <= requested_mastery_points <= SCALAR_MAX:
        raise ProgressionEditError(
            f"Free mastery points must be between {SCALAR_MIN} and {SCALAR_MAX}."
        )
    if requested_mastery_points != mastery_field.value:
        updates.append(
            CharacterFieldChange(
                field_id=mastery_field.field_id,
                label=mastery_field.label,
                original_value=mastery_field.value,
                updated_value=requested_mastery_points,
                section_key=mastery_field.section_key,
                byte_offset=mastery_field.byte_offset,
                byte_length=mastery_field.byte_length,
            )
        )

    if not updates:
        raise ProgressionEditError("No character field changes were requested.")

    patched_text = container.raw_text
    working_container = container
    for update in sorted(updates, key=lambda item: (item.section_key, item.byte_offset)):
        replacement_bytes = struct.pack("<d", float(update.updated_value))
        patched_text = patch_hex_bytes(
            container=working_container,
            entry_key=update.section_key,
            byte_offset=update.byte_offset,
            new_bytes=replacement_bytes,
        )
        working_container = parse_save_text(
            raw_text=patched_text,
            source_path=container.source_path,
        )

    return validate_character_field_changes(
        original_container=container,
        patched_text=patched_text,
        expected_updates=tuple(updates),
    )


def validate_character_field_changes(
    original_container: SaveContainer,
    patched_text: str,
    expected_updates: tuple[CharacterFieldChange, ...],
) -> CharacterPatchResult:
    patched_container = parse_save_text(
        raw_text=patched_text,
        source_path=original_container.source_path,
    )

    current_values = {
        "character.level": detect_character_level(patched_container).value,
        "character.free_skill_points": detect_free_skill_points(patched_container).value,
        "character.free_mastery_points": detect_free_mastery_points(patched_container).value,
    }
    for update in expected_updates:
        actual_value = current_values.get(update.field_id)
        if actual_value != update.updated_value:
            raise ProgressionEditError(
                f"Patched {update.label.lower()} validation failed. "
                f"Expected {update.updated_value}, got {actual_value}."
            )

    changed_keys = tuple(
        key
        for key in original_container.decoded_json
        if original_container.decoded_json[key] != patched_container.decoded_json.get(key)
    )
    intended_keys = tuple(dict.fromkeys(update.section_key for update in expected_updates))
    if changed_keys != intended_keys:
        raise ProgressionEditError(
            "Validation failed because more than the intended top-level section changed: "
            f"{changed_keys!r}"
        )

    original_entry = original_container.entry_by_key(CHARACTER_SECTION_KEY)
    patched_entry = patched_container.entry_by_key(CHARACTER_SECTION_KEY)
    if original_entry is None or patched_entry is None:
        raise ProgressionEditError("Patched container is missing the targeted character section.")
    if original_entry.decoded_bytes is None or patched_entry.decoded_bytes is None:
        raise ProgressionEditError("Section 'c' could not be decoded for validation.")
    if len(original_entry.decoded_bytes) != len(patched_entry.decoded_bytes):
        raise ProgressionEditError("Patched character section changed length unexpectedly.")

    changed_byte_offsets = tuple(
        offset
        for offset, (before, after) in enumerate(
            zip(original_entry.decoded_bytes, patched_entry.decoded_bytes)
        )
        if before != after
    )
    allowed_offsets = {
        offset
        for update in expected_updates
        for offset in range(update.byte_offset, update.byte_offset + update.byte_length)
    }
    if any(offset not in allowed_offsets for offset in changed_byte_offsets):
        raise ProgressionEditError(
            "Validation failed because bytes outside the intended scalar ranges changed: "
            f"{changed_byte_offsets!r}"
        )

    return CharacterPatchResult(
        updated_fields=expected_updates,
        changed_keys=changed_keys,
        changed_byte_offsets=changed_byte_offsets,
        patched_text=patched_text,
        patched_container=patched_container,
    )


def _detect_integer_double(
    container: SaveContainer,
    field_id: str,
    label: str,
    byte_offset: int,
) -> ProgressionField:
    entry = container.entry_by_key(CHARACTER_SECTION_KEY)
    if entry is None or entry.kind != "hex_section" or entry.decoded_bytes is None:
        raise ProgressionEditError("Character metadata section 'c' is missing or not decodable.")

    if len(entry.decoded_bytes) < byte_offset + DOUBLE_BYTE_LENGTH:
        raise ProgressionEditError(f"Section 'c' is too short to contain {label.lower()}.")

    raw_value = struct.unpack(
        "<d",
        entry.decoded_bytes[byte_offset : byte_offset + DOUBLE_BYTE_LENGTH],
    )[0]
    if not raw_value.is_integer():
        raise ProgressionEditError(
            f"Detected {label.lower()} is not stored as an integer value: {raw_value!r}"
        )

    value = int(raw_value)
    if not SCALAR_MIN <= value <= SCALAR_MAX:
        raise ProgressionEditError(
            f"Detected {label.lower()} {value} is outside the supported range "
            f"{SCALAR_MIN}..{SCALAR_MAX}."
        )

    return ProgressionField(
        field_id=field_id,
        label=label,
        value=value,
        byte_offset=byte_offset,
    )


def _apply_integer_double_patch(
    container: SaveContainer,
    detect_field,
    new_value: int,
) -> ProgressionPatchResult:
    field = detect_field(container)
    if not SCALAR_MIN <= new_value <= SCALAR_MAX:
        raise ProgressionEditError(
            f"{field.label} must be between {SCALAR_MIN} and {SCALAR_MAX}."
        )

    replacement_bytes = struct.pack("<d", float(new_value))
    patched_text = patch_hex_bytes(
        container=container,
        entry_key=field.section_key,
        byte_offset=field.byte_offset,
        new_bytes=replacement_bytes,
    )
    return _validate_integer_double_patch(
        original_container=container,
        patched_text=patched_text,
        detect_field=detect_field,
        expected_value=new_value,
    )


def _validate_integer_double_patch(
    original_container: SaveContainer,
    patched_text: str,
    detect_field,
    expected_value: int,
) -> ProgressionPatchResult:
    original_field = detect_field(original_container)
    patched_container = parse_save_text(
        raw_text=patched_text,
        source_path=original_container.source_path,
    )
    patched_field = detect_field(patched_container)
    if patched_field.value != expected_value:
        raise ProgressionEditError(
            f"Patched {patched_field.label.lower()} validation failed. "
            f"Expected {expected_value}, got {patched_field.value}."
        )

    changed_keys = tuple(
        key
        for key in original_container.decoded_json
        if original_container.decoded_json[key] != patched_container.decoded_json.get(key)
    )
    if changed_keys != (original_field.section_key,):
        raise ProgressionEditError(
            "Validation failed because more than the intended top-level section changed: "
            f"{changed_keys!r}"
        )

    original_entry = original_container.entry_by_key(original_field.section_key)
    patched_entry = patched_container.entry_by_key(original_field.section_key)
    if original_entry is None or patched_entry is None:
        raise ProgressionEditError("Patched container is missing the targeted character section.")
    if original_entry.decoded_bytes is None or patched_entry.decoded_bytes is None:
        raise ProgressionEditError("Section 'c' could not be decoded for validation.")
    if len(original_entry.decoded_bytes) != len(patched_entry.decoded_bytes):
        raise ProgressionEditError("Patched character section changed length unexpectedly.")

    changed_byte_offsets = tuple(
        offset
        for offset, (before, after) in enumerate(
            zip(original_entry.decoded_bytes, patched_entry.decoded_bytes)
        )
        if before != after
    )
    allowed_offsets = range(
        original_field.byte_offset,
        original_field.byte_offset + original_field.byte_length,
    )
    if any(offset not in allowed_offsets for offset in changed_byte_offsets):
        raise ProgressionEditError(
            "Validation failed because bytes outside the intended scalar range changed: "
            f"{changed_byte_offsets!r}"
        )

    return ProgressionPatchResult(
        field_id=patched_field.field_id,
        label=patched_field.label,
        original_value=original_field.value,
        updated_value=patched_field.value,
        section_key=patched_field.section_key,
        byte_offset=patched_field.byte_offset,
        byte_length=patched_field.byte_length,
        changed_keys=changed_keys,
        changed_byte_offsets=changed_byte_offsets,
        patched_text=patched_text,
        patched_container=patched_container,
    )
