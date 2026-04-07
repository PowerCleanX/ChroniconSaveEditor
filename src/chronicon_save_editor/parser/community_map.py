from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path

from chronicon_save_editor.models import CommunityMap, SectionMapping


def load_community_map(path: Path | None = None) -> CommunityMap:
    if path is None:
        resource = files("chronicon_save_editor.data").joinpath("field_map.json")
        raw_text = resource.read_text(encoding="utf-8")
    else:
        raw_text = path.read_text(encoding="utf-8")

    payload = json.loads(raw_text)
    sections = {
        key: SectionMapping(
            key=key,
            label=value.get("label", key),
            description=value.get("description", ""),
            confidence=value.get("confidence", "unknown"),
        )
        for key, value in payload.get("sections", {}).items()
    }
    return CommunityMap(
        sections=sections,
        fields=payload.get("fields", {}),
        affixes=payload.get("affixes", {}),
    )
