from __future__ import annotations

import binascii
from dataclasses import dataclass
import struct
from typing import Any

from chronicon_save_editor.models import SaveContainer
from chronicon_save_editor.parser.json_container import parse_save_text, patch_hex_bytes


EQUIPPED_SECTION_KEY = "e"
ITEM_RECORD_MAGIC = 403
FIELD_MARKER = 1
NUMERIC_VALUE_TYPE = 0
STRING_VALUE_TYPE = 1
OPAQUE_VALUE_TYPE = 13


class EquippedItemError(ValueError):
    """Raised when equipped item parsing or affix editing fails."""


@dataclass(frozen=True)
class EquippedAffixDefinition:
    key: str
    label: str
    editable: bool = True
    decimals: int = 2


@dataclass(frozen=True)
class EquippedItemAffix:
    key: str
    label: str
    value: float
    decimals: int
    record_index: int
    item_name: str
    section_key: str
    outer_byte_offset: int
    outer_byte_length: int
    inner_byte_offset: int
    inner_byte_length: int


@dataclass(frozen=True)
class EquippedItemRecord:
    record_index: int
    name: str
    level: int | None
    outer_record_offset: int
    outer_record_length: int
    affixes: tuple[EquippedItemAffix, ...]
    numeric_fields: dict[str, float]


@dataclass(frozen=True)
class EquippedAffixPatchResult:
    item_name: str
    affix_key: str
    original_value: float
    updated_value: float
    section_key: str
    changed_keys: tuple[str, ...]
    changed_byte_offsets: tuple[int, ...]
    patched_text: str
    patched_container: SaveContainer


@dataclass(frozen=True)
class ParsedItemField:
    key: str
    value_type: int
    value: Any
    value_offset: int
    value_length: int


def read_equipped_items(container: SaveContainer) -> tuple[EquippedItemRecord, ...]:
    entry = container.entry_by_key(EQUIPPED_SECTION_KEY)
    if entry is None or entry.kind != "hex_section" or entry.decoded_bytes is None:
        raise EquippedItemError("Equipped item section 'e' is missing or not decodable.")

    affix_map = _load_affix_definitions(container)
    outer = entry.decoded_bytes

    if len(outer) < 20:
        raise EquippedItemError("Equipped item section is too short to contain any records.")

    record_count = struct.unpack_from("<I", outer, 4)[0]
    records: list[EquippedItemRecord] = []
    outer_offset = 0

    for record_index in range(record_count):
        if outer_offset + 20 > len(outer):
            raise EquippedItemError("Equipped item section ended before all records were parsed.")

        record_length = struct.unpack_from("<I", outer, outer_offset + 16)[0]
        record_ascii_offset = outer_offset + 20
        record_ascii_end = record_ascii_offset + record_length
        if record_ascii_end > len(outer):
            raise EquippedItemError("Equipped item record extends past the end of section 'e'.")

        record_ascii = outer[record_ascii_offset:record_ascii_end]
        try:
            inner = binascii.unhexlify(record_ascii)
        except binascii.Error as exc:
            raise EquippedItemError("Equipped item record did not contain valid inner hex.") from exc

        parsed_fields = _parse_item_record(inner)
        field_lookup = {field.key: field for field in parsed_fields}
        name_field = field_lookup.get("name")
        if name_field is None or not isinstance(name_field.value, str):
            outer_offset = record_ascii_end
            continue

        name = name_field.value
        level_value = field_lookup.get("level")
        level = _float_to_int(level_value.value) if level_value is not None and isinstance(level_value.value, float) else None

        numeric_fields = {
            field.key: field.value
            for field in parsed_fields
            if field.value_type == NUMERIC_VALUE_TYPE and isinstance(field.value, float)
        }
        affixes: list[EquippedItemAffix] = []
        for key, definition in affix_map.items():
            field = field_lookup.get(key)
            if field is None or field.value_type != NUMERIC_VALUE_TYPE or not isinstance(field.value, float):
                continue

            affixes.append(
                EquippedItemAffix(
                    key=key,
                    label=definition.label,
                    value=field.value,
                    decimals=definition.decimals,
                    record_index=record_index,
                    item_name=name,
                    section_key=EQUIPPED_SECTION_KEY,
                    outer_byte_offset=record_ascii_offset + (field.value_offset * 2),
                    outer_byte_length=field.value_length * 2,
                    inner_byte_offset=field.value_offset,
                    inner_byte_length=field.value_length,
                )
            )

        if affixes:
            records.append(
                EquippedItemRecord(
                    record_index=record_index,
                    name=name,
                    level=level,
                    outer_record_offset=record_ascii_offset,
                    outer_record_length=record_length,
                    affixes=tuple(affixes),
                    numeric_fields=numeric_fields,
                )
            )

        outer_offset = record_ascii_end

    return tuple(records)


