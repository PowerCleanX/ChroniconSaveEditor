import json
import struct

from chronicon_save_editor.parser import (
    apply_character_level_patch,
    detect_character_level,
    parse_save_text,
)


def test_character_level_read_write_round_trip() -> None:
    raw_text = _build_save_text(level=56)

    original = parse_save_text(raw_text)
    detected = detect_character_level(original)
    patch_result = apply_character_level_patch(original, new_level=60)
    updated = parse_save_text(patch_result.patched_text)
    updated_field = detect_character_level(updated)

    assert detected.value == 56
    assert patch_result.original_level == 56
    assert patch_result.updated_level == 60
    assert patch_result.changed_keys == ("c",)
    assert patch_result.changed_byte_offsets
    assert all(24 <= offset <= 31 for offset in patch_result.changed_byte_offsets)
    assert updated_field.value == 60
    assert updated.decoded_json["y"] is False
    assert original.decoded_json["a"] == updated.decoded_json["a"]


def _build_save_text(level: int) -> str:
    section_c = bytearray(409)
    struct.pack_into("<I", section_c, 0, 0x12F)
    struct.pack_into("<I", section_c, 4, 0x20)
    struct.pack_into("<d", section_c, 16, 1.0)
    struct.pack_into("<d", section_c, 24, float(level))
    struct.pack_into("<d", section_c, 72, 2.0)
    struct.pack_into("<d", section_c, 84, 3.0)
    struct.pack_into("<d", section_c, 96, 294.0)
    struct.pack_into("<d", section_c, 108, -4.0)
    struct.pack_into("<d", section_c, 120, -4.0)
    struct.pack_into("<d", section_c, 132, -4.0)
    struct.pack_into("<d", section_c, 144, -4.0)
    struct.pack_into("<d", section_c, 156, -4.0)
    struct.pack_into("<d", section_c, 168, 1.0)
    struct.pack_into("<d", section_c, 180, -1.0)
    struct.pack_into("<d", section_c, 192, 35.0)
    struct.pack_into("<d", section_c, 228, 4.0)
    struct.pack_into("<d", section_c, 240, 50.0)
    struct.pack_into("<I", section_c, 248, 1)
    struct.pack_into("<I", section_c, 252, 16)
    section_c[256:272] = b"2F01000000000000"
    struct.pack_into("<I", section_c, 272, 1)
    struct.pack_into("<I", section_c, 276, 7)
    section_c[280:287] = b"Templar"
    struct.pack_into("<I", section_c, 287, 1)
    struct.pack_into("<I", section_c, 291, 7)
    section_c[295:302] = b"default"
    struct.pack_into("<I", section_c, 302, 1)
    struct.pack_into("<I", section_c, 306, 7)
    section_c[310:317] = b"default"

    payload = {
        "c": section_c.hex().upper(),
        "a": "00010203",
        "y": False,
    }
    return json.dumps(payload)
