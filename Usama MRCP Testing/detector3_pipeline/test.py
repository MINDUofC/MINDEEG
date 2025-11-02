import argparse
import time
import os
import numpy as np
import matplotlib.pyplot as plt

from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
from brainflow.data_filter import DataFilter


def main():
    BoardShim.enable_dev_board_logger()

    parser = argparse.ArgumentParser()
    parser.add_argument('--timeout', type=int, required=False, default=0)
    parser.add_argument('--ip-port', type=int, required=False, default=0)
    parser.add_argument('--ip-protocol', type=int, required=False, default=0)
    parser.add_argument('--ip-address', type=str, required=False, default='')
    parser.add_argument('--serial-port', type=str, required=False, default='COM3')
    parser.add_argument('--mac-address', type=str, required=False, default='')
    parser.add_argument('--other-info', type=str, required=False, default='')
    parser.add_argument('--serial-number', type=str, required=False, default='')
    parser.add_argument('--board-id', type=int, required=False, default=57)
    parser.add_argument('--file', type=str, required=False, default='')
    parser.add_argument('--master-board', type=int, required=False, default=BoardIds.NO_BOARD)
    parser.add_argument('--duration', type=float, required=False, default=10.0)
    parser.add_argument('--outdir', type=str, required=False,
                        default=r"C:\Users\rashe\OneDrive - University of Calgary\Desktop")
    args = parser.parse_args()

    params = BrainFlowInputParams()
    params.ip_port = args.ip_port
    params.serial_port = args.serial_port
    params.mac_address = args.mac_address
    params.other_info = args.other_info
    params.serial_number = args.serial_number
    params.ip_address = args.ip_address
    params.ip_protocol = args.ip_protocol
    params.timeout = args.timeout
    params.file = args.file
    params.master_board = args.master_board

    # Prepare output paths
    os.makedirs(args.outdir, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    pairs_csv = os.path.join(args.outdir, f"packets_{stamp}.csv")
    full_csv  = os.path.join(args.outdir, f"recording_{stamp}.csv")

    board = BoardShim(args.board_id, params)
    try:
        board.prepare_session()
        board.start_stream()
        time.sleep(3.0)

        commands = [
            "chon_1_1", 
            #"rldadd_1", 
            #"chon_2_0", 
            #"rldadd_2",
            #"chon_3_0", 
            #"rldadd_3", 
            #"chon_4_0", 
            #"rldadd_4",
            #"chon_5_0", 
            #"rldadd_5", 
            #"chon_6_0", 
            #"rldadd_6",
            #"chon_7_0", 
            #"rldadd_7", 
            #"chon_8_0", 
            #"rldadd_8"
        ]
        for cmd in commands:
            board.config_board(cmd)
            time.sleep(1.0)

        time.sleep(2.0)
        board.get_board_data()  # clear buffer after cfg
        time.sleep(float(args.duration))

        board.stop_stream()
        data = board.get_board_data()  # shape: [rows, samples]

        ts_ch = BoardShim.get_timestamp_channel(args.board_id)
        try:
            pkt_ch = BoardShim.get_package_num_channel(args.board_id)
        except Exception:
            print("No package channel")
            pkt_ch = -1

        timestamps = data[ts_ch, :] if ts_ch is not None and ts_ch >= 0 else np.array([])
        if pkt_ch is not None and pkt_ch >= 0:
            packets = data[pkt_ch, :]
        else:
            print("No package channel using timestamps")
            packets = np.arange(timestamps.size, dtype=np.int64)

        # Save pairs (unchanged formatting)
        pair_mat = np.vstack([timestamps, packets]).T
        header = "timestamp_s,packet_number"
        np.savetxt(pairs_csv, pair_mat, delimiter=",", header=header, comments="", fmt="%.25f,%d")
        print(f"Saved timestamp/packet pairs -> {pairs_csv}")

        # Full dump (unchanged formatting)
        DataFilter.write_file(data, full_csv, "w")
        print(f"Saved full BrainFlow dump -> {full_csv}")

        # =========================
        # EXISTING PLOTS
        # =========================
        eeg_rows = BoardShim.get_eeg_channels(args.board_id)
        eeg_sig = data[eeg_rows[0], :] if len(eeg_rows) else np.array([])

        if timestamps.size:
            delta_t = np.diff(timestamps, prepend=timestamps[0])
        else:
            delta_t = np.array([])

        n = min(timestamps.size, packets.size,
                delta_t.size if delta_t.size else timestamps.size,
                eeg_sig.size if eeg_sig.size else timestamps.size)
        t   = timestamps[:n]
        pkt = packets[:n]
        dt  = delta_t[:n] if delta_t.size else np.array([])
        d_pkt = (np.diff(pkt, prepend=pkt[0]) % 256) if pkt.size else np.array([])

        if dt.size:
            dt_pos = dt[dt > 0]
            if dt_pos.size:
                print(f"Median Δt = {np.median(dt_pos):.6f} s, fs ≈ {1.0/np.median(dt_pos):.3f} Hz")
        print(f"First 10 timestamps: {t[:10]}")
        print(f"First 10 packets: {pkt[:10]}")
        if dt.size: print(f"First 10 Δt: {dt[:10]}")

        fig, axs = plt.subplots(3, 1, figsize=(12, 8), sharex=True, constrained_layout=True)
        if eeg_sig.size:
            axs[0].plot(t, eeg_sig[:n], linewidth=1)
            axs[0].set_ylabel(f'EEG[{eeg_rows[0]}]')
            axs[0].set_title('EEG sample stream')
            axs[0].grid(True, alpha=0.3)
        else:
            axs[0].text(0.5, 0.5, 'No EEG channel to plot', ha='center', va='center')
            axs[0].set_title('EEG sample stream')

        axs[1].plot(t, pkt, linewidth=1, label='packet# (0–255)')
        if d_pkt.size:
            axs[1].scatter(t, d_pkt, s=6, label='Δpacket (mod 256)')
        axs[1].set_ylabel('packet#')
        axs[1].set_title('Packet counter & per-sample increment')
        axs[1].grid(True, alpha=0.3)
        axs[1].legend(loc='upper right')

        if dt.size:
            axs[2].plot(t, dt, linewidth=1)
            if dt_pos.size:
                axs[2].axhline(np.median(dt_pos), linestyle='--', linewidth=1, label='median Δt')
                axs[2].legend()
        else:
            axs[2].text(0.5, 0.5, 'No timestamps -> no Δt', ha='center', va='center')
        axs[2].set_ylabel('Δt (s)')
        axs[2].set_xlabel('Device timestamp (s)')
        axs[2].set_title('Inter-arrival time')
        axs[2].grid(True, alpha=0.3)

        # =========================
        # NEW WINDOW: FFT + PSD
        # =========================
        if eeg_sig.size:
            # Choose sampling rate: prefer timestamp-derived, else board nominal
            fs_nom = BoardShim.get_sampling_rate(args.board_id)
            fs_est = 1.0 / np.median(dt_pos) if dt.size and dt_pos.size else fs_nom
            if 0.5 * fs_nom <= fs_est <= 2.0 * fs_nom:
                fs = fs_est
            else:
                fs = fs_nom

            x = eeg_sig.astype(np.float64, copy=False)
            x = x - np.mean(x)

            # --- FFT (single-sided) with Hann taper ---
            N = len(x)
            w = np.hanning(N)
            cg = w.mean()                 # coherent gain for Hann (≈ 0.5)
            xw = (x - np.mean(x)) * w     # you already remove the mean

            nfft = 1 << int(np.ceil(np.log2(max(1, N))))
            X = np.fft.rfft(xw, n=nfft)
            freqs = np.fft.rfftfreq(nfft, d=1.0/fs)

            # amplitude spectrum, compensate coherent gain; then single-sided correction
            mag = np.abs(X) / (N * cg)
            if nfft > 1:
                mag[1:-1] *= 2.0
            # --- PSD ---
            try:
                from scipy.signal import welch
                # segment ~4 seconds if possible for good variance/reln
                seg = int(min(max(fs*4, fs), N))
                psd_f, psd_p = welch(x, fs=fs, nperseg=seg, noverlap=seg//2)
            except Exception:
                # Fallback: simple periodogram
                psd_f = freqs
                psd_p = (np.abs(X)**2) / (fs * N)

            fig2, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), constrained_layout=True)

            ax1.plot(freqs, mag, lw=1)
            ax1.set_xlim(0, fs/2)
            ax1.set_title("Single-sided FFT magnitude")
            ax1.set_xlabel("Frequency (Hz)")
            ax1.set_ylabel("Amplitude")
            ax1.grid(True, alpha=0.3)

            ax2.plot(psd_f, psd_p, lw=1)
            ax2.set_xlim(0, fs/2)
            ax2.set_title("Power Spectral Density")
            ax2.set_xlabel("Frequency (Hz)")
            ax2.set_ylabel("Power/Hz")
            ax2.grid(True, alpha=0.3)

        plt.show()

    finally:
        board.release_session()


if __name__ == "__main__":
    main()
