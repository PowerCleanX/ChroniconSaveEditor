# Chronicon Save Editor

[![Buy Me a Coffee](https://img.buymeacoffee.com/button-api/?text=Buy%20me%20a%20coffee&emoji=&slug=powerclean&button_colour=FFDD00&font_colour=000000&font_family=Arial&outline_colour=000000&coffee_colour=ffffff)](https://buymeacoffee.com/powerclean)

Unofficial fan-made desktop save editor for Chronicon.

Chronicon Save Editor is an open-source desktop app for inspecting and editing Chronicon save files with a focus on safe, minimal patching instead of blindly rewriting whole files.

Quick download for the latest release:
[github.com/PowerCleanX/ChroniconSaveEditor/releases/latest](https://github.com/PowerCleanX/ChroniconSaveEditor/releases/latest)

## What It Does

The current public release focuses on a small set of confirmed, safe edits:

- Character level
- Free skill points
- Free mastery points
- Equipped item numeric affix editing for mapped equipped items

The app creates a timestamped backup automatically when you open a save and validates patched saves before writing them back to disk.

## Save Discovery

On Windows, the file picker starts in `%LOCALAPPDATA%\Chronicon\save` when that folder exists.

If the default Chronicon save folder is not found, the app falls back to the normal file picker. The last opened folder is remembered for the next session.

## Portable Windows .exe

If you are using the portable release build:

1. Download `ChroniconSaveEditor.exe`.
2. Run the executable directly.
3. Open your `*.char` save file.
4. The app will create a backup automatically before loading the save.

The portable executable uses the same Editor and Inspector workflow as the source version.

## Run From Source

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .[dev]
python -m chronicon_save_editor
```

## Build The Portable .exe

Use the included build script:

```powershell
.\scripts\build_windows_portable.ps1
```

That script packages:

- the PySide6 runtime
- bundled application data such as `field_map.json`

Output:

```text
dist\ChroniconSaveEditor.exe
```

If you prefer the direct PyInstaller command:

```powershell
.venv\Scripts\python.exe -m PyInstaller `
  --noconfirm `
  --clean `
  --name ChroniconSaveEditor `
  --windowed `
  --onefile `
  --collect-all PySide6 `
  --collect-data chronicon_save_editor `
  src\chronicon_save_editor\__main__.py
```

## How To Use

1. Open a `*.char` save file.
2. Let the app create its automatic backup.
3. Use the `Editor` tab for normal editing.
4. Save character changes with `Apply Character Changes`.
5. Save equipped affix changes with `Save Affix`.
6. Review the success or failure message after each save.

The main window also keeps a short last-change summary so it is easy to confirm what was updated.

## Inspector Mode

`Inspector` is a secondary, advanced view for users who want low-level visibility into the save structure.

It includes:

- raw section browser
- raw JSON token view
- hex view
- ASCII preview
- printable-string extraction

Inspector stays disabled until `Advanced Mode` is explicitly enabled in the main window.

## Backups

Every time you open a save, the app creates a timestamped backup in a sibling `backups\` folder before loading the file.

That backup behavior is automatic and intended to make testing edits safer.

## Known Limitations

The current release does not yet support:

- Currency editing
- Inventory injection or duplication
- Mastery level editing
- Gem or socket editing
- Stash editing

If a field is not clearly mapped and safely patchable, it is intentionally left unsupported.

## Screenshots

Screenshots will be added here as the release presentation is polished further.

Suggested placeholders:

- Main Editor view
- Equipped item affix editor
- Inspector mode

## Roadmap

### Near term

- Better release polish and UI refinements
- Before/after diff views
- Additional safely confirmed scalar fields
- Better error messaging and recovery flow

### Later

- Currency editing once global/shared storage is confidently mapped
- Broader community-maintained field mappings
- More item editing once mappings are strongly validated

## Tests

```powershell
.venv\Scripts\python.exe -m pytest
```

## Project Layout

```text
src/chronicon_save_editor/
  data/                 Community-maintained mapping files
  parser/               Save parsing and exact-byte patch helpers
  services/             Backup and save-location helpers
  ui/                   PySide6 desktop UI
tests/                  Parser and service tests
scripts/                Build helpers
```

## Warning

This tool is unofficial and may break saves if used incorrectly.

Always keep manual backups of your original save files.

Use at your own risk.

## Legal / Disclaimer

- Unofficial fan-made project
- Not affiliated with the Chronicon developer
- Intended for personal use, experimentation, and save inspection/editing

## Support

If this tool saves you time and you want to support development, you can buy me a coffee here:

**Buy Me a Coffee:** [buymeacoffee.com/powerclean](https://buymeacoffee.com/powerclean)
