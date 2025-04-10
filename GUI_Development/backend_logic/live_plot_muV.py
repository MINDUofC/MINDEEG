import numpy as np
import time
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PyQt5.QtCore import QTimer
from vispy import scene
from vispy.scene import Line
from vispy.color import get_colormap
from brainflow.board_shim import BoardShim
from GUI_Development.backend_logic.data_processing import get_filtered_data


class MuVGraphVispyStacked(QWidget):
    def __init__(self, board_shim, BoardOnCheckBox, preprocessing_controls, parent=None):
        super().__init__(parent)

        self.board_shim = board_shim
        self.BoardOnCheckBox = BoardOnCheckBox
        self.preprocessing_controls = preprocessing_controls

        self.eeg_channels = None
        self.sampling_rate = None
        self.num_points = None
        self.update_speed_ms = 30
        self.max_points = 1000

        self.lines = []
        self.offset_spacing = 150  # µV offset between channels

        self.last_time = time.time()
        self.init_ui()
        self.init_timer()

    def init_ui(self):
        layout = QVBoxLayout(self)
        colormap = get_colormap("cool")

        # Shared canvas and view
        self.canvas = scene.SceneCanvas(keys=None, show=False, bgcolor="black", parent=self)
        self.view = self.canvas.central_widget.add_view()
        self.view.camera = 'panzoom'
        self.view.camera.set_range()
        self.view.camera.interactive = False  # Lock user from panning/zooming unless you want it

        layout.addWidget(self.canvas.native)

        # Create 8 line visuals
        for i in range(8):
            color = colormap.map(np.array([i / 8]))[0]
            line = Line(pos=np.zeros((2, 2)), color=color, parent=self.view.scene)
            self.lines.append(line)

        # Pause button
        self.pause_button = QPushButton("Pause")
        self.pause_button.setStyleSheet("font-family: 'Montserrat ExtraBold';")
        self.pause_button.clicked.connect(self.toggle_pause)
        layout.addWidget(self.pause_button)

    def init_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(self.update_speed_ms)

    def toggle_pause(self):
        if self.timer.isActive():
            self.timer.stop()
            self.pause_button.setText("Resume")
        else:
            self.timer.start(self.update_speed_ms)
            self.pause_button.setText("Pause")

    def update_plot(self):
        if not self.board_shim or not self.BoardOnCheckBox.isChecked():
            return

        if self.eeg_channels is None or self.sampling_rate is None or self.num_points is None:
            self.eeg_channels = BoardShim.get_eeg_channels(self.board_shim.get_board_id())
            self.sampling_rate = BoardShim.get_sampling_rate(self.board_shim.get_board_id())
            self.num_points = int(6 * self.sampling_rate)
            print(f"Board Initialized: {len(self.eeg_channels)} EEG channels, {self.sampling_rate} Hz")

        filtered_data = get_filtered_data(
            self.board_shim, self.num_points, self.eeg_channels, self.preprocessing_controls
        )

        for i, channel in enumerate(self.eeg_channels):
            y = filtered_data[channel]
            x = np.linspace(0, len(y) / self.sampling_rate, len(y))

            if len(x) > self.max_points:
                x = x[-self.max_points:]
                y = y[-self.max_points:]

            # 🧠 Normalize and confine to a vertical "band"
            y_min, y_max = np.min(y), np.max(y)
            if y_max - y_min == 0:
                y_norm = np.zeros_like(y)
            else:
                y_norm = (y - y_min) / (y_max - y_min)

            y_scaled = y_norm * self.offset_spacing * 0.8  # Scale to 80% of lane height
            offset_y = y_scaled + i * self.offset_spacing  # Vertically offset

            self.lines[i].set_data(np.column_stack((x, offset_y)))

        # Autoscale view to fit all channels
        self.view.camera.set_range(
            x=(x.min(), x.max()),
            y=(0, self.offset_spacing * len(self.eeg_channels))
        )

        # Optional: FPS print for performance testing
        # now = time.time()
        # print(f"FPS: {1 / (now - self.last_time):.1f}")
        # self.last_time = now
