from __future__ import annotations

from dataclasses import dataclass
import sys

from PySide6.QtCore import QObject, QSettings, Signal, Slot, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .audio import list_input_devices, list_output_devices
from .config import APP_NAME, LANGUAGES, DirectionConfig, load_api_key
from .engine import DirectionEvents, TranslationDirection


class UiBus(QObject):
    status = Signal(str, str)
    source_text = Signal(str, str)
    target_text = Signal(str, str)
    error = Signal(str)


@dataclass(slots=True)
class DirectionWidgets:
    enabled: QCheckBox
    input_device: QComboBox
    output_device: QComboBox
    target_language: QComboBox
    status: QLabel
    source_text: QPlainTextEdit
    target_text: QPlainTextEdit


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("LiveInterpreter")
        self.resize(1180, 760)
        self.settings = QSettings("Aleksey341", APP_NAME)
        self.bus = UiBus()
        self.bus.status.connect(self._on_status)
        self.bus.source_text.connect(self._append_source)
        self.bus.target_text.connect(self._append_target)
        self.bus.error.connect(self._show_error)
        self._remote_direction: TranslationDirection | None = None
        self._local_direction: TranslationDirection | None = None

        self._inputs = list_input_devices()
        self._outputs = list_output_devices()
        self._build_ui()
        self._restore_settings()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title_row = QHBoxLayout()
        title = QLabel("LIVE INTERPRETER")
        title.setStyleSheet("font-size: 22px; font-weight: 800;")
        self.global_status = QLabel("● READY")
        self.global_status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        title_row.addWidget(title)
        title_row.addStretch(1)
        title_row.addWidget(self.global_status)
        layout.addLayout(title_row)

        hint = QLabel(
            "Два независимых канала перевода. Источник языка определяется автоматически, вы выбираете только язык перевода."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        controls = QGridLayout()
        self.remote = self._direction_box("remote", "Собеседник → Вы", "Русский")
        self.local = self._direction_box("local", "Вы → Собеседник", "English")
        controls.addWidget(self.remote[0], 0, 0)
        controls.addWidget(self.local[0], 0, 1)
        layout.addLayout(controls)

        self.remote_widgets = self.remote[1]
        self.local_widgets = self.local[1]

        buttons = QHBoxLayout()
        self.refresh_btn = QPushButton("Обновить устройства")
        self.refresh_btn.clicked.connect(self._refresh_devices)
        self.start_btn = QPushButton("▶ Начать перевод")
        self.start_btn.clicked.connect(self.start_translation)
        self.stop_btn = QPushButton("■ Остановить")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_translation)
        buttons.addWidget(self.refresh_btn)
        buttons.addStretch(1)
        buttons.addWidget(self.stop_btn)
        buttons.addWidget(self.start_btn)
        layout.addLayout(buttons)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._transcript_box("Собеседник → Вы", self.remote_widgets))
        splitter.addWidget(self._transcript_box("Вы → Собеседник", self.local_widgets))
        splitter.setSizes([580, 580])
        layout.addWidget(splitter, 1)

        privacy = QLabel("По умолчанию приложение не сохраняет аудио и текст разговора на диск.")
        privacy.setStyleSheet("color:#777;")
        layout.addWidget(privacy)
        self.setCentralWidget(root)

    def _direction_box(self, key: str, title: str, default_lang_name: str):
        box = QGroupBox(title)
        form = QFormLayout(box)
        enabled = QCheckBox("Включён")
        enabled.setChecked(True)
        input_combo = QComboBox()
        output_combo = QComboBox()
        lang_combo = QComboBox()
        lang_combo.addItems(LANGUAGES.keys())
        idx = lang_combo.findText(default_lang_name)
        if idx >= 0:
            lang_combo.setCurrentIndex(idx)
        status = QLabel("ready")
        status.setStyleSheet("font-weight:700;")
        self._fill_input_combo(input_combo)
        self._fill_output_combo(output_combo)
        form.addRow("Канал", enabled)
        form.addRow("Вход", input_combo)
        form.addRow("Выход", output_combo)
        form.addRow("Переводить на", lang_combo)
        form.addRow("Статус", status)
        widgets = DirectionWidgets(enabled, input_combo, output_combo, lang_combo, status, QPlainTextEdit(), QPlainTextEdit())
        return box, widgets

    def _transcript_box(self, title: str, widgets: DirectionWidgets) -> QWidget:
        box = QGroupBox(title)
        layout = QVBoxLayout(box)
        layout.addWidget(QLabel("Оригинал"))
        widgets.source_text.setReadOnly(True)
        widgets.source_text.setPlaceholderText("Здесь появится распознанная исходная речь…")
        layout.addWidget(widgets.source_text, 1)
        layout.addWidget(QLabel("Перевод"))
        widgets.target_text.setReadOnly(True)
        widgets.target_text.setPlaceholderText("Здесь появится текст перевода…")
        layout.addWidget(widgets.target_text, 1)
        return box

    def _fill_input_combo(self, combo: QComboBox) -> None:
        current = combo.currentData() if combo.count() else None
        combo.clear()
        for d in self._inputs:
            combo.addItem(d.display_name, d.name)
        if current:
            idx = combo.findData(current)
            if idx >= 0:
                combo.setCurrentIndex(idx)

    def _fill_output_combo(self, combo: QComboBox) -> None:
        current = combo.currentData() if combo.count() else None
        combo.clear()
        for d in self._outputs:
            combo.addItem(d.display_name, d.name)
        if current:
            idx = combo.findData(current)
            if idx >= 0:
                combo.setCurrentIndex(idx)

    def _refresh_devices(self) -> None:
        self._inputs = list_input_devices()
        self._outputs = list_output_devices()
        for widgets in (self.remote_widgets, self.local_widgets):
            self._fill_input_combo(widgets.input_device)
            self._fill_output_combo(widgets.output_device)

    def _direction_config(self, key: str, label: str, w: DirectionWidgets) -> DirectionConfig:
        return DirectionConfig(
            enabled=w.enabled.isChecked(),
            input_device_name=str(w.input_device.currentData() or ""),
            output_device_name=str(w.output_device.currentData() or ""),
            target_language=LANGUAGES[w.target_language.currentText()],
            label=label,
        )

    def _events(self, key: str) -> DirectionEvents:
        return DirectionEvents(
            on_status=lambda s: self.bus.status.emit(key, s),
            on_source_text=lambda t: self.bus.source_text.emit(key, t),
            on_target_text=lambda t: self.bus.target_text.emit(key, t),
            on_error=lambda e: self.bus.error.emit(e),
        )

    @Slot()
    def start_translation(self) -> None:
        api_key = load_api_key()
        if not api_key:
            QMessageBox.critical(
                self,
                "OPENAI_API_KEY не найден",
                "Создайте live_interpreter/.env по образцу .env.example и укажите OPENAI_API_KEY.",
            )
            return
        self._save_settings()
        remote_cfg = self._direction_config("remote", "Собеседник → Вы", self.remote_widgets)
        local_cfg = self._direction_config("local", "Вы → Собеседник", self.local_widgets)
        if not remote_cfg.enabled and not local_cfg.enabled:
            QMessageBox.warning(self, "Нет каналов", "Включите хотя бы одно направление перевода.")
            return
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.refresh_btn.setEnabled(False)
        self.global_status.setText("● CONNECTING")
        QApplication.processEvents()
        try:
            if remote_cfg.enabled:
                self._remote_direction = TranslationDirection(api_key, remote_cfg, self._events("remote"))
                self._remote_direction.start()
            if local_cfg.enabled:
                self._local_direction = TranslationDirection(api_key, local_cfg, self._events("local"))
                self._local_direction.start()
            self.global_status.setText("● ONLINE")
        except Exception as exc:
            self._show_error(str(exc))
            self.stop_translation()

    @Slot()
    def stop_translation(self) -> None:
        self.global_status.setText("● STOPPING")
        QApplication.processEvents()
        for direction in (self._remote_direction, self._local_direction):
            if direction:
                try:
                    direction.stop()
                except Exception as exc:
                    self.bus.error.emit(str(exc))
        self._remote_direction = None
        self._local_direction = None
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.refresh_btn.setEnabled(True)
        self.global_status.setText("● READY")

    @Slot(str, str)
    def _on_status(self, key: str, status: str) -> None:
        w = self.remote_widgets if key == "remote" else self.local_widgets
        w.status.setText(status)

    @Slot(str, str)
    def _append_source(self, key: str, text: str) -> None:
        w = self.remote_widgets if key == "remote" else self.local_widgets
        cursor = w.source_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        w.source_text.setTextCursor(cursor)
        w.source_text.ensureCursorVisible()

    @Slot(str, str)
    def _append_target(self, key: str, text: str) -> None:
        w = self.remote_widgets if key == "remote" else self.local_widgets
        cursor = w.target_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        w.target_text.setTextCursor(cursor)
        w.target_text.ensureCursorVisible()

    @Slot(str)
    def _show_error(self, message: str) -> None:
        QMessageBox.critical(self, "LiveInterpreter", message)

    def _save_settings(self) -> None:
        for prefix, w in (("remote", self.remote_widgets), ("local", self.local_widgets)):
            self.settings.setValue(f"{prefix}/enabled", w.enabled.isChecked())
            self.settings.setValue(f"{prefix}/input", w.input_device.currentData() or "")
            self.settings.setValue(f"{prefix}/output", w.output_device.currentData() or "")
            self.settings.setValue(f"{prefix}/language", w.target_language.currentText())

    def _restore_settings(self) -> None:
        for prefix, w in (("remote", self.remote_widgets), ("local", self.local_widgets)):
            w.enabled.setChecked(self.settings.value(f"{prefix}/enabled", True, bool))
            input_name = self.settings.value(f"{prefix}/input", "")
            output_name = self.settings.value(f"{prefix}/output", "")
            lang = self.settings.value(f"{prefix}/language", w.target_language.currentText())
            i = w.input_device.findData(input_name)
            if i >= 0:
                w.input_device.setCurrentIndex(i)
            i = w.output_device.findData(output_name)
            if i >= 0:
                w.output_device.setCurrentIndex(i)
            i = w.target_language.findText(lang)
            if i >= 0:
                w.target_language.setCurrentIndex(i)

    def closeEvent(self, event) -> None:
        self._save_settings()
        self.stop_translation()
        event.accept()


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    window = MainWindow()
    window.show()
    return app.exec()
