import numpy as np
import time
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PyQt5.QtCore import QTimer
from vispy import scene
from vispy.scene import Line, Text
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
        self.labels = []
        self.separators = []

        self.offset_spacing = 150
        self.label_margin_ratio = 0.05

        self.last_time = time.time()
        self.init_ui()
        self.init_timer()

    def init_ui(self):
        layout = QVBoxLayout(self)
        colormap = get_colormap("cool")

        self.canvas = scene.SceneCanvas(keys=None, show=False, bgcolor="black", parent=self)
        self.view = self.canvas.central_widget.add_view()
        self.view.camera = 'panzoom'

        # Slightly compressed layout: reduce spacing between channels
        self.offset_spacing = 130  # Used to be 150

        self.label_margin_ratio = 0.07  # Increased margin to shift signals right & make room for labels
        self.view.camera.set_range(x=(0, 1), y=(-20, self.offset_spacing * 8 + 40))  # moved everything down
        self.view.camera.interactive = False

        layout.addWidget(self.canvas.native)

        for i in range(8):
            # Placeholder straight line (flat until real data comes in)
            x_placeholder = np.linspace(0, 1 - self.label_margin_ratio, 200)
            x_placeholder += self.label_margin_ratio  # shift everything to the right
            y_placeholder = np.full_like(x_placeholder, (i + 0.5) * self.offset_spacing)

            color = colormap.map(np.array([i / 8]))[0]
            line = Line(
                pos=np.column_stack((x_placeholder, y_placeholder)),
                color=color,
                parent=self.view.scene
            )
            self.lines.append(line)

            # Channel label (smaller, more left)
            label = Text(
                text=f"Channel {i + 1}",
                color='#CCCCCC',  # Light grey like PyQtGraph
                font_size=5,
                rotation=-90,
                parent=self.view.scene,
                anchor_x='center',
                anchor_y='center',
                pos=(self.label_margin_ratio * 0.15, (i + 0.5) * self.offset_spacing)
            )

            self.labels.append(label)

            # Horizontal separator line
            sep_y = (i + 1) * self.offset_spacing
            sep = Line(
                pos=np.array([[0, sep_y], [1, sep_y]]),
                color=(0.3, 0.3, 0.3, 0.6),
                parent=self.view.scene
            )
            self.separators.append(sep)

        # Title (adjusted position + new name)
        self.title = Text(
            text="µV - Time Domain Plot",
            color='#DDDDDD',  # Slightly brighter for heading
            font_size=9,
            bold=False,
            parent=self.view.scene,
            anchor_x='center',
            anchor_y='top',
            pos=(0.5, self.offset_spacing * 8 + 30)
        )

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

        canvas_width = self.canvas.size[0]
        label_margin = canvas_width * self.label_margin_ratio

        for i, channel in enumerate(self.eeg_channels):
            y = filtered_data[channel]
            x = np.linspace(0, len(y) / self.sampling_rate, len(y))

            if len(x) > self.max_points:
                x = x[-self.max_points:]
                y = y[-self.max_points:]

            y_min, y_max = np.min(y), np.max(y)
            if y_max - y_min == 0:
                y_norm = np.zeros_like(y)
            else:
                y_norm = (y - y_min) / (y_max - y_min)

            y_scaled = y_norm * self.offset_spacing * 0.8
            offset_y = y_scaled + i * self.offset_spacing

            x_scaled = x / x.max() if x.max() != 0 else x
            x_scaled = x_scaled * (1 - self.label_margin_ratio)
            x_scaled += self.label_margin_ratio

            self.lines[i].set_data(np.column_stack((x_scaled, offset_y)))

        self.view.camera.set_range(x=(0, 1), y=(0, self.offset_spacing * len(self.eeg_channels)))
