from pathlib import Path

from chronicon_save_editor.services.backup import create_timestamped_backup, rollback_backup


def test_create_timestamped_backup_copies_source(tmp_path: Path) -> None:
    source = tmp_path / "hero.char"
    source.write_text('{ "b": "41424344", "y": true }', encoding="utf-8")

    backup = create_timestamped_backup(source)

    assert backup.source_path == source
    assert backup.backup_path.exists()
    assert backup.backup_path.parent.name == "backups"
    assert backup.backup_path.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")


def test_rollback_backup_restores_contents(tmp_path: Path) -> None:
    source = tmp_path / "hero.char"
    backup_path = tmp_path / "hero.char.20260406-220000.bak"

    source.write_text("mutated", encoding="utf-8")
    backup_path.write_text("original", encoding="utf-8")

    rollback_backup(backup_path, source)

    assert source.read_text(encoding="utf-8") == "original"