def apply_equipped_affix_patch(
    container: SaveContainer,
    record_index: int,
    affix_key: str,
    new_value: float,
) -> EquippedAffixPatchResult:
    items = read_equipped_items(container)
    item = next((candidate for candidate in items if candidate.record_index == record_index), None)
    if item is None:
        raise EquippedItemError(f"Equipped item record {record_index} was not found.")

    affix = next((candidate for candidate in item.affixes if candidate.key == affix_key), None)
    if affix is None:
        raise EquippedItemError(
            f"Equipped item '{item.name}' does not expose an editable affix '{affix_key}'."
        )

    replacement_inner_bytes = struct.pack("<d", float(new_value))
    replacement_outer_bytes = replacement_inner_bytes.hex().upper().encode("ascii")
    patched_text = patch_hex_bytes(
        container=container,
        entry_key=EQUIPPED_SECTION_KEY,
        byte_offset=affix.outer_byte_offset,
        new_bytes=replacement_outer_bytes,
    )

    return validate_equipped_affix_patch(
        original_container=container,
        patched_text=patched_text,
        record_index=record_index,
        affix_key=affix_key,
        expected_value=float(new_value),
    )


def validate_equipped_affix_patch(
    original_container: SaveContainer,
    patched_text: str,
    record_index: int,
    affix_key: str,
    expected_value: float,
) -> EquippedAffixPatchResult:
    original_items = read_equipped_items(original_container)
    original_item = next((candidate for candidate in original_items if candidate.record_index == record_index), None)
    if original_item is None:
        raise EquippedItemError(f"Equipped item record {record_index} was not found.")

    original_affix = next((candidate for candidate in original_item.affixes if candidate.key == affix_key), None)
    if original_affix is None:
        raise EquippedItemError(
            f"Equipped item '{original_item.name}' does not expose an editable affix '{affix_key}'."
        )

    patched_container = parse_save_text(
        raw_text=patched_text,
        source_path=original_container.source_path,
    )
    patched_items = read_equipped_items(patched_container)
    patched_item = next((candidate for candidate in patched_items if candidate.record_index == record_index), None)
    if patched_item is None:
        raise EquippedItemError("Patched save is missing the targeted equipped item.")

    patched_affix = next((candidate for candidate in patched_item.affixes if candidate.key == affix_key), None)
    if patched_affix is None:
        raise EquippedItemError("Patched save is missing the targeted equipped affix.")

    if patched_affix.value != expected_value:
        raise EquippedItemError(
            f"Patched affix validation failed. Expected {expected_value}, got {patched_affix.value}."
        )

    changed_keys = tuple(
        key
        for key in original_container.decoded_json
        if original_container.decoded_json[key] != patched_container.decoded_json.get(key)
    )
    if changed_keys != (EQUIPPED_SECTION_KEY,):
        raise EquippedItemError(
            "Validation failed because more than the intended top-level section changed: "
            f"{changed_keys!r}"
        )

    original_entry = original_container.entry_by_key(EQUIPPED_SECTION_KEY)
    patched_entry = patched_container.entry_by_key(EQUIPPED_SECTION_KEY)
    if original_entry is None or patched_entry is None:
        raise EquippedItemError("Patched save is missing section 'e'.")
    if original_entry.decoded_bytes is None or patched_entry.decoded_bytes is None:
        raise EquippedItemError("Section 'e' could not be decoded for validation.")
    if len(original_entry.decoded_bytes) != len(patched_entry.decoded_bytes):
        raise EquippedItemError("Section 'e' changed length unexpectedly.")

    changed_byte_offsets = tuple(
        offset
        for offset, (before, after) in enumerate(
            zip(original_entry.decoded_bytes, patched_entry.decoded_bytes)
        )
        if before != after
    )
    allowed_offsets = range(
        original_affix.outer_byte_offset,
        original_affix.outer_byte_offset + original_affix.outer_byte_length,
    )
    if any(offset not in allowed_offsets for offset in changed_byte_offsets):
        raise EquippedItemError(
            "Validation failed because bytes outside the intended affix range changed: "
            f"{changed_byte_offsets!r}"
        )

    return EquippedAffixPatchResult(
        item_name=patched_item.name,
        affix_key=affix_key,
        original_value=original_affix.value,
        updated_value=patched_affix.value,
        section_key=EQUIPPED_SECTION_KEY,
        changed_keys=changed_keys,
        changed_byte_offsets=changed_byte_offsets,
        patched_text=patched_text,
        patched_container=patched_container,
    )


