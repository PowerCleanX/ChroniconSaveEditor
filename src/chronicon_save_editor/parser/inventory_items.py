from __future__ import annotations

import binascii
from dataclasses import dataclass
import struct

from chronicon_save_editor.models import SaveContainer
from chronicon_save_editor.parser.equipped_items import _parse_item_record


INVENTORY_SECTION_KEY = "i"
OUTER_RECORD_HEADER_LENGTH = 20
TRAILING_PADDING_LENGTH = 12


class InventoryItemError(ValueError):
    """Raised when inventory slot parsing fails."""


@dataclass(frozen=True)
class InventorySlotRecord:
    slot_index: int
    outer_record_offset: int
    header_words: tuple[int, int, int, int, int]
    slot_hint_word: int
    record_length: int
    is_occupied: bool
    item_name: str | None
    quantity: int | None
    level: int | None
    item_id: int | None


@dataclass(frozen=True)
class InventoryDuplicationAssessment:
    source_slot_index: int
    target_slot_index: int
    can_duplicate_safely: bool
    reason: str
    source_record_length: int
    target_record_length: int


def read_inventory_slots(container: SaveContainer) -> tuple[InventorySlotRecord, ...]:
    entry = container.entry_by_key(INVENTORY_SECTION_KEY)
    if entry is None or entry.kind != "hex_section" or entry.decoded_bytes is None:
        raise InventoryItemError("Inventory section 'i' is missing or not decodable.")

    outer = entry.decoded_bytes
    if len(outer) < OUTER_RECORD_HEADER_LENGTH:
        raise InventoryItemError("Inventory section 'i' is too short to contain slot records.")

    slot_count = struct.unpack_from("<I", outer, 4)[0]
    slots: list[InventorySlotRecord] = []
    outer_offset = 0

    for slot_index in range(slot_count):
        if outer_offset + OUTER_RECORD_HEADER_LENGTH > len(outer):
            raise InventoryItemError("Inventory section ended before all slot records were parsed.")

        header_words = struct.unpack_from("<IIIII", outer, outer_offset)
        record_length = header_words[4]
        record_ascii_offset = outer_offset + OUTER_RECORD_HEADER_LENGTH
        record_ascii_end = record_ascii_offset + record_length
        if record_ascii_end > len(outer):
            raise InventoryItemError("Inventory slot record extends past the end of section 'i'.")

        item_name: str | None = None
        quantity: int | None = None
        level: int | None = None
        item_id: int | None = None

        if record_length > 0:
            try:
                inner = binascii.unhexlify(outer[record_ascii_offset:record_ascii_end])
            except binascii.Error as exc:
                raise InventoryItemError("Inventory slot record did not contain valid inner hex.") from exc

            parsed_fields = _parse_item_record(inner)
            field_lookup = {field.key: field for field in parsed_fields}
            name_field = field_lookup.get("name")
            if name_field is not None and isinstance(name_field.value, str):
                item_name = name_field.value

            quantity_field = field_lookup.get("qt")
            if quantity_field is not None:
                quantity = _float_to_int(quantity_field.value)

            level_field = field_lookup.get("level")
            if level_field is not None:
                level = _float_to_int(level_field.value)

            id_field = field_lookup.get("id")
            if id_field is not None:
                item_id = _float_to_int(id_field.value)

        slots.append(
            InventorySlotRecord(
                slot_index=slot_index,
                outer_record_offset=outer_offset,
                header_words=header_words,
                slot_hint_word=header_words[2],
                record_length=record_length,
                is_occupied=record_length > 0,
                item_name=item_name,
                quantity=quantity,
                level=level,
                item_id=item_id,
            )
        )
        outer_offset = record_ascii_end

    trailing = outer[outer_offset:]
    if trailing and any(byte != 0 for byte in trailing):
        raise InventoryItemError("Inventory section contains unexpected non-zero trailing bytes.")
    if trailing and len(trailing) != TRAILING_PADDING_LENGTH:
        raise InventoryItemError(
            f"Inventory section trailing padding was {len(trailing)} bytes; expected {TRAILING_PADDING_LENGTH}."
        )

    return tuple(slots)


def find_first_empty_inventory_slot(
    slots: tuple[InventorySlotRecord, ...],
) -> InventorySlotRecord | None:
    hinted_slots = [slot for slot in slots if not slot.is_occupied and slot.slot_hint_word != 0]
    if hinted_slots:
        return hinted_slots[0]

    for slot in slots:
        if not slot.is_occupied:
            return slot
    return None


def assess_inventory_duplication(
    container: SaveContainer,
    *,
    source_slot_index: int,
    target_slot_index: int,
) -> InventoryDuplicationAssessment:
    slots = read_inventory_slots(container)
    try:
        source_slot = slots[source_slot_index]
        target_slot = slots[target_slot_index]
    except IndexError as exc:
        raise InventoryItemError("Requested inventory slot index is out of range.") from exc

    if not source_slot.is_occupied:
        raise InventoryItemError(f"Inventory slot {source_slot_index} is empty.")
    if target_slot.is_occupied:
        raise InventoryItemError(f"Inventory slot {target_slot_index} is already occupied.")

    return InventoryDuplicationAssessment(
        source_slot_index=source_slot_index,
        target_slot_index=target_slot_index,
        can_duplicate_safely=False,
        reason=(
            "Empty inventory slots in section 'i' are stored as zero-length inline records. "
            "Duplicating a full item into one would require expanding section 'i' and shifting "
            "the later slot headers, so this injector remains disabled."
        ),
        source_record_length=source_slot.record_length,
        target_record_length=target_slot.record_length,
    )


def _float_to_int(value: object) -> int | None:
    if not isinstance(value, float):
        return None
    if not value.is_integer():
        return None
    return int(value)
