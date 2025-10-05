from PyQt5.QtWidgets import QDialog, QLabel, QComboBox, QPushButton, QVBoxLayout, QHBoxLayout, QFrame, QWidget
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
import random


class BlackScreenTimerWindow(QDialog):
    """
    Full-black, frameless cue window synced to TimingEngine.
    Safeties:
      - Opening cancels and resets any active run, freezes timeline visuals, disables dashboard Record/Stop
      - Closing cancels and resets, unfreezes visuals, re-enables Record/Stop
      - Record/Stop inside this dialog call the same handlers as the dashboard

    Symbols:
      - '✚' anticipation when trial_time < 0
      - chosen cue on trial_time crossing 0
      - '⬛' during buffer
      - '✅' after final trial
      - '⚙️' idle when engine not active
      - '🛑' stop when active run or recording
    """

    def __init__(self, timing_engine, before_spinbox=None, timeline_widget=None, parent=None):
        super().__init__(parent)
        self.engine = timing_engine
        self.before_spinbox = before_spinbox
        self.timeline_widget = timeline_widget

        # state
        self._prev_trial_time_ms = None
        self._current_phase = "idle"
        self._current_trial_index = -1
        self._finished = False

        # cue options
        self.cue_map = {
            "Right (→)": "→",
            "Left (←)": "←",
            "Up (↑)": "↑",
            "Down (↓)": "↓",
            "Go (🟢)": "🟢",
        }

        self._build_ui()
        self._wire_engine()

    def _build_ui(self):
        # Standard window with close/min/max controls
        self.setWindowFlags(Qt.Window | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle("Black Screen Timer")
        # Global font + controls styling (Montserrat SemiBold, compact sizes)
        self.setStyleSheet(
            """
            background-color: black;
            font-family: 'Montserrat SemiBold';
            font-size: 10pt;

            QPushButton {
                color: white;
                background: rgba(255,255,255,0.10);
                border: 1px solid rgba(255,255,255,0.25);
                border-radius: 8px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.18);
                border-color: rgba(255,255,255,0.35);
            }
            QPushButton:pressed {
                background: rgba(255,255,255,0.28);
                padding-top: 7px;
                padding-bottom: 5px;
            }

            QComboBox {
                color: white;
                background: rgba(255,255,255,0.10);
                border: 1px solid rgba(255,255,255,0.25);
                border-radius: 8px;
                padding: 4px 8px;
            }
            QComboBox:hover {
                background: rgba(255,255,255,0.18);
                border-color: rgba(255,255,255,0.35);
            }
            QComboBox:pressed {
                background: rgba(255,255,255,0.28);
            }
            QComboBox QAbstractItemView {
                color: white;
                background: #111111;
                selection-background-color: rgba(255,255,255,0.25);
                selection-color: white;
                border: 1px solid rgba(255,255,255,0.25);
            }
            """
        )
        self.setModal(False)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # center symbol
        center = QWidget(self)
        center.setAttribute(Qt.WA_StyledBackground, True)
        center.setStyleSheet("background: black;")
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setAlignment(Qt.AlignCenter)

        self.symbol = QLabel("⚙️", center)
        
        self.symbol.setStyleSheet("color: white; font-size: 250px;")
        self.symbol.setAlignment(Qt.AlignCenter)
        center_layout.addWidget(self.symbol)

        # bottom-left area: legend + config + record/stop controls with collapsible panel
        bl = QFrame(self)
        bl.setFrameShape(QFrame.NoFrame)
        bl_layout = QHBoxLayout(bl)
        bl_layout.setContentsMargins(20, 20, 20, 20)
        bl_layout.setAlignment(Qt.AlignLeft | Qt.AlignBottom)

        legend = QFrame(bl)
        legend_layout = QVBoxLayout(legend)
        legend_layout.setContentsMargins(12, 12, 12, 12)
        legend.setStyleSheet("color: white; background: rgba(255,255,255,0.07); border-radius: 6px;")
        legend_title = QLabel("ℹ️ Legend", legend)
        legend_title.setStyleSheet("color: white; font-size: 10pt;")
        legend_layout.addWidget(legend_title)
        for txt in [
            "✚  = Anticipation (trial_time < 0)",
            "⬛ = Buffer between trials",
            "✅ = Completed",
            "⚙️ = Idle (no active trials)",
            "🛑 = Stop (when active run or recording)",

        ]:
            lbl = QLabel(txt, legend)
            lbl.setStyleSheet("color: white; font-size: 8pt;")
            legend_layout.addWidget(lbl)

        config = QFrame(bl)
        config_layout = QVBoxLayout(config)
        config_layout.setContentsMargins(12, 12, 12, 12)
        config.setStyleSheet("color: white; background: rgba(255,255,255,0.07); border-radius: 6px;")
        cfg_title = QLabel("Cue Configuration", config)
        cfg_title.setStyleSheet("color: white; font-size: 10pt;")
        config_layout.addWidget(cfg_title)

        self.odd_combo = QComboBox(config)
        self.even_combo = QComboBox(config)
        for k in self.cue_map.keys():
            self.odd_combo.addItem(k)
            self.even_combo.addItem(k)
        self.odd_combo.setCurrentText("Right (→)")
        self.even_combo.setCurrentText("Left (←)")

        self.order_combo = QComboBox(config)
        self.order_combo.addItems(["Alternating", "Fixed", "Random"])
        self.order_combo.setCurrentText("Alternating")

        odd_lbl = QLabel("Odd Trials:", config)
        odd_lbl.setStyleSheet("font-size: 8pt;")
        config_layout.addWidget(odd_lbl)
        config_layout.addWidget(self.odd_combo)
        even_lbl = QLabel("Even Trials:", config)
        even_lbl.setStyleSheet("font-size: 8pt;")
        config_layout.addWidget(even_lbl)
        config_layout.addWidget(self.even_combo)
        order_lbl = QLabel("Order:", config)
        order_lbl.setStyleSheet("font-size: 8pt;")
        config_layout.addWidget(order_lbl)
        config_layout.addWidget(self.order_combo)

        # record/stop controls
        controls = QFrame(bl)
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(12, 12, 12, 12)
        controls.setStyleSheet("color: white; background: rgba(255,255,255,0.07); border-radius: 6px;")

        self.btn_record = QPushButton("Record", controls)
        # Inherit dialog-level QPushButton hover/press styles
        self.btn_stop = QPushButton("Stop", controls)
        # Per-button stylesheet: lighten on hover and shrink slightly when pressed
        button_style = (
            "QPushButton {"
            "  color: white;"
            "  background: rgba(255,255,255,0.12);"
            "  border: 1px solid rgba(255,255,255,0.30);"
            "  border-radius: 8px;"
            "  padding: 6px 12px;"
            "  font-family: 'Montserrat SemiBold';"
            "  font-size: 10pt;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(255,255,255,0.20);"
            "  border-color: rgba(255,255,255,0.40);"
            "}"
            "QPushButton:pressed {"
            "  background: rgba(255,255,255,0.28);"
            "  padding: 5px 11px;"
            "  font-size: 9.5pt;"
            "}"
        )
        try:
            self.btn_record.setStyleSheet(button_style)
            self.btn_stop.setStyleSheet(button_style)
        except Exception:
            pass
        self.btn_record.clicked.connect(self._on_click_record)
        self.btn_stop.clicked.connect(self._on_click_stop)
        for b in (self.btn_record, self.btn_stop):
            b.setCursor(Qt.PointingHandCursor)
        # Removed redundant 'Controls' label per request
        controls_layout.addWidget(self.btn_record)
        controls_layout.addWidget(self.btn_stop)

        # Collapsible container holding legend + config + controls horizontally
        panel_container = QFrame(bl)
        panel_container_layout = QHBoxLayout(panel_container)
        panel_container_layout.setContentsMargins(0, 0, 0, 0)
        panel_container_layout.setSpacing(12)
        panel_container_layout.addWidget(legend)
        panel_container_layout.addWidget(config)
        panel_container_layout.addWidget(controls)

        # Toggle button to show/hide the panel
        self.panel_visible = True
        self.panel_toggle_btn = QPushButton("Hide panel", bl)
        try:
            self.panel_toggle_btn.setStyleSheet(
                "QPushButton { font-size: 9pt; padding: 3px 8px;color: white; }"
            )
        except Exception:
            pass

        def toggle_panel():
            self.panel_visible = not self.panel_visible
            panel_container.setVisible(self.panel_visible)
            self.panel_toggle_btn.setText("Hide panel" if self.panel_visible else "Show panel")
            self.panel_toggle_btn.setStyleSheet("QPushButton { font-size: 9pt; padding: 3px 8px;color: white; }")

        self.panel_toggle_btn.clicked.connect(toggle_panel)

        # Stack toggle button above the panel in a vertical holder
        left_column = QFrame(bl)
        left_column_layout = QVBoxLayout(left_column)
        left_column_layout.setContentsMargins(0, 0, 0, 0)
        left_column_layout.setSpacing(6)
        left_column_layout.addWidget(self.panel_toggle_btn)
        left_column_layout.addWidget(panel_container)

        bl_layout.addWidget(left_column)

        root.addWidget(center, 1)
        root.addWidget(bl, 0, alignment=Qt.AlignLeft | Qt.AlignBottom)

    def _wire_engine(self):
        try:
            self.engine.tick_8ms.connect(self._on_tick)
            self.engine.phase_changed.connect(self._on_phase_changed)
            self.engine.run_completed.connect(self._on_run_completed)
            self.engine.trial_started.connect(self._on_trial_started)
            self.engine.state_changed.connect(self._on_state_changed)
        except Exception:
            pass

    # ——— Lifecycle ———
    def showEvent(self, e):
        super().showEvent(e)

        # Mutual exclusion: if a run is active, cancel/reset before entering cue mode
        try:
            parent = self.parent()
            if getattr(self.engine, "run_active", False) and hasattr(parent, "stop_all_and_reset"):
                parent.stop_all_and_reset()
        except Exception:
            pass

        # Freeze timeline visuals while dialog exists (even if minimized/hidden)
        try:
            if self.timeline_widget is not None:
                self.timeline_widget.setUpdatesEnabled(False)
                if hasattr(self.timeline_widget, "view"):
                    self.timeline_widget.view.setUpdatesEnabled(False)
        except Exception:
            pass

        # Disable main Record/Stop to avoid race conditions while open
        try:
            parent = self.parent()
            if parent and hasattr(parent, "recordButton") and parent.recordButton:
                parent.recordButton.setEnabled(False)
            if parent and hasattr(parent, "stopButton") and parent.stopButton:
                parent.stopButton.setEnabled(False)
        except Exception:
            pass

        self._current_phase = getattr(self.engine, "phase", "idle")
        self._current_trial_index = getattr(self.engine, "trial_index", -1)
        self._prev_trial_time_ms = self._compute_trial_time_ms()
        # Ensure we allow updates for a fresh session
        self._finished = False
        self._on_state_changed(getattr(self.engine, "run_active", False), getattr(self.engine, "recording_enabled", False))

    def closeEvent(self, e):
        # Treat close as STOP in all cases
        try:
            parent = self.parent()
            if hasattr(parent, "stop_all_and_reset"):
                # Only show stop status if something was active
                was_run_active = bool(getattr(parent, 'timing_engine', None) and parent.timing_engine.run_active)
                was_recording = bool(getattr(parent, 'recording_manager', None) and parent.recording_manager.is_recording)
                parent.stop_all_and_reset()
                if not (was_run_active or was_recording):
                    try:
                        if hasattr(parent, 'StatusBar') and parent.StatusBar is not None:
                            parent.StatusBar.setText("")
                    except Exception:
                        pass
        except Exception:
            pass

        # Unfreeze timeline visuals and re-enable dashboard controls ONLY when closed
        try:
            if self.timeline_widget is not None:
                if hasattr(self.timeline_widget, "view"):
                    self.timeline_widget.view.setUpdatesEnabled(True)
                self.timeline_widget.setUpdatesEnabled(True)
            parent = self.parent()
            if parent and hasattr(parent, "recordButton") and parent.recordButton is not None:
                parent.recordButton.setEnabled(True)
            if parent and hasattr(parent, "stopButton") and parent.stopButton is not None:
                parent.stopButton.setEnabled(True)
        except Exception:
            pass

        # Disconnect signals
        try:
            self.engine.tick_8ms.disconnect(self._on_tick)
            self.engine.phase_changed.disconnect(self._on_phase_changed)
            self.engine.run_completed.disconnect(self._on_run_completed)
            self.engine.trial_started.disconnect(self._on_trial_started)
            self.engine.state_changed.disconnect(self._on_state_changed)
        except Exception:
            pass
        return super().closeEvent(e)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    # ——— Button actions ———
    def _on_click_record(self):
        # Use the same pipeline as the dashboard
        try:
            parent = self.parent()
            if parent and hasattr(parent, "handle_record_button"):
                parent.handle_record_button()
        except Exception:
            pass

    def _on_click_stop(self):
        try:
            parent = self.parent()
            # Determine whether a run/recording was active before stopping
            was_run_active = bool(getattr(parent, 'timing_engine', None) and parent.timing_engine.run_active) if parent else False
            was_recording = bool(getattr(parent, 'recording_manager', None) and parent.recording_manager.is_recording) if parent else False
            if parent and hasattr(parent, "handle_stop_button"):
                parent.handle_stop_button()
            # Show temporary red octagon only if something was active
            if was_run_active or was_recording:
                self._set_symbol("🛑")
                QTimer.singleShot(2000, lambda: self._set_symbol("⚙️"))
        except Exception:
            pass

    # ——— Engine callbacks ———
    def _on_state_changed(self, run_active: bool, recording_enabled: bool):
        # Keep buttons sensible
        try:
            self.btn_record.setEnabled(not run_active)
            self.btn_stop.setEnabled(run_active)
        except Exception:
            pass
        if run_active:
            # New run started, ensure we resume updates
            self._finished = False
        if not run_active:
            self._set_symbol("⚙️")

    def _on_trial_started(self, idx: int):
        self._current_trial_index = int(idx)
        # Reset finished flag and baseline at the start of each trial
        self._finished = False
        self._prev_trial_time_ms = self._compute_trial_time_ms()

    def _on_phase_changed(self, phase: str, trial_index: int):
        self._current_phase = phase
        self._current_trial_index = int(trial_index)
        if phase == "buffer":
            self._set_symbol("⬛")
        elif phase == "trial":
            # Entering a trial should allow updates again
            self._finished = False
            self._update_symbol_for_trial_time()
        else:
            self._set_symbol("⚙️")

    def _on_run_completed(self):
        self._finished = True
        self._set_symbol("✅")
        # After showing completion briefly, revert back to idle gear
        try:
            QTimer.singleShot(2000, lambda: self._set_symbol("⚙️"))
        except Exception:
            pass

    def _on_tick(self, now_ms: int, sched_ms: int):
        if self._finished:
            return
        if not bool(getattr(self.engine, "run_active", False)):
            self._set_symbol("⚙️")
            return
        if self._current_phase == "buffer":
            self._set_symbol("⬛")
            return
        if self._current_phase == "trial":
            self._update_symbol_for_trial_time()

    # ——— Cue logic ———
    def _compute_trial_time_ms(self) -> int:
        try:
            trial_elapsed_ms = int(self.engine.get_trial_elapsed_ms())
        except Exception:
            trial_elapsed_ms = 0
        try:
            before_s = int(self.engine.before_s)
        except Exception:
            before_s = int(self.before_spinbox.value()) if self.before_spinbox is not None else 0
        return trial_elapsed_ms - (before_s * 1000)

    def _update_symbol_for_trial_time(self):
        current_ms = self._compute_trial_time_ms()
        prev_ms = self._prev_trial_time_ms
        self._prev_trial_time_ms = current_ms
        if current_ms < 0:
            self._set_symbol("✚")
            return
        if prev_ms is None or (prev_ms < 0 <= current_ms):
            cue = self._select_cue_for_trial(self._current_trial_index)
            self._set_symbol(cue)

    def _select_cue_for_trial(self, trial_index: int) -> str:
        mode = self.order_combo.currentText()
        odd_choice = self.cue_map.get(self.odd_combo.currentText(), "→")
        even_choice = self.cue_map.get(self.even_combo.currentText(), "←")
        if mode == "Fixed":
            return odd_choice
        if mode == "Random":
            return random.choice(list(self.cue_map.values()))
        one_based = int(trial_index) + 1
        return odd_choice if (one_based % 2 == 1) else even_choice

    def _set_symbol(self, s: str):
        if self.symbol.text() != s:
            self.symbol.setText(s)


