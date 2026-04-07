import pytest

from chronicon_save_editor.parser.json_container import (
    SaveFormatError,
    format_hex_dump,
    parse_save_text,
    patch_hex_bytes,
)


def test_parse_save_text_indexes_hex_sections_and_primitives() -> None:
    raw_text = '{ "a": "41424344", "name": "hero", "y": true }'

    container = parse_save_text(raw_text)

    assert container.entry_count == 3
    assert container.hex_section_count == 1
    assert container.entry_by_key("a") is not None
    assert container.entry_by_key("a").decoded_bytes == b"ABCD"
    assert container.entry_by_key("name").kind == "primitive"
    assert container.entry_by_key("y").raw_value is True


def test_parse_save_text_preserves_raw_token_span() -> None:
    raw_text = '{\n  "a": "41424344",\n  "y": false\n}'

    container = parse_save_text(raw_text)
    entry = container.entry_by_key("a")

    assert entry is not None
    token = container.raw_text[entry.span.token_start : entry.span.token_end]
    assert token == '"41424344"'
    assert entry.span.string_content_start is not None
    assert entry.span.string_content_end is not None


def test_patch_hex_bytes_rewrites_only_requested_region() -> None:
    raw_text = '{ "a": "41424344", "y": true }'
    container = parse_save_text(raw_text)

    patched = patch_hex_bytes(container, "a", byte_offset=1, new_bytes=b"ZZ")

    assert patched == '{ "a": "415A5A44", "y": true }'


def test_format_hex_dump_includes_offsets() -> None:
    dump = format_hex_dump(b"ABCDEFGH")

    assert "00000000" in dump
    assert "41 42 43 44 45 46 47 48" in dump


def test_invalid_json_raises_save_format_error() -> None:
    with pytest.raises(SaveFormatError):
        parse_save_text("{ invalid json }")
