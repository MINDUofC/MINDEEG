from PyQt5.QtCore import QObject, QTimer, QElapsedTimer, Qt, pyqtSignal


class TimingEngine(QObject):
    tick_8ms = pyqtSignal(int, int)            # now_ms, sched_ms
    state_changed = pyqtSignal(bool, bool)     # run_active, recording_enabled
    phase_changed = pyqtSignal(str, int)       # phase, trial_index
    trial_started = pyqtSignal(int)
    run_completed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.global_timer = QElapsedTimer()
        self.trial_timer = QElapsedTimer()

        self._timer = QTimer()
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.timeout.connect(self._on_tick)
        self._interval_ms = 8  # 125 Hz

        # State
        self.run_active = False
        self.recording_enabled = False
        self.phase = "idle"  # "trial" | "buffer" | "idle"
        self.trial_index = -1
        self.total_trials = 0
        self.before_s = 0
        self.after_s = 0
        self.buffer_s = 0

        # Schedule bookkeeping
        self._initialized = False
        self._sched_start_ms = 0
        self._trial_sched_start_ms = 0
        self._buffer_sched_start_ms = 0
        self._tick_count = 0

    def configure_run(self, *, before_s: int, after_s: int, buffer_s: int, total_trials: int):
        self.before_s = int(before_s)
        self.after_s = int(after_s)
        self.buffer_s = int(buffer_s)
        self.total_trials = int(total_trials)

    def start(self, recording_enabled: bool):
        self.recording_enabled = bool(recording_enabled)
        # Always reset the run schedule baseline so global runs are per-run
        if not self._initialized:
            self.global_timer.start()
            self._initialized = True
        now_ms = self.global_timer.elapsed()
        self._sched_start_ms = now_ms
        self._tick_count = 0

        self.trial_index = 0
        self._start_trial(now_ms)
        self.run_active = True
        self.state_changed.emit(self.run_active, self.recording_enabled)
        self.phase_changed.emit(self.phase, self.trial_index)

        if not self._timer.isActive():
            self._timer.start(self._interval_ms)
            QTimer.singleShot(0, lambda: self._emit_tick(self.global_timer.elapsed()))

    def stop(self):
        if self._timer.isActive():
            self._timer.stop()
        if self.run_active:
            self.run_active = False
            self.phase = "idle"
            self.state_changed.emit(self.run_active, self.recording_enabled)
            self.run_completed.emit()

    def _start_trial(self, now_ms: int):
        self.phase = "trial"
        self.trial_timer.start()
        self._trial_sched_start_ms = now_ms
        self.trial_started.emit(self.trial_index)

    def _start_buffer(self, now_ms: int):
        self.phase = "buffer"
        self._buffer_sched_start_ms = now_ms

    def _emit_tick(self, now_ms: int):
        sched_ms = self._sched_start_ms + (self._tick_count * self._interval_ms)
        self.tick_8ms.emit(now_ms, sched_ms)

    def _on_tick(self):
        now_ms = self.global_timer.elapsed()
        self._emit_tick(now_ms)
        self._tick_count += 1

        if not self.run_active:
            return

        if self.phase == "trial":
            elapsed_s = self.trial_timer.elapsed() / 1000.0
            if elapsed_s >= (self.before_s + self.after_s):
                self.trial_index += 1
                if self.trial_index >= self.total_trials:
                    self.stop()
                else:
                    self._start_buffer(now_ms)
                    self.phase_changed.emit(self.phase, self.trial_index)
        elif self.phase == "buffer":
            buf_elapsed_s = (now_ms - self._buffer_sched_start_ms) / 1000.0
            if buf_elapsed_s >= self.buffer_s:
                self._start_trial(now_ms)
                self.phase_changed.emit(self.phase, self.trial_index)

    # Public helpers for consumers
    def get_run_elapsed_ms(self) -> int:
        if not self._initialized:
            return 0
        now_ms = self.global_timer.elapsed()
        # Elapsed relative to the current run's schedule start
        return max(0, now_ms - self._sched_start_ms)

    def get_trial_elapsed_ms(self) -> int:
        # Directly from the shared trial timer
        return int(self.trial_timer.elapsed())


