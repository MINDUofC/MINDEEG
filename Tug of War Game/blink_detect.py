import time
import threading
import logging
import numpy as np
from brainflow.board_shim import BoardShim
from brainflow.data_filter import DataFilter, FilterTypes, DetrendOperations

class BlinkDetector(threading.Thread):
    def __init__(self, board_shim, blink_queue, threshold_uv = 200):
        super().__init__()
        self.board_shim = board_shim
        self.board_id = board_shim.get_board_id()
        self.blink_queue = blink_queue # Queue to communicate blinks to main game thread

        eeg_all = BoardShim.get_eeg_channels(self.board_id)
        self.eeg_channels = eeg_all[6:8] if len(eeg_all) >= 8 else eeg_all[-2:]
        logging.info(f"Blink EEG Channels: {self.eeg_channels}")

        self.sampling_rate = BoardShim.get_sampling_rate(self.board_id)
        self.num_points = int(2 * self.sampling_rate)
        if self.num_points % 2 == 1:
            self.num_points -= 1

        self.threshold_uv = threshold_uv
        self.blink_count = 0

        self._in_blink = False  # debounce flag
        self.running = True  # Control flag for stopping thread
     
    def run(self):
        while self.running:
            # Call this repeatedly in a loop or thread
            if self.board_shim is None:
                time.sleep(0.05)
                continue
            try:
                data = self.board_shim.get_current_board_data(self.num_points)
                if data.shape[1] < self.num_points:
                    time.sleep(0.05)
                    continue
                signals = []
                for ch in self.eeg_channels:
                    sig = np.copy(data[ch][-self.num_points:])
                    DataFilter.detrend(sig, DetrendOperations.LINEAR.value)
                    DataFilter.remove_environmental_noise(sig, self.sampling_rate, 2)
                    DataFilter.perform_bandpass(sig, self.sampling_rate, 3.0, 45.0, 4,
                                                FilterTypes.BUTTERWORTH_ZERO_PHASE.value, 0)
                    DataFilter.perform_bandstop(sig, self.sampling_rate, 50.0, 65.0, 4,
                                                FilterTypes.BUTTERWORTH_ZERO_PHASE.value, 0)
                    signals.append(sig)

                # Average channels for blink detection
                avg_signal = np.mean(np.vstack(signals), axis=0)
                above_thresh = np.any(np.abs(avg_signal) > self.threshold_uv)
                logging.info(f"Avg signal max abs: {np.max(np.abs(avg_signal))}, Above threshold: {above_thresh}")
            
                # Rising-edge only debounce logic
                if not self._in_blink and above_thresh:
                    self.blink_count += 1
                    logging.info(f"Blink detected! Total blinks: {self.blink_count}")
                    self._in_blink = True
                    try:
                        self.blink_queue.put_nowait(True)  # Signal blink
                    except Exception as e:
                        logging.error(f"Error putting blink in queue: {e}")
                        pass
                elif self._in_blink and not above_thresh:
                    # Signal returned below threshold ⇒ ready for next blink
                    self._in_blink = False
            except Exception as e:
                logging.error(f"Error in blink detection loop: {e}")
                pass
            time.sleep(0.05)

    def stop(self):
        self.running = False
        try:
            self.board_shim.stop_stream()
        except Exception:
            pass
        try:
            if self.board_shim.is_prepared():
                self.board_shim.release_session()
        except Exception:
            pass
       