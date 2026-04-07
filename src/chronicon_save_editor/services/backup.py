from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil

from chronicon_save_editor.models import BackupRecord


def create_timestamped_backup(source_path: Path, backup_root: Path | None = None) -> BackupRecord:
    backup_directory = backup_root or source_path.parent / "backups"
    backup_directory.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup_path = backup_directory / f"{source_path.name}.{timestamp}.bak"
    shutil.copy2(source_path, backup_path)
    return BackupRecord(source_path=source_path, backup_path=backup_path)


def rollback_backup(backup_path: Path, target_path: Path) -> None:
    shutil.copy2(backup_path, target_path)
