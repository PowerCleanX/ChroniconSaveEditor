# Chronicon Save Editor

Unofficial fan-made desktop save editor for Chronicon.

Chronicon Save Editor is an open-source utility for inspecting and editing Chronicon save files with a focus on **safe, minimal patching** rather than blindly rewriting whole files. The goal is to make common edits easier for players while reducing the risk of corrupting saves.

## Status

Early project / concept stage.

Planned focus:
- safe save backups before any edit
- read-only inspection mode first
- support for common edits such as level, currencies, and selected item affix values
- before/after diff view
- advanced mode for risky or experimental edits

## Goals

- Make Chronicon save editing accessible to normal players
- Preserve saves by patching only the bytes that actually need to change
- Keep the parser and UI separate so the community can improve field mappings over time
- Build a transparent editor that shows exactly what changed

## Planned Features

### Safe editing
- Automatic timestamped backup when opening a save
- Validation before save
- Rollback from backup
- Warnings for unknown or risky edits

### Inspector tools
- Read-only save overview
- Character summary
- Item and affix inspection
- Field-level and hex-level diff viewer

### First editable fields
- Character level
- Gold and crystals, where detected
- Known item affix numeric values
- Additional progression values as mappings are confirmed

### Advanced mode
- Hidden behind an explicit toggle
- For experimental fields not yet fully mapped
- Designed for experienced users who accept the risks

## Design Principles

- **Back up first**
- **Patch minimally**
- **Show the diff**
- **Warn clearly**
- **Do not pretend unknown data is safe**

## Tech Stack

Planned stack:
- **Python**
- **PySide6** for desktop UI

Project structure should keep:
- parser logic
- field mapping definitions
- validation logic
- UI

cleanly separated.

## Community Mapping

A long-term goal is to support community-maintained mappings for:
- save sections
- character fields
- item affixes
- numeric value types

This should make it easier to expand the editor without rewriting the application each time a new field is identified.

## Installation

Not yet available.

When the first version is ready, installation instructions for Windows will be added here.

## Usage

Not yet available.

Planned basic workflow:
1. Open a `.char` save file
2. Automatic backup is created
3. Inspect detected fields
4. Make safe edits
5. Review before/after diff
6. Save patched file
7. Test in game

## Warning

This tool is unofficial and may break saves if used incorrectly.

Always keep manual backups of your original save files.

Use at your own risk.

## Legal / Disclaimer

- Unofficial fan-made project
- Not affiliated with the Chronicon developer
- Intended for personal use, experimentation, and save inspection/editing

If the Chronicon developer has any concerns about this project, please open an issue.

## Contributing

Contributions are welcome once the initial parser and UI scaffold are in place.

Likely contribution areas:
- parser improvements
- field identification
- affix mapping
- testing against known-good saves
- UI improvements
- packaging and release workflow

## Roadmap

### Phase 1
- Project scaffold
- Save loading
- Backup creation
- Read-only inspector

### Phase 2
- Character level editing
- Diff viewer
- Validation checks

### Phase 3
- Currency editing
- Known item affix editing
- Better error handling

### Phase 4
- Community mapping support
- Advanced mode
- Release packaging

## Support

If this tool saves you time and you want to support development, you can buy me a coffee here:

**Buy Me a Coffee:** [Add your link here](https://example.com)

## License

Suggested license: **MIT**

If you prefer community improvements to remain open, you could instead use **GPL-3.0**.
