import json
import struct

from chronicon_save_editor.parser import (
    apply_equipped_affix_patch,
    parse_save_text,
    read_equipped_items,
)


def test_read_equipped_items_extracts_name_level_and_mapped_affixes() -> None:
    raw_text = _build_save_text()

    container = parse_save_text(raw_text)
    items = read_equipped_items(container)

    assert len(items) == 1
    item = items[0]
    assert item.name == "Test Relic"
    assert item.level == 42
    affixes = {affix.key: affix.value for affix in item.affixes}
    assert affixes["dmg"] == 123.0
    assert affixes["crit"] == 0.15
    assert affixes["enchant_value0"] == 9.0


def test_equipped_affix_patch_round_trip_only_changes_selected_range() -> None:
    raw_text = _build_save_text()

    original = parse_save_text(raw_text)
    patch_result = apply_equipped_affix_patch(
        container=original,
        record_index=0,
        affix_key="dmg",
        new_value=321.0,
    )
    updated = parse_save_text(patch_result.patched_text)
    updated_items = read_equipped_items(updated)

    assert patch_result.changed_keys == ("e",)
    assert patch_result.changed_byte_offsets
    affix = next(affix for affix in updated_items[0].affixes if affix.key == "dmg")
    assert affix.value == 321.0
    assert all(
        affix.outer_byte_offset <= offset < affix.outer_byte_offset + affix.outer_byte_length
        for offset in patch_result.changed_byte_offsets
    )


def _build_save_text() -> str:
    item_fields = [
        ("dmg", 123.0),
        ("level", 42.0),
        ("quality", 4.0),
        ("crit", 0.15),
        ("enchant_value0", 9.0),
        ("name", "Test Relic"),
        ("socket_prismatic0", b"\x00" * 8),
    ]
    inner_record = _build_item_record(item_fields)
    outer_section = _build_outer_equipped_section([inner_record])
    payload = {
        "e": outer_section.hex().upper(),
        "c": "2F0100002000000000000000000000000000F03F000000000000000000004540",
        "y": False,
    }
    return json.dumps(payload)


def _build_outer_equipped_section(item_records: list[bytes]) -> bytes:
    outer = bytearray()
    for index, record in enumerate(item_records):
        record_ascii = record.hex().upper().encode("ascii")
        if index == 0:
            outer += struct.pack("<IIIII", 603, len(item_records), 2, 1, len(record_ascii))
        else:
            outer += struct.pack("<IIIII", 0, 0, 0, 1, len(record_ascii))
        outer += record_ascii
    outer += b"\x00" * 12
    return bytes(outer)


def _build_item_record(fields: list[tuple[str, object]]) -> bytes:
    payload = bytearray(struct.pack("<II", 403, len(fields)))
    for key, value in fields:
        key_bytes = key.encode("ascii")
        payload += struct.pack("<II", 1, len(key_bytes))
        payload += key_bytes
        if isinstance(value, str):
            value_bytes = value.encode("utf-8")
            payload += struct.pack("<II", 1, len(value_bytes))
            payload += value_bytes
        elif isinstance(value, (bytes, bytearray)):
            payload += struct.pack("<I", 13)
            payload += bytes(value)
        else:
            payload += struct.pack("<I", 0)
            payload += struct.pack("<d", float(value))
    return bytes(payload)
