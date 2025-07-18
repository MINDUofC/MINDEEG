import sys
import logging
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QGraphicsView, \
    QGraphicsScene, QGraphicsRectItem, QGraphicsLineItem, QGraphicsTextItem
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QColor, QBrush, QPen, QFont
from PyQt5.QtCore import QElapsedTimer
from GUI_Development.backend_logic import backend_eeg as beeg

# —————————————————————————————————————————————————————————————
# Configure logging: debug output to console
logging.basicConfig(level=logging.DEBUG,
                    format='[%(levelname)s] %(asctime)s %(message)s',
                    datefmt='%H:%M:%S')
# —————————————————————————————————————————————————————————————

class TimelineWidget(QWidget):
    # ─── INIT ────────────────────────────────────────────────────────────────
    def __init__(self, recordButton, stopButton,
                 beforeOnset, afterOnset,
                 buffer, numTrials, status_bar):
        super().__init__()
        # Make the whole widget transparent
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent; border: none;")

        # Build UI
        self.initUI(recordButton, stopButton,
                    beforeOnset, afterOnset,
                    buffer, numTrials, status_bar)

    # ─── INITIALIZATION AND GRAPHICAL SETUP ────────────────────────────────────
    def initUI(self, recordButton, stopButton,
               beforeOnset, afterOnset,
               buffer, numTrials, status_bar):
        layout = QVBoxLayout()

        # Total elapsed time label (updates every tick)
        self.global_time_label = QLabel("Total Time: 0s (Buffer)", self)
        self.global_time_label.setAlignment(Qt.AlignRight)
        self.global_time_label.setStyleSheet(
            "font-size: 16px; font-family: 'Montserrat ExtraBold'; color: black;")
        layout.addWidget(self.global_time_label)

        # Per‑trial time label (relative to movement onset)
        self.trial_time_label = QLabel("Trial 1 Time: 0s", self)
        self.trial_time_label.setAlignment(Qt.AlignRight)
        self.trial_time_label.setStyleSheet(
            "font-size: 16px; font-family: 'Montserrat ExtraBold'; color: black;")
        layout.addWidget(self.trial_time_label)

        # Precise timers for logging and animations
        self.global_timer = QElapsedTimer()   # wall‑clock for whole run + buffers
        self.global_time_data = []            # store (timestamp, label)

        self.trial_timer = QElapsedTimer()    # resets at each trial start
        self.trial_time_data = []             # store (timestamp, trial#)

        # Movement‑onset indicator (text only)
        self.label = QLabel("Movement Onset at 0s", self)
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)

        # Hook up your record/stop buttons
        self.start_button = recordButton
        self.start_button.clicked.connect(lambda: self.start_animation(status_bar))
        self.stop_button  = stopButton
        self.stop_button.clicked.connect(lambda: self.sudden_stop(status_bar))

        # State vars
        self.in_trial    = False
        self.trial_count = numTrials
        self.trial_count.setText("5")

        self.buffer_time = buffer
        self.buffer_time.setValue(3)

        # Onset window controls
        self.time_before = beforeOnset
        self.time_before.setValue(3)
        self.time_before.valueChanged.connect(self.update_markers)

        self.time_after  = afterOnset
        self.time_after.setValue(3)
        self.time_after.valueChanged.connect(self.update_markers)

        # Graphics view & scene for timeline
        self.view  = QGraphicsView(self)
        self.scene = QGraphicsScene(self)
        self.view.setScene(self.scene)
        layout.addWidget(self.view)

        # ─── prevent scrollbars from cutting off content ─────────────────
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Precise update timer for progress & labels
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(lambda: self.update_progress(status_bar))

        # Init trial indices & pixel progress
        self.trial_number = 0
        self.progress     = 0.0

        # Timeline geometry
        self.timeline_width  = 1300
        self.timeline_height = 80
        self.timeline_x      = 50
        self.timeline_y      = 200

        # Draw background bar
        self.background_rect = QGraphicsRectItem(
            self.timeline_x, self.timeline_y,
            self.timeline_width, self.timeline_height
        )
        self.background_rect.setBrush(QBrush(QColor(220, 220, 220)))
        self.scene.addItem(self.background_rect)

        # Draw fill bar (blue)
        self.fill_rect = QGraphicsRectItem(
            self.timeline_x, self.timeline_y, 0, self.timeline_height
        )
        self.fill_rect.setBrush(QBrush(QColor(50, 150, 250)))
        self.scene.addItem(self.fill_rect)

        # Center “0 s” line
        self.center_line = QGraphicsLineItem(
            self.timeline_x,
            self.timeline_y + self.timeline_height / 2,
            self.timeline_x + self.timeline_width,
            self.timeline_y + self.timeline_height / 2
        )
        self.center_line.setPen(QPen(QColor(0, 0, 0), 2))
        self.scene.addItem(self.center_line)

        # Markers for each second
        self.markers = []
        self.update_markers()

        # Buffer countdown label (red)
        self.buffer_label_display = QLabel("", self)
        self.buffer_label_display.setAlignment(Qt.AlignCenter)
        self.buffer_label_display.setStyleSheet(
            "font-size: 20px; font-family: 'Montserrat ExtraBold'; color: red;")
        self.buffer_label_display.setMinimumHeight(30)
        layout.addWidget(self.buffer_label_display)

        # Manually position all labels (unchanged logic)
        label_width  = 250
        label_height = 35
        self.global_time_label.setGeometry(
            self.timeline_x + self.timeline_width - 292,
            self.global_time_label.y() + 120,
            label_width, label_height
        )
        self.trial_time_label.setGeometry(
            self.timeline_x + self.timeline_width - 292,
            140, label_width, label_height
        )
        self.label.setGeometry(
            self.timeline_x + self.timeline_width // 2 - (label_width // 2),
            self.timeline_y - 50, label_width, label_height
        )
        self.buffer_label_display.setGeometry(
            -10, self.buffer_label_display.y() + 125,
            label_width, label_height
        )

        # Ensure labels are on top
        self.global_time_label.raise_()
        self.trial_time_label.raise_()
        self.label.setVisible(False)
        self.buffer_label_display.raise_()

        # Buffer bar (vertical orange)
        self.buffer_width  = 50
        self.buffer_x      = self.timeline_x + 1350
        self.buffer_y      = self.timeline_y
        self.buffer_height = 155

        self.buffer_background = QGraphicsRectItem(
            self.buffer_x, self.buffer_y,
            self.buffer_width, self.buffer_height
        )
        self.buffer_background.setBrush(QBrush(QColor(220, 220, 220)))
        self.scene.addItem(self.buffer_background)

        self.buffer_fill = QGraphicsRectItem(
            self.buffer_x, self.buffer_y + self.buffer_height,
            self.buffer_width, 0
        )
        self.buffer_fill.setBrush(QBrush(QColor(255, 165, 0)))
        self.scene.addItem(self.buffer_fill)

        # keep track of how “full” each bar is (0.0–1.0)
        self.progress_frac = 0.0
        self.buffer_frac = 0.0

    # ─── DRAW SECOND‐BY‐SECOND MARKERS ─────────────────────────────────────────
    def update_markers(self):
        # Remove old markers
        for marker in self.markers:
            self.scene.removeItem(marker)
        self.markers.clear()

        time_before = self.time_before.value()
        time_after  = self.time_after.value()
        total_time  = time_before + time_after
        step_size   = self.timeline_width / total_time

        for i in range(-time_before, time_after + 1):
            x_pos = self.timeline_x + (i + time_before) * step_size
            line = QGraphicsLineItem(
                x_pos, self.timeline_y,
                x_pos, self.timeline_y + self.timeline_height
            )
            # Bold center, dashed others
            if i != 0:
                line.setPen(QPen(QColor(100, 100, 100), 1, Qt.DashLine))
            else:
                line.setPen(QPen(QColor(0, 0, 0), 3))
            self.scene.addItem(line)
            self.markers.append(line)

            # Numeric second label
            label = QGraphicsTextItem(f"{i}s")
            label.setDefaultTextColor(QColor(0, 0, 0))
            label.setFont(QFont("Montserrat ExtraBold", 9))
            label.setPos(x_pos - 10,
                         self.timeline_y + self.timeline_height + 12)
            self.scene.addItem(label)
            self.markers.append(label)

            # Special “Movement Onset” text under 0
            if i == 0:
                onset_label = QGraphicsTextItem("Movement Onset")
                onset_label.setDefaultTextColor(QColor(200, 0, 0))
                onset_label.setFont(QFont("Montserrat ExtraBold", 11))
                text_width = onset_label.boundingRect().width()
                onset_label.setPos(
                    x_pos - text_width/2,
                    self.timeline_y + self.timeline_height + 35
                )
                self.scene.addItem(onset_label)
                self.markers.append(onset_label)

    # ─── MAIN ANIMATION START ──────────────────────────────────────────────────
    def start_animation(self, status_bar):
        """Trigger global timer + first trial."""
        if self.in_trial:
            beeg.set_status(status_bar,
                            message="Already Running!",
                            error=True)
            logging.error("Attempted to start while already running.")
            return

        beeg.set_status(status_bar,
                        message="Run Started!",
                        error=False)
        logging.debug("Global run started.")

        self.in_trial      = True
        self.global_timer.start()
        self.total_duration = (
            self.time_before.value()
            + self.time_after.value()
        )
        self.trial_number  = 0
        self.total_trials  = int(self.trial_count.text())
        self.buffer        = self.buffer_time.value()

        # Start trial‐relative clock
        self.trial_timer.start()
        self.progress = 0.0
        self.timer.start(10)  # 10ms ticks for precise updates

    # ─── UPDATE PROGRESS & LABELS EACH TICK ───────────────────────────────────
    def update_progress(self, status_bar):
        """Compute real elapsed, update bars & labels, detect transitions."""
        if not self.in_trial:
            logging.error("update_progress called with no trial active.")
            return

        # Real seconds since trial start
        elapsed_trial = self.trial_timer.elapsed() / 1000.0
        frac = min(elapsed_trial / self.total_duration, 1.0)
        self.progress = frac * self.timeline_width

        # Update trial label (relative to onset)
        time_before = self.time_before.value()
        current_time = (
            -time_before
            + frac * (self.time_before.value() + self.time_after.value())
        )
        self.trial_time_label.setText(
            f"Trial {self.trial_number+1} Time: {current_time:.2f}s"
        )

        # Update global label
        elapsed_global = self.global_timer.elapsed() / 1000.0
        self.global_time_label.setText(
            f"Total Time: {elapsed_global:.2f}s (Trial {self.trial_number+1})"
        )

        # End‑of‑trial?
        if elapsed_trial >= self.total_duration:
            self.trial_number += 1
            logging.debug(f"Trial {self.trial_number} completed.")

            # All done?
            if self.trial_number >= self.total_trials:
                self.timer.stop()
                self.label.setText("Trials Completed")
                beeg.set_status(status_bar,
                                message="All Trials Completed!",
                                error=False)
                logging.info("All trials finished.")
                self.in_trial = False
                self.start_button.setEnabled(True)
                QTimer.singleShot(1500, self.reset_progress)
                return

            # Otherwise, buffer period
            self.label.setText(f"Buffering... {self.buffer}s")
            self.timer.stop()
            self.animate_buffer()
        else:
            # Animate blue fill bar
            self.fill_rect.setRect(
                self.timeline_x,
                self.timeline_y,
                self.progress,
                self.timeline_height
            )

        frac = min(elapsed_trial / self.total_duration, 1.0)

        # ─── remember this fraction for resizing later ─────────────────
        self.progress_frac = frac

        # update trial bar in pixels (you can leave self.progress if you want)
        self.progress = frac * self.timeline_width
        self.fill_rect.setRect(
            self.timeline_x,
            self.timeline_y,
            self.progress,
            self.timeline_height
        )

    # ─── IMMEDIATE STOP ────────────────────────────────────────────────────────
    def sudden_stop(self, status_bar):
        """Abort current run, clear timers & visuals."""
        if not self.in_trial:
            beeg.set_status(status_bar,
                            message="Nothing to stop!",
                            error=True)
            logging.error("Stop requested but no trial active.")
            return

        beeg.set_status(status_bar,
                        message="Stopped!",
                        error=False)
        logging.info("Run manually stopped.")

        # Stop all timers
        self.timer.stop()
        if hasattr(self, 'buffer_timer') and self.buffer_timer.isActive():
            self.buffer_timer.stop()

        # Block pending signals briefly
        self.buffer_timer = None
        self.blockSignals(True)
        QTimer.singleShot(50, lambda: self.blockSignals(False))

        # Reset all labels & bars
        self.global_time_label.setText("Total Time: 0s (Buffer)")
        self.trial_time_label.setText("Trial 1 Time: 0s")
        self.label.setText("Movement Onset at 0s")
        self.buffer_label_display.setText("")
        self.buffer_label_display.hide()

        self.progress = 0.0
        self.trial_number = 0
        self.fill_rect.setRect(
            self.timeline_x, self.timeline_y,
            0, self.timeline_height
        )
        self.buffer_fill.setRect(
            self.buffer_x,
            self.buffer_y + self.buffer_height,
            self.buffer_width, 0
        )

        self.in_trial = False
        self.start_button.setEnabled(True)

    # ─── RESET AFTER COMPLETION ────────────────────────────────────────────────
    def reset_progress(self):
        """Clears both bars after run (called 1.5s post‑complete)."""
        self.fill_rect.setRect(
            self.timeline_x, self.timeline_y,
            0, self.timeline_height
        )
        self.buffer_fill.setRect(
            self.buffer_x,
            self.buffer_y + self.buffer_height,
            self.buffer_width, 0
        )
        logging.debug("Progress bars reset.")

    # ─── BUFFER ANIMATION ─────────────────────────────────────────────────────
    def animate_buffer(self):
        """Fill the orange buffer bar over exactly buffer_time seconds."""
        if not self.in_trial:
            logging.error("animate_buffer called with no trial active.")
            return

        buffer_time = self.buffer_time.value()
        self.buffer_start_time = self.global_timer.elapsed()

        # High‑precision buffer timer
        self.buffer_timer = QTimer(self)
        self.buffer_timer.setTimerType(Qt.PreciseTimer)
        self.buffer_timer.timeout.connect(
            lambda: self.update_buffer_fill(buffer_time)
        )
        self.buffer_timer.start(int(1000 * buffer_time / 100))

        # Log buffer start
        self.global_time_data.append(
            (self.global_timer.elapsed(), "Buffer"))
        logging.debug(f"Buffer started for {buffer_time}s.")

        # Update labels
        elapsed_global = self.global_timer.elapsed() / 1000.0
        self.global_time_label.setText(
            f"Total Time: {elapsed_global:.2f}s (Buffer)"
        )
        self.buffer_label_display.setText(
            f"Next Trial In: {buffer_time}s"
        )
        self.buffer_label_display.setVisible(True)

        # Countdown text
        for i in range(buffer_time, 0, -1):
            QTimer.singleShot(
                (buffer_time - i) * 1000,
                lambda i=i: self.buffer_label_display.setText(f"Next Trial In: {i}s")
            )

        # Once buffer period ends:
        QTimer.singleShot(
            buffer_time * 1000,
            lambda: self.buffer_label_display.setText("")
        )
        QTimer.singleShot(
            buffer_time * 1000,
            lambda: self.start_trial()
        )
        QTimer.singleShot(
            buffer_time * 1000,
            lambda: self.keep_buffer_full()
        )

    # ─── UPDATE ORANGE BUFFER FILL ────────────────────────────────────────────
    def update_buffer_fill(self, buffer_time):
        """Stepwise grow the buffer bar based on real elapsed time."""
        elapsed = (
            (self.global_timer.elapsed() - self.buffer_start_time) / 1000
        )
        if elapsed >= buffer_time:
            self.buffer_timer.stop()
            logging.debug("Buffer fill reached full height.")
            return

        filled_height = (elapsed / buffer_time) * self.buffer_height
        self.buffer_fill.setRect(
            self.buffer_x,
            self.buffer_y + self.buffer_height - filled_height,
            self.buffer_width,
            filled_height
        )

        elapsed = (self.global_timer.elapsed() - self.buffer_start_time) / 1000

        # clamp & store fraction
        frac = min(elapsed / buffer_time, 1.0)
        self.buffer_frac = frac

        # now adjust the orange bar in pixels
        filled_height = frac * self.buffer_height
        self.buffer_fill.setRect(
            self.buffer_x,
            self.buffer_y + self.buffer_height - filled_height,
            self.buffer_width,
            filled_height
        )

    # ─── START NEXT TRIAL AFTER BUFFER ────────────────────────────────────────
    def start_trial(self):
        """Reset trial bar, start trial_timer again, and resume updates."""
        if not self.in_trial:
            logging.error("start_trial called but in_trial=False.")
            return

        self.trial_timer.start()
        trial_label = f"Trial {self.trial_number+1}"
        self.global_time_data.append(
            (self.global_timer.elapsed(), trial_label)
        )
        self.trial_time_label.setText(
            f"Trial {self.trial_number+1} Time: 0s"
        )
        self.progress = 0.0
        self.fill_rect.setRect(
            self.timeline_x, self.timeline_y,
            0, self.timeline_height
        )
        self.label.setText("Movement Onset at 0s")
        self.timer.start(10)
        logging.debug(f"Started Trial {self.trial_number+1}.")

    # ─── FLASH FULL BUFFER, THEN CLEAR ─────────────────────────────────────────
    def keep_buffer_full(self):
        """Show full buffer briefly, then clear it to indicate completion."""
        self.buffer_fill.setRect(
            self.buffer_x,
            self.buffer_y,
            self.buffer_width,
            self.buffer_height
        )
        logging.debug("Buffer shown at full height for completion cue.")
        # After 1 s, clear the buffer bar
        QTimer.singleShot(1000, lambda: self.clear_buffer())

    # ─── CLEAR BUFFER BAR ──────────────────────────────────────────────────────
    def clear_buffer(self):
        """Empty buffer bar—called after keep_buffer_full delay."""
        self.buffer_fill.setRect(
            self.buffer_x,
            self.buffer_y + self.buffer_height,
            self.buffer_width,
            0
        )
        logging.debug("Buffer cleared after completion cue.")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # — recalc the timeline’s position & size based on the new widget size —
        # keep a 50px margin on left/right:
        self.timeline_x     = 100
        self.timeline_width = (self.width() - 2*self.timeline_x)
        # keep the same height & vertical offset you already chose:
        # self.timeline_y, self.timeline_height remain unchanged

        # update the background bar
        self.background_rect.setRect(
            self.timeline_x,
            self.timeline_y,
            self.timeline_width,
            self.timeline_height
        )

        # update the blue fill to whatever progress you had
        self.fill_rect.setRect(
            self.timeline_x,
            self.timeline_y,
            self.progress,
            self.timeline_height
        )

        # move the center line
        self.center_line.setLine(
            self.timeline_x,
            self.timeline_y + self.timeline_height/2,
            self.timeline_x + self.timeline_width,
            self.timeline_y + self.timeline_height/2
        )

        # redraw all the second‐markers in the new width
        self.update_markers()

        # ─── reposition the two time‑labels as part of the bar ───────────────
        label_w, label_h = 250, 35
        # same vertical offset as the Movement Onset label
        y_pos = self.timeline_y - label_h - 15  # tweak -15 to match your exact "−50"

        # left label: its left edge sits on the left marker (-time_before)
        self.global_time_label.setGeometry(
            self.timeline_x,
            y_pos,
            label_w,
            label_h
        )

        # right label: its right edge sits on the right marker (+time_after)
        self.trial_time_label.setGeometry(
            self.timeline_x + self.timeline_width - label_w - 200,
            y_pos,
            label_w,
            label_h
        )

        # movement‑onset label (unchanged)
        self.label.setGeometry(
            self.timeline_x + (self.timeline_width // 2) - (label_w // 2),
            self.timeline_y - 50,
            label_w,
            label_h
        )

        # movement‐onset label centered above the bar
        self.label.setGeometry(
            self.timeline_x + (self.timeline_width//2) - 125,
            self.timeline_y - 50,
            250, 35
        )

        # buffer countdown label (left of timeline, keep your old Y offset)
        self.buffer_label_display.setGeometry(
            -10,
            self.buffer_label_display.y(),
            250, 35
        )

        # Recompute trial‑fill bar from the saved fraction
        fill_w = int(self.timeline_width * self.progress_frac)
        self.fill_rect.setRect(
            self.timeline_x,
            self.timeline_y,
            fill_w,
            self.timeline_height
        )

        # Recompute buffer‑fill bar from the saved fraction
        buffer_h = int(self.buffer_height * self.buffer_frac)
        self.buffer_fill.setRect(
            self.buffer_x,
            self.buffer_y + self.buffer_height - buffer_h,
            self.buffer_width,
            buffer_h
        )

        # — finally, shift the vertical buffer bar over to sit just to the right —
        self.buffer_x = self.timeline_x + self.timeline_width + 50
        self.buffer_background.setRect(
            self.buffer_x,
            self.buffer_y,
            self.buffer_width,
            self.buffer_height
        )
        # preserve whatever fill‐height you’d already animated:
        current_fill_h = self.buffer_fill.rect().height()
        self.buffer_fill.setRect(
            self.buffer_x,
            self.buffer_y + self.buffer_height - current_fill_h,
            self.buffer_width,
            current_fill_h
        )
        self.scene.setSceneRect(self.scene.itemsBoundingRect())
        # ─── ensure the view itself fills the widget (no clipping) ───────────
        self.view.setGeometry(0, 0, self.width(), self.height())
