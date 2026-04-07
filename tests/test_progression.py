import json
import struct

from chronicon_save_editor.parser import (
    apply_character_field_changes,
    apply_free_mastery_points_patch,
    apply_free_skill_points_patch,
    detect_character_level,
    detect_free_mastery_points,
    detect_free_skill_points,
    parse_save_text,
)


def test_free_skill_points_read_write_round_trip() -> None:
    raw_text = _build_save_text(free_skill_points=0, unsupported_scalar=35)

    original = parse_save_text(raw_text)
    detected = detect_free_skill_points(original)
    patch_result = apply_free_skill_points_patch(original, new_value=36)
    updated = parse_save_text(patch_result.patched_text)
    updated_field = detect_free_skill_points(updated)

    assert detected.value == 0
    assert patch_result.original_value == 0
    assert patch_result.updated_value == 36
    assert patch_result.changed_keys == ("c",)
    assert patch_result.changed_byte_offsets
    assert all(48 <= offset <= 55 for offset in patch_result.changed_byte_offsets)
    assert updated_field.value == 36
    assert original.decoded_json["a"] == updated.decoded_json["a"]


def test_combined_character_changes_patch_only_modified_ranges() -> None:
    raw_text = _build_save_text(free_skill_points=2, unsupported_scalar=35, level=70)

    original = parse_save_text(raw_text)
    patch_result = apply_character_field_changes(
        original,
        new_level=71,
        new_free_skill_points=3,
        new_free_mastery_points=4,
    )
    updated = parse_save_text(patch_result.patched_text)
    updated_level = detect_character_level(updated)
    updated_skill_points = detect_free_skill_points(updated)
    updated_mastery_points = detect_free_mastery_points(updated)

    assert [field.field_id for field in patch_result.updated_fields] == [
        "character.level",
        "character.free_skill_points",
        "character.free_mastery_points",
    ]
    assert patch_result.changed_keys == ("c",)
    assert patch_result.changed_byte_offsets
    assert all(
        24 <= offset <= 31 or 48 <= offset <= 55 or 204 <= offset <= 211
        for offset in patch_result.changed_byte_offsets
    )
    assert updated_level.value == 71
    assert updated_skill_points.value == 3
    assert updated_mastery_points.value == 4
    assert original.decoded_json["a"] == updated.decoded_json["a"]


def test_free_mastery_points_read_write_round_trip() -> None:
    raw_text = _build_save_text(free_skill_points=2, unsupported_scalar=35, mastery_candidate=1)

    original = parse_save_text(raw_text)
    detected = detect_free_mastery_points(original)
    patch_result = apply_free_mastery_points_patch(original, new_value=4)
    updated = parse_save_text(patch_result.patched_text)
    updated_field = detect_free_mastery_points(updated)

    assert detected.value == 1
    assert patch_result.original_value == 1
    assert patch_result.updated_value == 4
    assert patch_result.changed_keys == ("c",)
    assert patch_result.changed_byte_offsets
    assert all(204 <= offset <= 211 for offset in patch_result.changed_byte_offsets)
    assert updated_field.value == 4
    assert original.decoded_json["a"] == updated.decoded_json["a"]


def _build_save_text(
    free_skill_points: int,
    unsupported_scalar: int,
    level: int = 70,
    mastery_candidate: int = 1,
) -> str:
    section_c = bytearray(409)
    struct.pack_into("<I", section_c, 0, 0x12F)
    struct.pack_into("<I", section_c, 4, 0x20)
    struct.pack_into("<d", section_c, 24, float(level))
    struct.pack_into("<d", section_c, 36, 11532.154737500394)
    struct.pack_into("<d", section_c, 48, float(free_skill_points))
    struct.pack_into("<d", section_c, 72, 2.0)
    struct.pack_into("<d", section_c, 96, 294.0)
    struct.pack_into("<f", section_c, 184, -1.875)
    struct.pack_into("<d", section_c, 192, float(unsupported_scalar))
    struct.pack_into("<d", section_c, 204, float(mastery_candidate))
    struct.pack_into("<d", section_c, 216, 5560.594737500267)
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
