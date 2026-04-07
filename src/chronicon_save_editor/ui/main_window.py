from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from chronicon_save_editor.models import BackupRecord, SaveContainer, SaveEntry
from chronicon_save_editor.parser import (
    EquippedItemError,
    LevelEditError,
    ProgressionEditError,
    SaveFormatError,
    apply_character_field_changes,
    apply_equipped_affix_patch,
    detect_character_level,
    detect_free_mastery_points,
    detect_free_skill_points,
    format_hex_dump,
    load_save_container,
    read_equipped_items,
)
from chronicon_save_editor.services import (
    LAST_OPEN_DIR_KEY,
    choose_initial_open_dir,
    create_timestamped_backup,
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Chronicon Save Editor")

        self._container: SaveContainer | None = None
        self._backup_record: BackupRecord | None = None
        self._settings = QSettings()

        self._open_button = QPushButton("Open Save")
        self._open_button.clicked.connect(self.open_file)

        self._reload_button = QPushButton("Reload")
        self._reload_button.clicked.connect(self.reload_current_file)
        self._reload_button.setEnabled(False)

        self._advanced_button = QPushButton("Advanced Mode: Off")
        self._advanced_button.setCheckable(True)
        self._advanced_button.toggled.connect(self._set_advanced_enabled)

        self._file_label = QLabel("No file loaded")
        self._backup_label = QLabel("Backup: n/a")
        self._validation_label = QLabel("Validation: n/a")
        self._last_change_label = QLabel("No edits applied in this session")
        self._last_change_label.setWordWrap(True)
        self._safety_label = QLabel(
            "Unofficial fan-made tool. Use at your own risk. "
            "A timestamped backup is created automatically whenever you open a save."
        )
        self._safety_label.setWordWrap(True)

        self._level_spin = QSpinBox()
        self._level_spin.setRange(1, 300)
        self._level_spin.setEnabled(False)

        self._apply_character_button = QPushButton("Apply Character Changes")
        self._apply_character_button.clicked.connect(self.apply_character_changes)
        self._apply_character_button.setEnabled(False)

        self._free_skill_points_spin = QSpinBox()
        self._free_skill_points_spin.setRange(0, 1000000)
        self._free_skill_points_spin.setEnabled(False)

        self._free_mastery_points_spin = QSpinBox()
        self._free_mastery_points_spin.setRange(0, 1000000)
        self._free_mastery_points_spin.setEnabled(False)

        self._character_status = QLabel("Character editor unavailable")
        self._character_status.setWordWrap(True)

        self._character_help = QLabel(
            "Edit confirmed character fields only. The app patches only the bytes for fields you changed "
            "and validates the save before it is written."
        )
        self._character_help.setWordWrap(True)

        self._equipped_item_tree = QTreeWidget()
        self._equipped_item_tree.setColumnCount(3)
        self._equipped_item_tree.setHeaderLabels(["Equipped Item", "Level", "Mapped Affixes"])
        self._equipped_item_tree.currentItemChanged.connect(self._handle_equipped_item_selection)

        self._affix_tree = QTreeWidget()
        self._affix_tree.setColumnCount(3)
        self._affix_tree.setHeaderLabels(["Affix", "Key", "Value"])
        self._affix_tree.currentItemChanged.connect(self._handle_affix_selection)

        self._selected_item_label = QLabel("No equipped item selected")
        self._selected_affix_label = QLabel("No affix selected")

        self._affix_spin = QDoubleSpinBox()
        self._affix_spin.setRange(-1000000000.0, 1000000000.0)
        self._affix_spin.setDecimals(4)
        self._affix_spin.setEnabled(False)

        self._save_affix_button = QPushButton("Save Affix")
        self._save_affix_button.clicked.connect(self.save_selected_affix)
        self._save_affix_button.setEnabled(False)

        self._affix_status = QLabel("Equipped item affix editor unavailable")
        self._affix_status.setWordWrap(True)
        self._equipped_help = QLabel(
            "Only mapped numeric affixes for equipped items are editable. "
            "Unknown item fields remain read-only."
        )
        self._equipped_help.setWordWrap(True)

        self._entry_tree = QTreeWidget()
        self._entry_tree.setColumnCount(4)
        self._entry_tree.setHeaderLabels(["Key", "Kind", "Size", "Map"])
        self._entry_tree.currentItemChanged.connect(self._handle_entry_selection)

        self._detail_title = QLabel("Select an entry")
        self._detail_kind = QLabel("-")
        self._detail_map = QLabel("-")
        self._detail_span = QLabel("-")
        self._detail_notes = QLabel("-")

        self._raw_json_view = QPlainTextEdit()
        self._raw_json_view.setReadOnly(True)

        self._hex_view = QPlainTextEdit()
        self._hex_view.setReadOnly(True)

        self._ascii_view = QPlainTextEdit()
        self._ascii_view.setReadOnly(True)

        self._strings_view = QPlainTextEdit()
        self._strings_view.setReadOnly(True)

        self._main_tabs = QTabWidget()
        self._build_ui()

    def _build_ui(self) -> None:
        self._main_tabs.addTab(self._build_editor_widget(), "Editor")
        inspector_index = self._main_tabs.addTab(self._build_inspector_widget(), "Inspector")
        self._main_tabs.setTabEnabled(inspector_index, False)

        self.setCentralWidget(self._main_tabs)
        self.statusBar().showMessage("Open a Chronicon save file to begin editing confirmed fields.")

    def _build_editor_widget(self) -> QWidget:
        toolbar_layout = QHBoxLayout()
        toolbar_layout.addWidget(self._open_button)
        toolbar_layout.addWidget(self._reload_button)
        toolbar_layout.addStretch(1)
        toolbar_layout.addWidget(self._advanced_button)

        status_group = QGroupBox("Session")
        status_layout = QFormLayout(status_group)
        status_layout.addRow("Save file", self._file_label)
        status_layout.addRow("Backup", self._backup_label)
        status_layout.addRow("Loaded state", self._validation_label)
        status_layout.addRow("Last change", self._last_change_label)

        character_widget = QGroupBox("Character")
        character_layout = QVBoxLayout(character_widget)

        character_form = QFormLayout()
        character_form.addRow("Character level", self._level_spin)
        character_form.addRow("Free skill points", self._free_skill_points_spin)
        character_form.addRow("Free mastery points", self._free_mastery_points_spin)
        character_form.addRow("", self._apply_character_button)
        character_form.addRow("Status", self._character_status)
        character_layout.addLayout(character_form)
        character_layout.addWidget(self._character_help)

        equipped_editor_layout = QFormLayout()
        equipped_editor_layout.addRow("Selected item", self._selected_item_label)
        equipped_editor_layout.addRow("Selected affix", self._selected_affix_label)
        equipped_editor_layout.addRow("Affix value", self._affix_spin)
        equipped_editor_layout.addRow("", self._save_affix_button)
        equipped_editor_layout.addRow("Status", self._affix_status)

        equipped_affix_widget = QWidget()
        equipped_affix_layout = QVBoxLayout(equipped_affix_widget)
        equipped_affix_layout.addWidget(self._affix_tree)
        equipped_affix_layout.addLayout(equipped_editor_layout)
        equipped_affix_layout.addWidget(self._equipped_help)

        equipped_splitter = QSplitter(Qt.Orientation.Horizontal)
        equipped_splitter.addWidget(self._equipped_item_tree)
        equipped_splitter.addWidget(equipped_affix_widget)
        equipped_splitter.setStretchFactor(0, 2)
        equipped_splitter.setStretchFactor(1, 3)

        editor_sections = QTabWidget()
        editor_sections.addTab(character_widget, "Character")
        editor_sections.addTab(equipped_splitter, "Equipped Items")

        editor_widget = QWidget()
        editor_layout = QVBoxLayout(editor_widget)
        editor_layout.addLayout(toolbar_layout)
        editor_layout.addWidget(self._safety_label)
        editor_layout.addWidget(status_group)
        editor_layout.addWidget(editor_sections)
        return editor_widget

    def _build_inspector_widget(self) -> QWidget:
        detail_header_layout = QFormLayout()
        detail_header_layout.addRow("Entry", self._detail_title)
        detail_header_layout.addRow("Kind", self._detail_kind)
        detail_header_layout.addRow("Mapping", self._detail_map)
        detail_header_layout.addRow("JSON span", self._detail_span)
        detail_header_layout.addRow("Notes", self._detail_notes)

        detail_tabs = QTabWidget()
        detail_tabs.addTab(self._raw_json_view, "Raw JSON")
        detail_tabs.addTab(self._hex_view, "Hex")
        detail_tabs.addTab(self._ascii_view, "ASCII")
        detail_tabs.addTab(self._strings_view, "Printable Strings")

        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)
        detail_layout.addLayout(detail_header_layout)
        detail_layout.addWidget(detail_tabs)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._entry_tree)
        splitter.addWidget(detail_widget)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        inspector_widget = QWidget()
        inspector_layout = QVBoxLayout(inspector_widget)
        inspector_layout.addWidget(
            QLabel("Inspector mode exposes the raw section browser and low-level payload views.")
        )
        inspector_layout.addWidget(splitter)
        return inspector_widget

    def open_file(self) -> None:
        last_open_dir = self._settings.value(LAST_OPEN_DIR_KEY, "", type=str)
        initial_dir = choose_initial_open_dir(last_open_dir)
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Chronicon Save",
            str(initial_dir),
            "Chronicon Save (*.char);;All Files (*)",
        )
        if not file_path:
            return

        self._open_save(Path(file_path))

    def reload_current_file(self) -> None:
        if self._container is None:
            return
        self._open_save(self._container.source_path)

    def _open_save(self, path: Path) -> None:
        try:
            backup_record = create_timestamped_backup(path)
            container = load_save_container(path)
        except (OSError, SaveFormatError) as exc:
            QMessageBox.critical(self, "Open Failed", str(exc))
            return

        self._settings.setValue(LAST_OPEN_DIR_KEY, str(path.parent))
        self._backup_record = backup_record
        self._container = container
        self._reload_button.setEnabled(True)

        self._file_label.setText(str(container.source_path))
        self._backup_label.setText(str(backup_record.backup_path))
        self._validation_label.setText("Loaded and validated")
        self._last_change_label.setText("No edits applied since this file was opened")

        self._sync_character_editor()
        self._sync_equipped_items()
        self._populate_entry_tree(container)
        self.statusBar().showMessage(f"Loaded {path.name}. Backup created automatically.")

    def apply_character_changes(self) -> None:
        if self._container is None:
            return

        try:
            current_level = detect_character_level(self._container)
            current_skill_points = detect_free_skill_points(self._container)
            current_mastery_points = detect_free_mastery_points(self._container)
        except (LevelEditError, ProgressionEditError) as exc:
            self._sync_character_editor(error_message=str(exc))
            QMessageBox.critical(self, "Character Save Failed", str(exc))
            return

        requested_level = int(self._level_spin.value())
        requested_skill_points = int(self._free_skill_points_spin.value())
        requested_mastery_points = int(self._free_mastery_points_spin.value())
        if (
            requested_level == current_level.value
            and requested_skill_points == current_skill_points.value
            and requested_mastery_points == current_mastery_points.value
        ):
            message = "Character fields are unchanged."
            self._character_status.setText(message)
            QMessageBox.information(self, "Character Unchanged", message)
            return

        try:
            patch_result = apply_character_field_changes(
                self._container,
                new_level=requested_level,
                new_free_skill_points=requested_skill_points,
                new_free_mastery_points=requested_mastery_points,
            )
            self._container.source_path.write_text(patch_result.patched_text, encoding="utf-8")
            self._container = load_save_container(self._container.source_path)
        except (LevelEditError, ProgressionEditError, OSError, SaveFormatError) as exc:
            message = f"Character save failed: {exc}"
            self._character_status.setText(message)
            QMessageBox.critical(self, "Character Save Failed", message)
            return

        self._file_label.setText(str(self._container.source_path))
        self._validation_label.setText("Saved and validated")
        self._populate_entry_tree(self._container)
        self._sync_character_editor()

        field_summaries = ", ".join(
            f"{update.label} {update.original_value} -> {update.updated_value}"
            for update in patch_result.updated_fields
        )
        message = f"Updated {field_summaries}."
        self._character_status.setText(message)
        self._last_change_label.setText(message)
        self.statusBar().showMessage(message)
        QMessageBox.information(self, "Character Saved", message)

    def save_selected_affix(self) -> None:
        if self._container is None:
            return

        item_widget = self._equipped_item_tree.currentItem()
        affix_widget = self._affix_tree.currentItem()
        if item_widget is None or affix_widget is None:
            message = "Select an equipped item and one mapped affix before saving."
            self._affix_status.setText(message)
            QMessageBox.information(self, "Affix Save Unavailable", message)
            return

        record_index = int(item_widget.data(0, Qt.ItemDataRole.UserRole))
        affix_key = str(affix_widget.data(0, Qt.ItemDataRole.UserRole))
        current_value = float(affix_widget.data(2, Qt.ItemDataRole.UserRole))
        requested_value = float(self._affix_spin.value())

        if requested_value == current_value:
            message = "The selected affix value is unchanged."
            self._affix_status.setText(message)
            QMessageBox.information(self, "Affix Unchanged", message)
            return

        try:
            patch_result = apply_equipped_affix_patch(
                container=self._container,
                record_index=record_index,
                affix_key=affix_key,
                new_value=requested_value,
            )
            self._container.source_path.write_text(patch_result.patched_text, encoding="utf-8")
            self._container = load_save_container(self._container.source_path)
        except (EquippedItemError, OSError, SaveFormatError) as exc:
            message = f"Affix save failed: {exc}"
            self._affix_status.setText(message)
            QMessageBox.critical(self, "Affix Save Failed", message)
            return

        self._file_label.setText(str(self._container.source_path))
        self._validation_label.setText("Saved and validated")
        self._sync_character_editor()
        self._sync_equipped_items(selected_record_index=record_index, selected_affix_key=affix_key)
        self._populate_entry_tree(self._container)

        message = (
            f"Updated {patch_result.item_name} -> {affix_key} "
            f"from {patch_result.original_value:g} to {patch_result.updated_value:g}."
        )
        self._affix_status.setText(message)
        self._last_change_label.setText(message)
        self.statusBar().showMessage(message)
        QMessageBox.information(self, "Affix Saved", message)

    def _set_advanced_enabled(self, enabled: bool) -> None:
        self._advanced_button.setText("Advanced Mode: On" if enabled else "Advanced Mode: Off")
        self._main_tabs.setTabEnabled(1, enabled)
        if not enabled and self._main_tabs.currentIndex() == 1:
            self._main_tabs.setCurrentIndex(0)

    def _populate_entry_tree(self, container: SaveContainer) -> None:
        self._entry_tree.clear()
        for entry in container.entries:
            item = QTreeWidgetItem(
                [
                    entry.key,
                    entry.kind,
                    entry.size_text,
                    entry.mapping.label if entry.mapping else "Unmapped",
                ]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, entry.key)
            self._entry_tree.addTopLevelItem(item)

        if self._entry_tree.topLevelItemCount() > 0:
            self._entry_tree.setCurrentItem(self._entry_tree.topLevelItem(0))

    def _sync_character_editor(self, error_message: str | None = None) -> None:
        if self._container is None:
            self._level_spin.setEnabled(False)
            self._free_skill_points_spin.setEnabled(False)
            self._free_mastery_points_spin.setEnabled(False)
            self._apply_character_button.setEnabled(False)
            self._character_status.setText(error_message or "No save loaded")
            return

        try:
            level_field = detect_character_level(self._container)
            skill_field = detect_free_skill_points(self._container)
            mastery_field = detect_free_mastery_points(self._container)
        except (LevelEditError, ProgressionEditError) as exc:
            self._level_spin.setEnabled(False)
            self._free_skill_points_spin.setEnabled(False)
            self._free_mastery_points_spin.setEnabled(False)
            self._apply_character_button.setEnabled(False)
            self._character_status.setText(error_message or str(exc))
            return

        self._level_spin.blockSignals(True)
        self._level_spin.setValue(level_field.value)
        self._level_spin.blockSignals(False)
        self._level_spin.setEnabled(True)
        self._free_skill_points_spin.blockSignals(True)
        self._free_skill_points_spin.setValue(skill_field.value)
        self._free_skill_points_spin.blockSignals(False)
        self._free_skill_points_spin.setEnabled(True)
        self._free_mastery_points_spin.blockSignals(True)
        self._free_mastery_points_spin.setValue(mastery_field.value)
        self._free_mastery_points_spin.blockSignals(False)
        self._free_mastery_points_spin.setEnabled(True)
        self._apply_character_button.setEnabled(True)
        self._character_status.setText(
            f"Ready to save. Current values: level {level_field.value}, "
            f"free skill points {skill_field.value}, free mastery points {mastery_field.value}."
        )

    def _sync_equipped_items(
        self,
        error_message: str | None = None,
        selected_record_index: int | None = None,
        selected_affix_key: str | None = None,
    ) -> None:
        self._equipped_item_tree.clear()
        self._affix_tree.clear()
        self._selected_item_label.setText("No equipped item selected")
        self._selected_affix_label.setText("No affix selected")
        self._affix_spin.setEnabled(False)
        self._save_affix_button.setEnabled(False)

        if self._container is None:
            self._affix_status.setText(error_message or "No save loaded")
            return

        try:
            items = read_equipped_items(self._container)
        except EquippedItemError as exc:
            self._affix_status.setText(error_message or str(exc))
            return

        for item in items:
            widget = QTreeWidgetItem(
                [
                    item.name,
                    str(item.level) if item.level is not None else "-",
                    str(len(item.affixes)),
                ]
            )
            widget.setData(0, Qt.ItemDataRole.UserRole, item.record_index)
            self._equipped_item_tree.addTopLevelItem(widget)
            if selected_record_index is not None and item.record_index == selected_record_index:
                self._equipped_item_tree.setCurrentItem(widget)

        if self._equipped_item_tree.currentItem() is None and self._equipped_item_tree.topLevelItemCount() > 0:
            self._equipped_item_tree.setCurrentItem(self._equipped_item_tree.topLevelItem(0))

        if selected_affix_key and self._affix_tree.topLevelItemCount() > 0:
            for index in range(self._affix_tree.topLevelItemCount()):
                widget = self._affix_tree.topLevelItem(index)
                if str(widget.data(0, Qt.ItemDataRole.UserRole)) == selected_affix_key:
                    self._affix_tree.setCurrentItem(widget)
                    break

        if items:
            self._affix_status.setText(
                f"Loaded {len(items)} equipped items with mapped numeric affixes."
            )
        else:
            self._affix_status.setText("No equipped items with mapped editable affixes were detected.")

    def _handle_entry_selection(
        self,
        current: QTreeWidgetItem | None,
        previous: QTreeWidgetItem | None,
    ) -> None:
        del previous
        if current is None or self._container is None:
            return

        key = current.data(0, Qt.ItemDataRole.UserRole)
        entry = self._container.entry_by_key(str(key))
        if entry is None:
            return

        self._show_entry_details(entry)

    def _handle_equipped_item_selection(
        self,
        current: QTreeWidgetItem | None,
        previous: QTreeWidgetItem | None,
    ) -> None:
        del previous
        self._affix_tree.clear()
        self._selected_affix_label.setText("No affix selected")
        self._affix_spin.setEnabled(False)
        self._save_affix_button.setEnabled(False)

        if current is None or self._container is None:
            self._selected_item_label.setText("No equipped item selected")
            return

        record_index = int(current.data(0, Qt.ItemDataRole.UserRole))
        try:
            items = read_equipped_items(self._container)
        except EquippedItemError as exc:
            self._selected_item_label.setText("Unable to read equipped items")
            self._affix_status.setText(str(exc))
            return

        item = next((candidate for candidate in items if candidate.record_index == record_index), None)
        if item is None:
            self._selected_item_label.setText("Unknown equipped item")
            return

        level_text = str(item.level) if item.level is not None else "-"
        self._selected_item_label.setText(f"{item.name} (level {level_text})")
        for affix in item.affixes:
            affix_widget = QTreeWidgetItem(
                [
                    affix.label,
                    affix.key,
                    f"{affix.value:g}",
                ]
            )
            affix_widget.setData(0, Qt.ItemDataRole.UserRole, affix.key)
            affix_widget.setData(1, Qt.ItemDataRole.UserRole, affix.decimals)
            affix_widget.setData(2, Qt.ItemDataRole.UserRole, affix.value)
            self._affix_tree.addTopLevelItem(affix_widget)

        if self._affix_tree.topLevelItemCount() > 0:
            self._affix_tree.setCurrentItem(self._affix_tree.topLevelItem(0))

    def _handle_affix_selection(
        self,
        current: QTreeWidgetItem | None,
        previous: QTreeWidgetItem | None,
    ) -> None:
        del previous
        if current is None:
            self._selected_affix_label.setText("No affix selected")
            self._affix_spin.setEnabled(False)
            self._save_affix_button.setEnabled(False)
            return

        affix_key = str(current.data(0, Qt.ItemDataRole.UserRole))
        decimals = int(current.data(1, Qt.ItemDataRole.UserRole))
        value = float(current.data(2, Qt.ItemDataRole.UserRole))

        self._selected_affix_label.setText(affix_key)
        self._affix_spin.setDecimals(decimals)
        self._affix_spin.blockSignals(True)
        self._affix_spin.setValue(value)
        self._affix_spin.blockSignals(False)
        self._affix_spin.setEnabled(True)
        self._save_affix_button.setEnabled(True)

    def _show_entry_details(self, entry: SaveEntry) -> None:
        self._detail_title.setText(entry.key)
        self._detail_kind.setText(entry.kind)
        self._detail_map.setText(entry.mapping.label if entry.mapping else "Unmapped")
        self._detail_span.setText(f"{entry.span.token_start}..{entry.span.token_end}")
        self._detail_notes.setText(" | ".join(entry.notes) if entry.notes else "-")

        if self._container is None:
            return

        raw_token = self._container.raw_text[entry.span.token_start : entry.span.token_end]
        self._raw_json_view.setPlainText(raw_token)

        if entry.decoded_bytes is None:
            self._hex_view.setPlainText("(not a hex section)")
            self._ascii_view.setPlainText(str(entry.raw_value))
            self._strings_view.setPlainText("(not a hex section)")
            return

        self._hex_view.setPlainText(format_hex_dump(entry.decoded_bytes))
        self._ascii_view.setPlainText(_format_ascii_preview(entry.decoded_bytes))
        self._strings_view.setPlainText(
            "\n".join(entry.printable_strings) if entry.printable_strings else "(none)"
        )


def _format_ascii_preview(payload: bytes, max_bytes: int = 512) -> str:
    window = payload[:max_bytes]
    characters = []
    for byte in window:
        characters.append(chr(byte) if 32 <= byte <= 126 else ".")

    preview = "".join(characters)
    if len(payload) > max_bytes:
        preview += f"\n... truncated, showing {max_bytes} of {len(payload)} bytes"
    return preview
