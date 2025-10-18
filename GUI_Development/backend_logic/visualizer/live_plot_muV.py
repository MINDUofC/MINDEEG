import numpy as np
import time
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PyQt5.QtCore import QTimer
from vispy import scene
from vispy.scene import Line, Text
from vispy.color import get_colormap
from brainflow.board_shim import BoardShim
from backend_logic.data_handling.data_collector import CentralizedDataCollector


class MuVGraphVispyStacked(QWidget):
    def __init__(self, board_shim, BoardOnCheckBox, preprocessing_controls, ica_manager=None, data_collector=None, parent=None):
        super().__init__(parent)

        self.board_shim = board_shim
        self.BoardOnCheckBox = BoardOnCheckBox
        self.preprocessing_controls = preprocessing_controls
        self.ica_manager = ica_manager
        self.data_collector = data_collector

        # Live update config - 16ms for 60fps rendering (smoother visuals)
        self.update_speed_ms = 16
        self.max_points = 1000

        # Visual + layout config
        self.offset_spacing = 130
        self.label_margin_ratio = 0.07
        self._fixed_amp_range = None

        # Lazy vars
        self.eeg_channels = None
        self.sampling_rate = None
        self.num_points = None

        # Elements
        self.lines = []
        self.labels = []
        self.separators = []
        
        # Performance caching for rendering
        self._cached_position_arrays = {}  # Cache x/y position arrays per channel
        self._last_active_channel_count = 0

        self.last_time = time.time()
        self.init_ui()
        self.init_timer()

    def init_ui(self):
        layout = QVBoxLayout(self)
        colormap = get_colormap("cool")

        self.canvas = scene.SceneCanvas(keys=None, show=False, bgcolor="black", parent=self)
        self.view = self.canvas.central_widget.add_view()
        self.view.camera = 'panzoom'
        self.view.camera.set_range(x=(0, 1), y=(-20, self.offset_spacing * 8 + 40))
        self.view.camera.interactive = False

        layout.addWidget(self.canvas.native)

        for i in range(8):
            # Placeholder flat line per channel
            x_placeholder = np.linspace(0, 1 - self.label_margin_ratio, 200)
            x_placeholder += self.label_margin_ratio
            y_placeholder = np.full_like(x_placeholder, (i + 0.5) * self.offset_spacing)

            color = colormap.map(np.array([i / 8]))[0]
            line = Line(
                pos=np.column_stack((x_placeholder, y_placeholder)),
                color=color,
                parent=self.view.scene
            )
            self.lines.append(line)

            # Channel label
            label = Text(
                text=f"Channel {i + 1}",
                color='#CCCCCC',
                font_size=5,
                rotation=-90,
                parent=self.view.scene,
                anchor_x='center',
                anchor_y='center',
                pos=(self.label_margin_ratio * 0.15, (i + 0.5) * self.offset_spacing)
            )
            self.labels.append(label)

            # Separator line
            sep_y = (i + 1) * self.offset_spacing
            sep = Line(
                pos=np.array([[0, sep_y], [1, sep_y]]),
                color=(0.3, 0.3, 0.3, 0.6),
                parent=self.view.scene
            )
            self.separators.append(sep)

        # Title
        self.title = Text(
            text="µV - Time Domain Plot",
            color='#DDDDDD',
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
        # Do NOT start it here — it will be started only when the tab is activated

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

        # Lazy init board parameters
        if self.eeg_channels is None or self.sampling_rate is None or self.num_points is None:
            self.eeg_channels = BoardShim.get_eeg_channels(self.board_shim.get_board_id())
            self.sampling_rate = BoardShim.get_sampling_rate(self.board_shim.get_board_id())
            self.num_points = int(4 * self.sampling_rate)  # 4-second window (33% less processing)
            print(f"Board Initialized: {len(self.eeg_channels)} EEG channels, {self.sampling_rate} Hz")

        # Use centralized data collector
        filtered_data = self.data_collector.collect_data_muV() if self.data_collector else None
        
        if filtered_data is None:
            return

        track_height = self.offset_spacing * 0.8
        # Only update channels that have data - performance optimization
        num_active = min(len(self.eeg_channels), len(filtered_data))
        
        # Track if channel count changed to clear position cache
        if num_active != self._last_active_channel_count:
            self._cached_position_arrays.clear()
            self._last_active_channel_count = num_active

        for idx, line in enumerate(self.lines):
            # Only process and render active channels
            if idx < num_active:
                # ─── Active channel plotting ────────────────────────────
                channel = self.eeg_channels[idx]
                y = filtered_data[channel]
                
                # Cache x array computation - only depends on data length and sampling rate
                data_len = len(y)
                cache_key = f"x_{data_len}"
                if cache_key not in self._cached_position_arrays:
                    self._cached_position_arrays[cache_key] = np.linspace(0, data_len / self.sampling_rate, data_len)
                x = self._cached_position_arrays[cache_key]

                # Trim to max_points
                if len(x) > self.max_points:
                    x = x[-self.max_points:]
                    y = y[-self.max_points:]

                smoothing_on = (
                        self.preprocessing_controls["Average"].isChecked()
                        or self.preprocessing_controls["Median"].isChecked()
                )

                if smoothing_on:
                    # Lock amplitude range once
                    if self._fixed_amp_range is None:
                        peak = max(abs(y.min()), abs(y.max()), 1e-6)
                        self._fixed_amp_range = peak

                    amp = self._fixed_amp_range
                    y_clamped = np.clip(y, -amp, amp)
                    y_scaled = (y_clamped / amp) * (track_height / 2)


                else:
                    # Reset for next smoothing
                    self._fixed_amp_range = None

                    # Dynamic min/max → [0…1]
                    y_min, y_max = y.min(), y.max()
                    if y_max - y_min != 0:
                        y_norm = (y - y_min) / (y_max - y_min)
                    else:
                        y_norm = np.zeros_like(y)

                    # Scale + mean-lock
                    y_scaled = y_norm * track_height
                    curr_mean = y_scaled.mean()
                    desired_mean = track_height / 2
                    y_scaled = y_scaled - curr_mean + desired_mean

                # ─── FLAT-LINE THE OLDEST PORTION ALWAYS ───────────────────
                # Slightly reduce height
                y_scaled *= 0.95
                flat_duration_s = 0.1  # or 0.2 if you prefer
                flat_pts = min(int(flat_duration_s * self.sampling_rate), len(y_scaled))
                y_scaled[:flat_pts] = 0

                # Vertical stacking: centered if smoothing, else original
                if smoothing_on:
                    offset_y = y_scaled + (idx + 0.5) * self.offset_spacing
                else:
                    offset_y = y_scaled + (idx + 0.20) * self.offset_spacing

                # X scaling - cache when possible
                x_max = x.max()
                if x_max != 0:
                    x_cache_key = f"xscale_{data_len}"
                    if x_cache_key not in self._cached_position_arrays:
                        # Cache the scaled x positions (same for all channels with same data length)
                        x_scaled = (x / x_max) * (1 - self.label_margin_ratio) + self.label_margin_ratio
                        self._cached_position_arrays[x_cache_key] = x_scaled
                    else:
                        x_scaled = self._cached_position_arrays[x_cache_key]
                else:
                    x_scaled = x + self.label_margin_ratio

                # Draw and show - use pre-allocated column_stack
                line.set_data(np.column_stack((x_scaled, offset_y)))
                line.visible = True
                # Ensure labels and separators are visible for active channels
                if idx < len(self.labels):
                    self.labels[idx].visible = True
                if idx < len(self.separators):
                    self.separators[idx].visible = True
            else:
                # Hide inactive channels for better performance - no rendering overhead
                line.visible = False
                # Also hide labels and separators for inactive channels
                if idx < len(self.labels):
                    self.labels[idx].visible = False
                if idx < len(self.separators):
                    self.separators[idx].visible = False




