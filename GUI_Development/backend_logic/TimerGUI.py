import sys
from PyQt5.QtWidgets import  QWidget, QVBoxLayout, QLabel, QGraphicsView, \
    QGraphicsScene, QGraphicsRectItem, QGraphicsLineItem, QGraphicsTextItem
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QColor, QBrush, QPen, QFont
from PyQt5.QtCore import QElapsedTimer

class TimelineWidget(QWidget):
# INIT

    def __init__(self, recordButton, stopButton, beforeOnset, afterOnset, buffer, numTrials):
        super().__init__()
        # **Make the whole widget transparent**
        self.setAttribute(Qt.WA_TranslucentBackground)  # Ensures full transparency
        self.setStyleSheet("background: transparent; border: none;")  # Remove borders

        self.initUI(recordButton, stopButton, beforeOnset, afterOnset, buffer, numTrials)


# INITIALIZATION AND GRAPHICAL THINGS


    def initUI(self, recordButton,stopButton, beforeOnset, afterOnset, buffer, numTrials):
        layout = QVBoxLayout()

        # Total Elapsed Time Box
        self.global_time_label = QLabel("Total Time: 0s (Buffer)", self)
        self.global_time_label.setAlignment(Qt.AlignRight)
        self.global_time_label.setStyleSheet(
            "font-size: 16px; font-family: 'Montserrat ExtraBold'; color: black;")
        layout.addWidget(self.global_time_label)

        # Current Trial Time Box
        self.trial_time_label = QLabel("Trial 1 Time: 0s", self)
        self.trial_time_label.setAlignment(Qt.AlignRight)
        self.trial_time_label.setStyleSheet(
            "font-size: 16px; font-family: 'Montserrat ExtraBold'; color: black;")
        layout.addWidget(self.trial_time_label)

        # Global precise timer (tracks all trials + buffers)
        self.global_timer = QElapsedTimer()
        self.global_time_data = []  # Stores categorized time data (Trial X, Buffer, etc.)

        # Trial relative timer (tracks only trial-specific times)
        self.trial_timer = QElapsedTimer()
        self.trial_time_data = []  # Stores detailed trial times

        self.label = QLabel("Movement Onset at 0s", self)
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)

        self.start_button = recordButton
        self.start_button.clicked.connect(self.start_animation)
        # WILL NEED TO ALSO ADD IN START COLLECTING DATA AS WELL HERE LATER

        self.stop_button = stopButton  # Store stop button
        self.stop_button.clicked.connect(self.sudden_stop)
        self.in_trial = False
        self.trial_count = numTrials
        self.trial_count.setText("5")

        self.buffer_time = buffer
        self.buffer_time.setValue(3)

        self.time_before = beforeOnset
        self.time_before.setValue(3)
        self.time_before.valueChanged.connect(self.update_markers)

        self.time_after = afterOnset
        self.time_after.setValue(3)
        self.time_after.valueChanged.connect(self.update_markers)

        # Graphics View for timeline
        self.view = QGraphicsView(self)
        self.scene = QGraphicsScene(self)
        self.view.setScene(self.scene)
        layout.addWidget(self.view)


        self.timer = QTimer()
        self.timer.timeout.connect(self.update_progress)

        self.elapsed_time = 0
        self.trial_number = 0
        self.progress = 0.0

        # Setup timeline dimensions
        self.timeline_width = 1300  # Increased width from 900 to 1200
        self.timeline_height = 80  # Keep the same height
        self.timeline_x = 50
        self.timeline_y = 200  # Keep Y position consistent


        # Create background timeline with adjusted height
        self.background_rect = QGraphicsRectItem(
            self.timeline_x, self.timeline_y, self.timeline_width, self.timeline_height
        )
        self.background_rect.setBrush(QBrush(QColor(220, 220, 220)))  # Light gray background
        self.scene.addItem(self.background_rect)

        # Create filling progress bar with new height
        self.fill_rect = QGraphicsRectItem(
            self.timeline_x, self.timeline_y, 0, self.timeline_height
        )
        self.fill_rect.setBrush(QBrush(QColor(50, 150, 250)))  # Blue fill
        self.scene.addItem(self.fill_rect)

        # Update center line position
        self.center_line = QGraphicsLineItem(
            self.timeline_x, self.timeline_y + self.timeline_height / 2,
                             self.timeline_x + self.timeline_width, self.timeline_y + self.timeline_height / 2
        )
        self.center_line.setPen(QPen(QColor(0, 0, 0), 2))  # Keep line thickness
        self.scene.addItem(self.center_line)

        self.markers = []
        self.update_markers()

        # Buffer countdown indicator (Position it BELOW timeline and buffer)
        self.buffer_label_display = QLabel("", self)
        self.buffer_label_display.setAlignment(Qt.AlignCenter)
        self.buffer_label_display.setStyleSheet(
            "font-size: 20px; font-family: 'Montserrat ExtraBold'; color: red;")
        self.buffer_label_display.setMinimumHeight(30)  # Add spacing below

        # **Instead of adding it earlier, add it AFTER the GraphicsView**
        layout.addWidget(self.buffer_label_display)  # THEN buffer label, so it stays below

        # Manually Positioning all labels so they are visible
        label_width = 250  # Wider labels to prevent text cutoff

        label_height = 35  # Standard height for readability

        # Global Time Label (Top Right)
        self.global_time_label.setGeometry(self.timeline_x + self.timeline_width - 292,  self.global_time_label.y() + 120,label_width,label_height)

        # Trial Time Label (Below Global Time)
        self.trial_time_label.setGeometry(self.timeline_x + self.timeline_width - 292, 140, label_width, label_height)

        # Movement Onset Label (Centered Above Timeline)
        self.label.setGeometry(self.timeline_x + self.timeline_width // 2 - (label_width // 2), self.timeline_y - 50, label_width, label_height)

        # Buffer Countdown Label (Below Timeline, Centered)
        self.buffer_label_display.setGeometry(-10, self.buffer_label_display.y() + 125, label_width,label_height)

        self.global_time_label.raise_()
        self.trial_time_label.raise_()
        self.label.setVisible(False)
        self.buffer_label_display.raise_()

        # Buffer timeline setup (vertical bar)
        self.buffer_width = 50
        self.buffer_x = self.timeline_x + 1350
        self.buffer_y = self.timeline_y
        self.buffer_height = 155

        self.buffer_background = QGraphicsRectItem(self.buffer_x, self.buffer_y, self.buffer_width, self.buffer_height)
        self.buffer_background.setBrush(QBrush(QColor(220, 220, 220)))  # Light gray background
        self.scene.addItem(self.buffer_background)

        self.buffer_fill = QGraphicsRectItem(self.buffer_x, self.buffer_y + self.buffer_height, self.buffer_width, 0)
        self.buffer_fill.setBrush(QBrush(QColor(255, 165, 0)))  # Orange fill
        self.scene.addItem(self.buffer_fill)



    def update_markers(self):
        """Updates timeline markers based on input values, adjusting for new height."""
        for marker in self.markers:
            self.scene.removeItem(marker)
        self.markers.clear()

        time_before = self.time_before.value()
        time_after = self.time_after.value()
        total_time = time_before + time_after
        step_size = self.timeline_width / total_time

        for i in range(-time_before, time_after + 1):
            x_pos = self.timeline_x + (i + time_before) * step_size
            line = QGraphicsLineItem(x_pos, self.timeline_y, x_pos, self.timeline_y + self.timeline_height)

            # Make non-zero markers lighter and dotted
            if i != 0:
                line.setPen(QPen(QColor(100, 100, 100), 1, Qt.DashLine))  # Gray + Dotted
            else:
                line.setPen(QPen(QColor(0, 0, 0), 3))  # Bold black for zero marker

            self.scene.addItem(line)
            self.markers.append(line)

            # Time labels under markers
            label = QGraphicsTextItem(f"{i}s")
            label.setDefaultTextColor(QColor(0, 0, 0))
            label.setFont(QFont("Montserrat ExtraBold", 9, QFont.Normal))  # Adjusted size for new height
            label.setPos(x_pos - 10, self.timeline_y + self.timeline_height + 12)  # Adjusted spacing
            self.scene.addItem(label)
            self.markers.append(label)

            # Special label for Movement Onset (0s) (Fixing Centering Issue)
            if i == 0:
                onset_label = QGraphicsTextItem("Movement Onset")
                onset_label.setDefaultTextColor(QColor(200, 0, 0))  # Red for emphasis
                onset_label.setFont(QFont("Montserrat ExtraBold", 11, QFont.Normal))

                # Calculate text width and center it over "0"
                text_width = onset_label.boundingRect().width()
                correct_x_pos = x_pos - (text_width / 2)  # Centering fix

                onset_label.setPos(correct_x_pos, self.timeline_y + self.timeline_height + 35)
                self.scene.addItem(onset_label)
                self.markers.append(onset_label)

    # PROGRESS BAR ANIMATION


    def start_animation(self):
        """Starts the overall global timer and begins the first trial."""
        if self.in_trial:  # Prevent re-clicking record mid-trial
            return

        self.in_trial = True  # Mark trial as running
        self.start_button.setEnabled(False)  # Disable record button

        self.global_timer.start()  # Start the global timer
        self.total_duration = self.time_before.value() + self.time_after.value()
        self.trial_number = 0
        self.total_trials = int(self.trial_count.text())
        self.buffer = self.buffer_time.value()
        self.elapsed_time = 0
        self.progress = 0.0
        self.timer.start(10)  # Update every 10ms for smooth animation


    def update_progress(self):
        """Updates progress, trial timer, and global elapsed time."""
        self.elapsed_time += 0.01
        total_time = self.total_duration
        self.progress = (self.elapsed_time / total_time) * self.timeline_width

        # Track detailed trial time relative to onset
        time_before = self.time_before.value()
        current_trial_time = -time_before + (self.elapsed_time / total_time) * (time_before + self.time_after.value())

        # Update trial time box
        self.trial_time_label.setText(f"Trial {self.trial_number + 1} Time: {round(current_trial_time, 2)}s")

        # Update global elapsed time box
        elapsed_sec = round(self.global_timer.elapsed() / 1000, 2)
        self.global_time_label.setText(f"Total Time: {elapsed_sec}s (Trial {self.trial_number + 1})")

        if self.progress >= self.timeline_width:
            self.trial_number += 1
            if self.trial_number >= self.total_trials:
                self.timer.stop()
                self.label.setText("Trials Completed")
                self.in_trial = False  # Mark trial as completed
                self.start_button.setEnabled(True)  # Re-enable record button
                QTimer.singleShot(1500, self.reset_progress)  # Reset progress bar after 1.5s
                return

            self.label.setText(f"Buffering... {self.buffer}s")
            self.timer.stop()
            self.animate_buffer()
        else:
            self.fill_rect.setRect(self.timeline_x, self.timeline_y, self.progress, self.timeline_height)


    def sudden_stop(self):
        """Stops everything and resets progress to empty, but does nothing if already stopped."""
        if not self.in_trial:  # If no trial is running, do nothing
            return

        self.timer.stop()  # Stop animation timer
        if hasattr(self, 'buffer_timer') and self.buffer_timer.isActive():
            self.buffer_timer.stop()  # Ensure buffer animation stops

        # Prevent auto-starting of next trial if buffer was active
        self.buffer_timer = None  # Remove buffer timer reference to break callbacks
        self.blockSignals(True)  # Prevent queued signals from executing
        QTimer.singleShot(50, lambda: self.blockSignals(False))  # Unblock after a short delay

        # Reset all labels
        self.global_time_label.setText("Total Time: 0s (Buffer)")
        self.trial_time_label.setText("Trial 1 Time: 0s")
        self.label.setText("Movement Onset at 0s")
        self.buffer_label_display.setText("")
        self.buffer_label_display.hide()  # Hide buffer text properly

        # Reset progress bar
        self.elapsed_time = 0
        self.progress = 0.0
        self.trial_number = 0
        self.fill_rect.setRect(self.timeline_x, self.timeline_y, 0, self.timeline_height)  # Empty progress bar
        self.buffer_fill.setRect(self.buffer_x, self.buffer_y + self.buffer_height, self.buffer_width, 0)  # Empty buffer

        # Reset trial-related state
        self.in_trial = False  # Allow starting a new trial again
        self.start_button.setEnabled(True)  # Re-enable record button


    def reset_progress(self):
        """Resets progress bar to empty after trials complete."""
        self.fill_rect.setRect(self.timeline_x, self.timeline_y, 0, self.timeline_height)  # Clear progress bar
        self.buffer_fill.setRect(self.buffer_x, self.buffer_y + self.buffer_height, self.buffer_width, 0)  # Clear buffer

        # BUFFER MANAGEMENT AND ANIMATION


    def animate_buffer(self):
        """ Smoothly fills the buffer bar within the exact buffer time. """
        if self.in_trial is False:  # Prevent buffer from running if stopped
            return

        buffer_time = self.buffer_time.value()  # Get buffer duration
        self.buffer_progress = 0
        self.buffer_start_time = self.global_timer.elapsed()  # Capture precise start time
        self.buffer_timer = QTimer()

        # Ensure the buffer animation completes in exactly 'buffer_time' seconds
        self.buffer_timer.timeout.connect(lambda: self.update_buffer_fill(buffer_time))
        self.buffer_timer.start(int(1000 * buffer_time / 100))  # 100 steps

        # Store buffer classification
        self.global_time_data.append((self.global_timer.elapsed(), "Buffer"))

        # Update global time display to indicate buffer
        elapsed_sec = round(self.global_timer.elapsed() / 1000, 2)
        self.global_time_label.setText(f"Total Time: {elapsed_sec}s (Buffer)")
        self.buffer_label_display.setText(f"Next Trial In: {buffer_time}s")
        self.buffer_label_display.setVisible(True)  # Ensure it's always visible

        for i in range(buffer_time, 0, -1):
            QTimer.singleShot((buffer_time - i) * 1000,
                              lambda i=i: self.buffer_label_display.setText(f"Next Trial In: {i}s"))

        # Instead of hiding it, set it to an empty string when countdown completes
        QTimer.singleShot(buffer_time * 1000, lambda: self.buffer_label_display.setText("") if self.in_trial else None)
        QTimer.singleShot(buffer_time * 1000, lambda: self.start_trial() if self.in_trial else None)
        QTimer.singleShot(buffer_time * 1000, lambda: self.keep_buffer_full() if self.in_trial else None)


    def update_buffer_fill(self, buffer_time):
        """Ensures buffer animation completes exactly within buffer_time."""
        elapsed = (self.global_timer.elapsed() - self.buffer_start_time) / 1000  # Convert ms to seconds

        if elapsed >= buffer_time:
            self.buffer_timer.stop()  # Stop exactly at buffer_time
            return

        # Update buffer fill amount based on elapsed time
        filled_height = (elapsed / buffer_time) * self.buffer_height
        self.buffer_fill.setRect(
            self.buffer_x, self.buffer_y + self.buffer_height - filled_height,
            self.buffer_width, filled_height
        )


    def start_trial(self):
        """ Start the trial-specific timer and update display. """
        if not self.in_trial:  # Ensure that trial only starts if it wasn’t stopped
            return

        self.trial_timer.start()  # Start trial-specific timer

        # Store the global timer classification
        trial_label = f"Trial {self.trial_number + 1}"
        self.global_time_data.append((self.global_timer.elapsed(), trial_label))  # Store trial start time

        # Update trial display
        self.trial_time_label.setText(f"Trial {self.trial_number + 1} Time: 0s")

        self.elapsed_time = 0
        self.progress = 0.0
        self.fill_rect.setRect(self.timeline_x, self.timeline_y, 0, self.timeline_height)
        self.label.setText("Movement Onset at 0s")
        self.timer.start(10)  # Start blue progress bar immediately


    def keep_buffer_full(self):
        """ Keeps the buffer full for 250ms before resetting it. """
        self.buffer_fill.setRect(self.buffer_x, self.buffer_y, self.buffer_width,
                                 self.buffer_height)  # Show full buffer
        QTimer.singleShot(1000, lambda: self.clear_buffer())  # After 250ms, empty the buffer

    def clear_buffer(self):
        """ Clears the buffer, ready for the next trial, without affecting the timeline. """
        self.buffer_fill.setRect(self.buffer_x, self.buffer_y + self.buffer_height, self.buffer_width, 0)  # Empty buffer

