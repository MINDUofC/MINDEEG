import time
import logging
import numpy as np
from PyQt5.QtCore import pyqtSignal, QThread
from brainflow.board_shim import BoardShim, BrainFlowInputParams
from brainflow.data_filter import DataFilter, FilterTypes, DetrendOperations

class BlinkDetector(QThread):
    blink_detected = pyqtSignal(str)  # emits "P1" or "P2"

    def __init__(self, player="P1", board_id=57, serial_port="COM4"):
        super().__init__()
        self.player = player
        self.board_id = board_id
        self.serial_port = serial_port
        self.board_shim = None
        self.running = False
        self.threshold_uv = 200
        self._in_blink = False

    def setup_board(self):
        params = BrainFlowInputParams()
        params.serial_port = self.serial_port
        self.board_shim = BoardShim(self.board_id, params)
        self.board_shim.prepare_session()
        self.board_shim.start_stream()
        time.sleep(2)

        commands = [f"chon_{i}_12;rldadd_{i}" for i in range(1, 9)]
        for cmd in commands:
            for sub_cmd in cmd.split(";"):
                self.board_shim.config_board(sub_cmd)
                time.sleep(0.2)

        self.eeg_channels = BoardShim.get_eeg_channels(self.board_id)[6:8]
        self.sampling_rate = BoardShim.get_sampling_rate(self.board_id)
        self.num_points = int(2 * self.sampling_rate)

    def run(self):
        try:
            logging.basicConfig(level=logging.INFO)
            self.setup_board()
            self.running = True
            while self.running:
                self.detect_blink()
                time.sleep(0.03)
        except Exception:
            logging.exception("BlinkDetector failed")
        finally:
            if self.board_shim and self.board_shim.is_prepared():
                self.board_shim.release_session()

    def stop(self):
        self.running = False

    def detect_blink(self):
        if self.board_shim is None:
            return

        data = self.board_shim.get_current_board_data(self.num_points)
        ch7, ch8 = self.eeg_channels
        sig7, sig8 = data[ch7][-self.num_points:], data[ch8][-self.num_points:]

        for signal in (sig7, sig8):
            DataFilter.detrend(signal, DetrendOperations.LINEAR.value)
            DataFilter.remove_environmental_noise(signal, self.sampling_rate, 2)
            DataFilter.perform_bandpass(signal, self.sampling_rate, 3.0, 45.0, 4, FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)
            DataFilter.perform_bandstop(signal, self.sampling_rate, 50.0, 65.0, 4, FilterTypes.BUTTERWORTH_ZERO_PHASE, 0)

        avg_signal = (np.array(sig7) + np.array(sig8)) / 2.0
        above_thresh = np.any(np.abs(avg_signal) > self.threshold_uv)

        if not self._in_blink and above_thresh:
            self._in_blink = True
            self.blink_detected.emit(self.player)
        elif self._in_blink and not above_thresh:
            self._in_blink = False
