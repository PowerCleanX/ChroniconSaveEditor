import json
import struct

from chronicon_save_editor.parser import (
    assess_inventory_duplication,
    find_first_empty_inventory_slot,
    parse_save_text,
    read_inventory_slots,
)


def test_read_inventory_slots_detects_occupied_and_empty_records() -> None:
    raw_text = _build_save_text()

    container = parse_save_text(raw_text)
    slots = read_inventory_slots(container)

    assert len(slots) == 3
    assert slots[0].is_occupied is True
    assert slots[0].item_name == "Key"
    assert slots[0].quantity == 47
    assert slots[1].is_occupied is True
    assert slots[1].item_name == "Scroll of Return"
    assert slots[1].quantity == 70
    assert slots[2].is_occupied is False
    assert slots[2].record_length == 0
    assert find_first_empty_inventory_slot(slots).slot_index == 2


def test_inventory_duplication_assessment_keeps_empty_slot_injection_disabled() -> None:
    raw_text = _build_save_text()

    container = parse_save_text(raw_text)
    assessment = assess_inventory_duplication(
        container,
        source_slot_index=0,
        target_slot_index=2,
    )

    assert assessment.can_duplicate_safely is False
    assert assessment.source_record_length > 0
    assert assessment.target_record_length == 0
    assert "zero-length inline records" in assessment.reason


def _build_save_text() -> str:
    item_records = [
        _build_item_record(
            [
                ("id", 93.0),
                ("qt", 47.0),
                ("level", 1.0),
                ("quality", 1.0),
                ("name", "Key"),
            ]
        ),
        _build_item_record(
            [
                ("id", 249.0),
                ("qt", 70.0),
                ("level", 1.0),
                ("quality", 1.0),
                ("name", "Scroll of Return"),
            ]
        ),
    ]
    outer_section = _build_outer_inventory_section(item_records)
    payload = {
        "i": outer_section.hex().upper(),
        "c": "2F0100002000000000000000000000000000F03F000000000000000000004540",
        "y": False,
    }
    return json.dumps(payload)


def _build_outer_inventory_section(item_records: list[bytes]) -> bytes:
    outer = bytearray()
    slot_count = 3
    for index in range(slot_count):
        if index < len(item_records):
            record_ascii = item_records[index].hex().upper().encode("ascii")
            header_hint = 2 if index == 0 else 1078427648
            if index == 0:
                outer += struct.pack("<IIIII", 603, slot_count, 2, 1, len(record_ascii))
            else:
                outer += struct.pack("<IIIII", 0, 0, header_hint, 1, len(record_ascii))
            outer += record_ascii
        else:
            outer += struct.pack("<IIIII", 0, 0, 1074266112, 1, 0)
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
