import argparse
import logging
import sys
import time

import threading

import numpy as np

from brainflow.board_shim import BoardShim, BrainFlowInputParams
from brainflow.data_filter import DataFilter, FilterTypes, DetrendOperations



class BlinkDetector(threading.Thread):
    def __init__(self, board_shim, blink_queue, threshold_uv = 200):
        super().__init__()
        self.board_shim = board_shim
        self.board_id = board_shim.get_board_id()
        # Only channels 7 and 8

        self.blink_queue = blink_queue # Queue to communicate blinks to main game thread

        self.eeg_channels = BoardShim.get_eeg_channels(self.board_id)[6:8]
        print("EEG Channels:", self.eeg_channels)

        self.sampling_rate = BoardShim.get_sampling_rate(self.board_id)
        self.num_points = int(2 * self.sampling_rate)

        self.threshold_uv = threshold_uv
        self.blink_count = 0

        self._in_blink = False  # debounce flag
        self.running = True  # Control flag for stopping thread
     
    def run(self):
        while self.running:
            # Call this repeatedly in a loop or thread
            if self.board_shim is None:
                return
            
            data = self.board_shim.get_current_board_data(self.num_points)
            ch7, ch8 = self.eeg_channels
            sig7 = data[ch7][-self.num_points:]
            sig8 = data[ch8][-self.num_points:]
            print(f"Channel 7 data length: {len(sig7)}, Channel 8 data length: {len(sig8)}")

            if len(sig7) < self.num_points or len(sig8) < self.num_points:
                return  # not enough data yet
            
            # Filtering pipeline on both channels
            for signal in (sig7, sig8):
                DataFilter.detrend(signal, DetrendOperations.LINEAR.value)
                DataFilter.remove_environmental_noise(signal, self.sampling_rate, 2)
                DataFilter.perform_bandpass(
                    signal, self.sampling_rate, 3.0, 45.0, 4,
                    FilterTypes.BUTTERWORTH_ZERO_PHASE, 0
                )
                DataFilter.perform_bandstop(
                    signal, self.sampling_rate, 50.0, 65.0, 4,
                    FilterTypes.BUTTERWORTH_ZERO_PHASE, 0
                )

            # Average channels for blink detection
            avg_signal = (np.array(sig7) + np.array(sig8)) / 2.0
            above_thresh = np.any(np.abs(avg_signal) > self.threshold_uv)
            print(f"Avg signal max abs: {np.max(np.abs(avg_signal))}, Above threshold: {above_thresh}")
            # Rising-edge only debounce logic
            if not self._in_blink and above_thresh:
                self.blink_count += 1
                print(f"Blink detected! Total blinks: {self.blink_count}")
                self._in_blink = True
                self.blink_queue.put(True)  # Signal blink
            elif self._in_blink and not above_thresh:
                # Signal returned below threshold ⇒ ready for next blink
                self._in_blink = False
            else:
                # Clear status if no blink
                if not above_thresh:
                    print ("No blink detected.")
            
            time.sleep(0.05)

    def stop(self):
            self.running = False

