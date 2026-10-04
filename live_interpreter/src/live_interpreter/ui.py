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

from .api_probe import friendly_model_access_error, probe_model_access
from .audio import list_input_devices, list_output_devices
from .config import APP_NAME, ENGINE_MODES, LANGUAGES, DirectionConfig, load_api_key
from .engine import DirectionEvents, TranslationDirection
from .local_engine import probe_local_engine


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
        self.resize(1180, 790)
        self.settings = QSettings("Aleksey341", APP_NAME)
        self.bus = UiBus()
        self.bus.status.connect(self._on_status)
        self.bus.source_text.connect(self._append_source)
        self.bus.target_text.connect(self._append_target)
        self.bus.error.connect(self._show_error)
        self._remote_direction: TranslationDirection | None = None
        self._local_direction: TranslationDirection | None = None
        self._resolved_engine = ""

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
        self.engine_combo = QComboBox()
        for label, value in ENGINE_MODES.items():
            self.engine_combo.addItem(label, value)
        self.engine_combo.setToolTip(
            "Авто: использовать OpenAI Realtime, если модель доступна; иначе переключиться на локальный каскад."
        )
        self.global_status = QLabel("● READY")
        self.global_status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        title_row.addWidget(title)
        title_row.addStretch(1)
        title_row.addWidget(QLabel("Движок"))
        title_row.addWidget(self.engine_combo)
        title_row.addWidget(self.global_status)
        layout.addLayout(title_row)

        hint = QLabel(
            "OpenAI Realtime даёт минимальную задержку. Локальный каскад работает без API: "
            "faster-whisper → NLLB → Piper. В режиме Авто приложение само выбирает доступный движок."
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

        privacy = QLabel(
            "По умолчанию приложение не сохраняет аудио и текст разговора на диск. "
            "Local работает на компьютере; OpenAI отправляет аудио в Realtime API."
        )
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
        widgets = DirectionWidgets(
            enabled,
            input_combo,
            output_combo,
            lang_combo,
            status,
            QPlainTextEdit(),
            QPlainTextEdit(),
        )
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

    def _direction_config(self, label: str, w: DirectionWidgets, engine: str) -> DirectionConfig:
        return DirectionConfig(
            enabled=w.enabled.isChecked(),
            input_device_name=str(w.input_device.currentData() or ""),
            output_device_name=str(w.output_device.currentData() or ""),
            target_language=LANGUAGES[w.target_language.currentText()],
            label=label,
            engine=engine,
        )

    def _events(self, key: str) -> DirectionEvents:
        return DirectionEvents(
            on_status=lambda s: self.bus.status.emit(key, s),
            on_source_text=lambda t: self.bus.source_text.emit(key, t),
            on_target_text=lambda t: self.bus.target_text.emit(key, t),
            on_error=lambda e: self.bus.error.emit(e),
        )

    def _enabled_target_languages(self) -> tuple[str, ...]:
        result: list[str] = []
        for widgets in (self.remote_widgets, self.local_widgets):
            if widgets.enabled.isChecked():
                result.append(LANGUAGES[widgets.target_language.currentText()])
        return tuple(result)

    def _resolve_engine(self) -> tuple[str | None, str]:
        requested = str(self.engine_combo.currentData() or "auto")
        api_key = load_api_key()

        if requested == "openai":
            if not api_key:
                return None, "Для OpenAI Realtime нужен OPENAI_API_KEY в live_interpreter/.env."
            self.global_status.setText("● CHECKING OPENAI")
            QApplication.processEvents()
            probe = probe_model_access(api_key)
            if probe.available is False:
                return None, friendly_model_access_error(probe) + f"\n\nТехнически: {probe.display}"
            return "openai", "OpenAI Realtime"

        local_report = probe_local_engine(self._enabled_target_languages())
        if requested == "local":
            if not local_report.available:
                return None, local_report.detail
            return "local", local_report.detail

        # Auto: OpenAI first when a key exists and the model is actually available.
        openai_detail = "OPENAI_API_KEY не задан"
        if api_key:
            self.global_status.setText("● AUTO · CHECKING OPENAI")
            QApplication.processEvents()
            probe = probe_model_access(api_key)
            if probe.available is True:
                return "openai", "Auto выбрал OpenAI Realtime."
            openai_detail = friendly_model_access_error(probe) if probe.available is False else probe.display

        if local_report.available:
            return "local", "Auto переключился на Local. " + local_report.detail

        return None, (
            "Автоматический выбор не нашёл рабочего движка.\n\n"
            f"OpenAI: {openai_detail}\n"
            f"Local: {local_report.detail}"
        )

    @Slot()
    def start_translation(self) -> None:
        self._save_settings()
        if not self.remote_widgets.enabled.isChecked() and not self.local_widgets.enabled.isChecked():
            QMessageBox.warning(self, "Нет каналов", "Включите хотя бы одно направление перевода.")
            return

        resolved_engine, detail = self._resolve_engine()
        if not resolved_engine:
            self.global_status.setText("● ENGINE UNAVAILABLE")
            QMessageBox.critical(self, "Движок перевода недоступен", detail)
            return

        self._resolved_engine = resolved_engine
        if self.engine_combo.currentData() == "auto" and resolved_engine == "local":
            QMessageBox.information(self, "Auto → Local", detail)

        remote_cfg = self._direction_config("Собеседник → Вы", self.remote_widgets, resolved_engine)
        local_cfg = self._direction_config("Вы → Собеседник", self.local_widgets, resolved_engine)
        api_key = load_api_key() if resolved_engine == "openai" else ""

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.refresh_btn.setEnabled(False)
        self.engine_combo.setEnabled(False)
        self.global_status.setText("● CONNECTING" if resolved_engine == "openai" else "● LOCAL · LOADING")
        QApplication.processEvents()
        try:
            if remote_cfg.enabled:
                self._remote_direction = TranslationDirection(api_key, remote_cfg, self._events("remote"))
                self._remote_direction.start()
            if local_cfg.enabled:
                self._local_direction = TranslationDirection(api_key, local_cfg, self._events("local"))
                self._local_direction.start()
            if resolved_engine == "openai":
                self.global_status.setText("● ONLINE · OPENAI")
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
        self._resolved_engine = ""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.refresh_btn.setEnabled(True)
        self.engine_combo.setEnabled(True)
        self.global_status.setText("● READY")

    @Slot(str, str)
    def _on_status(self, key: str, status: str) -> None:
        w = self.remote_widgets if key == "remote" else self.local_widgets
        labels = {
            "local-loading": "local: загрузка",
            "local-loading-asr": "local: Whisper",
            "local-loading-translation": "local: NLLB",
            "local-online": "local: online",
            "local-text-only": "local: только текст",
        }
        w.status.setText(labels.get(status, status))
        if status == "local-online":
            self.global_status.setText("● ONLINE · LOCAL")
        elif status == "local-text-only":
            self.global_status.setText("● LOCAL · TEXT ONLY")
        elif status in {"error", "offline"}:
            self.global_status.setText("● ERROR" if status == "error" else "● OFFLINE")

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
        self.settings.setValue("engine", self.engine_combo.currentData() or "auto")
        for prefix, w in (("remote", self.remote_widgets), ("local", self.local_widgets)):
            self.settings.setValue(f"{prefix}/enabled", w.enabled.isChecked())
            self.settings.setValue(f"{prefix}/input", w.input_device.currentData() or "")
            self.settings.setValue(f"{prefix}/output", w.output_device.currentData() or "")
            self.settings.setValue(f"{prefix}/language", w.target_language.currentText())

    def _restore_settings(self) -> None:
        engine = self.settings.value("engine", "auto")
        i = self.engine_combo.findData(engine)
        if i >= 0:
            self.engine_combo.setCurrentIndex(i)
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
