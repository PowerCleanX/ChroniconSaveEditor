from pathlib import Path

from chronicon_save_editor.services.save_paths import (
    choose_initial_open_dir,
    discover_chronicon_save_dir,
)


def test_discover_chronicon_save_dir_prefers_localappdata(monkeypatch, tmp_path: Path) -> None:
    save_dir = tmp_path / "Chronicon" / "save"
    save_dir.mkdir(parents=True)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    discovered = discover_chronicon_save_dir()

    assert discovered == save_dir


def test_choose_initial_open_dir_uses_last_open_dir_when_it_exists(tmp_path: Path) -> None:
    last_dir = tmp_path / "last"
    last_dir.mkdir()

    chosen = choose_initial_open_dir(str(last_dir))

    assert chosen == last_dir


def test_choose_initial_open_dir_falls_back_to_discovered_save_dir(
    monkeypatch,
    tmp_path: Path,
) -> None:
    save_dir = tmp_path / "Chronicon" / "save"
    save_dir.mkdir(parents=True)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    chosen = choose_initial_open_dir(last_open_dir="")

    assert chosen == save_dir