def _parse_item_record(inner: bytes) -> tuple[ParsedItemField, ...]:
    if len(inner) < 8:
        raise EquippedItemError("Equipped item record is too short.")

    magic, field_count = struct.unpack_from("<II", inner, 0)
    if magic != ITEM_RECORD_MAGIC:
        raise EquippedItemError(f"Unexpected equipped item magic {magic!r}.")

    fields: list[ParsedItemField] = []
    offset = 8
    for _ in range(field_count):
        if offset + 8 > len(inner):
            raise EquippedItemError("Equipped item record ended before all fields were parsed.")

        marker, key_length = struct.unpack_from("<II", inner, offset)
        offset += 8
        if marker != FIELD_MARKER:
            raise EquippedItemError(f"Unexpected equipped item field marker {marker!r}.")
        if offset + key_length > len(inner):
            raise EquippedItemError("Equipped item field name extends past the record boundary.")

        key = inner[offset : offset + key_length].decode("ascii")
        offset += key_length

        if offset + 4 > len(inner):
            raise EquippedItemError("Equipped item field ended before value type could be read.")
        value_type = struct.unpack_from("<I", inner, offset)[0]
        offset += 4

        value_offset = offset
        if value_type == NUMERIC_VALUE_TYPE:
            if offset + 8 > len(inner):
                raise EquippedItemError("Numeric equipped item field extends past the record boundary.")
            value = struct.unpack_from("<d", inner, offset)[0]
            value_length = 8
            offset += value_length
        elif value_type == STRING_VALUE_TYPE:
            if offset + 4 > len(inner):
                raise EquippedItemError("String equipped item field missing its length.")
            value_length = struct.unpack_from("<I", inner, offset)[0]
            offset += 4
            value_offset = offset
            if offset + value_length > len(inner):
                raise EquippedItemError("String equipped item field extends past the record boundary.")
            value = inner[offset : offset + value_length].decode("utf-8")
            offset += value_length
        elif value_type == OPAQUE_VALUE_TYPE:
            if offset + 8 > len(inner):
                raise EquippedItemError("Opaque equipped item field extends past the record boundary.")
            value = inner[offset : offset + 8]
            value_length = 8
            offset += value_length
        else:
            raise EquippedItemError(f"Unsupported equipped item value type {value_type!r} for key '{key}'.")

        fields.append(
            ParsedItemField(
                key=key,
                value_type=value_type,
                value=value,
                value_offset=value_offset,
                value_length=value_length,
            )
        )

    return tuple(fields)


def _load_affix_definitions(container: SaveContainer) -> dict[str, EquippedAffixDefinition]:
    definitions: dict[str, EquippedAffixDefinition] = {}
    for key, payload in container.community_map.affixes.items():
        if not isinstance(payload, dict):
            continue
        definitions[key] = EquippedAffixDefinition(
            key=key,
            label=str(payload.get("label", key)),
            editable=bool(payload.get("editable", True)),
            decimals=int(payload.get("decimals", 2)),
        )
    return definitions


def _float_to_int(value: Any) -> int | None:
    if not isinstance(value, float):
        return None
    if not value.is_integer():
        return None
    return int(value)
