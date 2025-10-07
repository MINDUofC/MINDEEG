"""
Menu Handler Module for MINDStream EEG Application
Handles MenuOptions combo box functionality and dialog displays.
"""

from PyQt5.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea
from PyQt5.QtCore import Qt


DIALOG_STYLESHEET = """
    QDialog { 
        border-radius: 12px; 
        border: 2px solid #0047B2;
        background-color: #d7d7d7;
    }
    QLabel { 
        font-family: 'Montserrat SemiBold';
        color: #0A1F44; 
        border: none; 
        padding: 20px;
        background-color: transparent;
    }
    QLabel h1, QLabel h2, QLabel h3 {
        font-family: 'Montserrat Bold';
        color: #0A1F44;
    }
    QLabel b, QLabel strong {
        font-family: 'Montserrat Bold';
    }
    QLabel p {
        font-family: 'Montserrat SemiBold';
        line-height: 1.4;
    }
    QLabel p b, QLabel p strong {
        font-family: 'Montserrat Bold';
    }
    QLabel li {
        font-family: 'Montserrat SemiBold';
        line-height: 1.4;
    }
    QLabel li b, QLabel li strong {
        font-family: 'Montserrat Bold';
    }
    QPushButton { 
        font-family: 'Montserrat SemiBold'; 
        color: #0A1F44; 
        background-color: #FFFFFF; 
        border: 2px solid #0047B2; 
        min-width: 80px; 
        min-height: 35px; 
        border-radius: 18px; 
        padding: 8px 16px; 
    }
    QPushButton:hover { background-color: #F5F9FF; border-color: #1E63D0; }
    QPushButton:pressed { background-color: #EAF4FF; }
    QScrollArea { 
        border: none; 
        background-color: transparent; 
    }
    QScrollBar:vertical {
        background-color: #E8F2FF;
        width: 12px;
        border-radius: 6px;
        border: 1px solid #0047B2;
        margin: 0px;
    }
    QScrollBar::handle:vertical {
        background-color: #5C8FFF;
        border-radius: 10px;
        border: 1px solid #0047B2;
        min-height: 20px;
        margin: 1px;
    }
    QScrollBar::handle:vertical:hover {
        background-color: #4A7EE8;
    }
    QScrollBar::handle:vertical:pressed {
        background-color: #3A6ED6;
    }
    QScrollBar::add-line:vertical {
        height: 0px;
    }
    QScrollBar::sub-line:vertical {
        height: 0px;
    }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: transparent;
    }
"""



class MenuHandler:
    """Handles menu option selections and displays appropriate dialogs."""
    
    def __init__(self, parent_widget, menu_combo_box):
        """
        Initialize the menu handler.
        
        Args:
            parent_widget: The main application window (for dialog parent)
            menu_combo_box: The MenuOptions QComboBox widget
        """
        self.parent = parent_widget
        self.menu_combo = menu_combo_box
        
        # Connect the combo box signal
        if self.menu_combo is not None:
            self.menu_combo.currentTextChanged.connect(self.on_menu_option_selected)
            self._ensure_menu_items()
    
    def on_menu_option_selected(self, text):
        """Handle MenuOptions combo box selection."""
        if text == "About Us":
            self.show_about_us_dialog()
            # Reset combo box to default
            self.menu_combo.setCurrentText("Menu")
        elif text == "How to Use?":
            self.show_how_to_use_dialog()
            # Reset combo box to default
            self.menu_combo.setCurrentText("Menu")
        elif text == "Understanding Data Files":
            self.show_csv_data_guide_dialog()
            # Reset combo box to default
            self.menu_combo.setCurrentText("Menu")
        elif text == "Signal Processing Guide":
            self.show_signal_processing_guide_dialog()
            self.menu_combo.setCurrentText("Menu")
        elif text == "Recording Guide":
            self.show_recording_guide_dialog()
            self.menu_combo.setCurrentText("Menu")
        elif text == "Timing & Cues Guide":
            self.show_timing_cues_guide_dialog()
            self.menu_combo.setCurrentText("Menu")
        elif text == "FFT & PSD Explained":
            self.show_fft_psd_guide_dialog()
            self.menu_combo.setCurrentText("Menu")
        elif text == "Data Shapes":
            self.show_data_shapes_dialog()
            self.menu_combo.setCurrentText("Menu")

    def _ensure_menu_items(self):
        """Ensure extended menu items exist; add them if missing."""
        try:
            existing = set(self.menu_combo.itemText(i) for i in range(self.menu_combo.count()))
            additions = [
                "How to Use?",
                "Signal Processing Guide",
                "Recording Guide",
                "Timing & Cues Guide",
                "FFT & PSD Explained",
                "Data Shapes",
                "Understanding Data Files",
                "About Us",
            ]
            for item in additions:
                if item not in existing:
                    self.menu_combo.addItem(item)
        except Exception:
            pass
    
    def create_custom_dialog(self, title, content, width=600, height=400):
        """Create a custom dialog with proper sizing and layout control."""
        dialog = QDialog(self.parent)
        dialog.setWindowTitle(title)
        dialog.setStyleSheet(DIALOG_STYLESHEET)
        dialog.setFixedSize(width, height)
        dialog.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        
        # Main layout
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Scrollable content area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Content widget
        content_widget = QLabel(content)
        content_widget.setTextFormat(Qt.RichText)
        content_widget.setWordWrap(True)
        content_widget.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        content_widget.setContentsMargins(20, 20, 20, 20)
        # Enable clickable links and text selection
        content_widget.setOpenExternalLinks(True)
        content_widget.setTextInteractionFlags(Qt.TextBrowserInteraction)
        
        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)
        
        # Button layout
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(dialog.accept)
        button_layout.addWidget(ok_button)
        button_layout.addStretch()
        
        # Add button layout to main layout with some spacing
        button_widget = QLabel()  # Spacer
        button_widget.setFixedHeight(10)
        layout.addWidget(button_widget)
        layout.addLayout(button_layout)
        
        # Add bottom spacing
        bottom_spacer = QLabel()
        bottom_spacer.setFixedHeight(15)
        layout.addWidget(bottom_spacer)
        
        return dialog
    
    def show_about_us_dialog(self):
        """Show About Us information dialog."""
        about_text = """
<h2>About This Application</h2>

<p><b>Developer:</b> <a href="https://www.linkedin.com/in/taha--malik/" target="_blank">Taha Malik</a></p>

<p><b>Version:</b> 1.0.0<br>
<b>Development Phase:</b> April 2025 to September 2025</p>

<p><b>Purpose:</b> This application was created to help people who are interested in EEGs to collect data, visualize EEG signals, and experiment with brain-computer interfaces. It provides an accessible platform for researchers, students, and enthusiasts to explore the fascinating world of neural dynamics.</p>

<p><b>Compatibility:</b> Currently compatible with NeuroPawn boards. Version 2.0.0 coming soon will work with all boards from the BrainFlow library (up to 60 boards!).</p>

<p><b>Open Source:</b> This GUI is fully open source and available to all. You can tweak the code, contribute improvements, and customize it for your specific needs.</p>

<p><b>Sponsors & Contributors:</b><br>
• <b>MIND</b> (Mechatronics Integration of Neural Dynamics)<br>
• <b>NeuroPawn</b><br>
• <b>University of Calgary's Schulich School of Engineering</b></p>

<p>We thank all contributors for their support in making this project possible.</p>
        """
        
        dialog = self.create_custom_dialog("About MINDStream EEG", about_text, 650, 450)
        dialog.exec_()
    
    def show_how_to_use_dialog(self):
        """Show How to Use information dialog."""
        how_to_text = """
<h2>How to Use MINDStream EEG</h2>

<h3>Overview</h3>
<p>MINDStream EEG connects a <b>NeuroPawn</b> board (Board ID <b>57</b>), provides live visualization (µV, FFT, PSD), and records synchronized data with a cue-based timing engine running at <b>125 Hz</b>.</p>

<h3>1. Board Setup</h3>
<ol>
  <li><b>Hardware:</b> Connect the NeuroPawn EEG via USB (currently Board ID <b>57</b> only).</li>
  <li><b>Port Selection:</b> Click the <b>Port</b> combobox to scan and refresh available COM ports. Select your device port.</li>
  <li><b>Channel Dial (1–8):</b> Set the number of active EEG channels. Must be >0 to turn on the board.</li>
  <li><b>Common Reference (Optional):</b> Check to enable RLD (right-leg drive) common reference mode.</li>
  <li><b>Turn On Board:</b> Check <b>Board On/Off</b>. Internally, the app:
    <ul>
      <li>Creates a BrainFlow session with <code>timeout=15s</code>.</li>
      <li>Starts streaming with ring-buffer size <b>450000</b>.</li>
      <li>Clears the buffer and waits 2 seconds for initialization.</li>
      <li>Sends per-channel commands: <code>chon_{n}_12</code> (enables channel with gain <b>12</b>) and optional <code>rldadd_{n}</code> (common reference).</li>
      <li>Waits 0.25s between commands for hardware stability.</li>
      <li>Locks the Board ID, Port, Channel Dial, and Common Reference controls while the board is on.</li>
    </ul>
  </li>
  <li><b>Status Messages:</b> Top <b>StatusBar</b> shows: "Turning on…" → "Successful On" or error details.</li>
  <li><b>Turn Off:</b> Unchecking releases the session and re-enables all board controls.</li>
  <li><b>Sampling Rate:</b> Fixed at <b>125 Hz</b> throughout the application.</li>
</ol>

<h3>2. Visualization Tabs</h3>
<ul>
  <li><b>µV (Microvolt Time Domain):</b> Live multi-channel traces; each channel rendered with preprocessing applied.</li>
  <li><b>FFT (Fast Fourier Transform):</b> Frequency-domain amplitude spectrum per channel, up to Nyquist (62.5 Hz).</li>
  <li><b>PSD (Power Spectral Density):</b> Power per frequency bin per channel (Welch-style averaging).</li>
  <li><b>No Plot:</b> Empty tab with friendly message; use when your computer cannot handle live rendering + timer simultaneously.</li>
</ul>

<h3>3. Preprocessing Controls (Summary)</h3>
<p>See <b>Signal Processing Guide</b> for exhaustive details. High-level:</p>
<ul>
  <li><b>Environmental Noise:</b> 50/60 Hz removal applied automatically before all user settings.</li>
  <li><b>Detrend:</b> Linear detrend to remove DC drift.</li>
  <li><b>Band-Pass:</b> Up to 2 filters; IIR Butterworth order <b>4</b> or FIR <b>101 taps</b> zero-phase. Supports low/high/band modes.</li>
  <li><b>Band-Stop (Notch):</b> Up to 2 filters for removing narrow artifacts (e.g., 60 Hz). Same IIR/FIR choices.</li>
  <li><b>FastICA:</b> Requires ≥2 channels; calibration period default <b>8 s</b> (range 3–30). Automated artifact suppression.</li>
  <li><b>Smoothing:</b> Average or Median (mutually exclusive) over <b>Window</b> samples.</li>
</ul>

<h3>4. Recording & Timing</h3>
<ul>
  <li><b>BeforeOnset (s):</b> Anticipation window before movement onset (default 3 s).</li>
  <li><b>AfterOnset (s):</b> Response window after onset (default 3 s).</li>
  <li><b>TimeBetweenTrials (s):</b> Buffer interval between trials (default 3 s).</li>
  <li><b>NumOfTrials:</b> Total trials per run (default 5).</li>
  <li><b>Record / Stop:</b> Starts/stops the <b>TimingEngine (125 Hz master tick)</b> and recording.</li>
  <li><b>Data Types:</b> Select Raw µV, FFT, PSD. Choose file format (CSV only).</li>
  <li><b>Export Destination:</b> Set folder; persisted in <code>export_destination.txt</code>; validated on startup.</li>
  <li><b>Export Button:</b> Saves cached data to separate CSV files per type with datetime naming.</li>
  <li><b>⚠️ Important:</b> Starting a new recording clears all cached data. Export immediately after each session or record all desired types together.</li>
</ul>

<h3>5. Timeline Visualizer vs. Black Screen Timer</h3>
<ul>
  <li><b>Timeline:</b> Embedded progress bars (blue = trial; orange = buffer) with time labels (<b>Total Time</b>, <b>Trial Time</b>). Resets on stop/complete.</li>
  <li><b>Black Screen Timer (BlackScreenTimer button):</b> Full-screen cue display window. Shows symbols (✚ anticipation → cue at onset → ⬛ buffer → ✅ complete). Always-visible Record/Stop; collapsible legend/config. Mutual exclusion: opening stops timeline mode and freezes visuals; closing resets everything.</li>
</ul>

<h3>6. Status Indicators</h3>
<ul>
  <li><b>StatusBar (main):</b> Shows board/run state ("Successful On", "Recording started", "Recording stopped", "All Trials Completed!", "Nothing to stop!").</li>
  <li><b>ExportStatus:</b> Shows export readiness. Only shows "Recording complete - Ready to export" if recording actually occurred (not just timer-only mode).</li>
</ul>

<h3>7. AI Chatbot</h3>
<p>Click the chat icon (bottom-right) for real-time help. The first time you open it, the app may prompt to download a ~4.66 GB local LLM (requires CUDA-enabled GPU recommended). The toggle button is locked during initialization to avoid QThread disruption; it re-enables on success or failure.</p>

<h3>8. Tips</h3>
<ul>
  <li>Always verify µV signal quality (good electrode contact, minimal drift) before starting experiments.</li>
  <li>Use <b>No Plot</b> tab during recording if your system cannot render live graphs smoothly.</li>
  <li>Minimize subject movement and ensure stable power supply.</li>
  <li><b>Data Management:</b> Export data immediately after each recording session. Starting a new recording clears all cached data from previous sessions.</li>
</ul>
        """
        
        dialog = self.create_custom_dialog("How to Use MINDStream EEG", how_to_text, 780, 600)
        dialog.exec_()
    
    def show_csv_data_guide_dialog(self):
        """Show CSV Data Structure Guide dialog."""
        csv_guide_text = """
<h2>CSV Data Structures</h2>

<h3>Raw µV (Long Format)</h3>
<p>Each row is a single timestamp to accommodate spreadsheet tools that prefer many rows over columns.</p>
<pre>ch1, ch2, ch3, ch4, ch5, ch6, ch7, ch8, global_s, trial_s</pre>
<ul>
  <li><b>global_s:</b> Run-relative seconds.</li>
  <li><b>trial_s:</b> Onset-relative seconds. During buffer rows, values are prefixed with <b>"B - "</b>.</li>
  <li>Values are floating-point with 10 decimal places.</li>
  <li>Ordering is preserved across channels.</li>
  <li>Sampling aligned to engine ticks at 125 Hz.</li>
  
</ul>

<h3>FFT (Frequency Amplitudes)</h3>
<p>Header contains the frequency vector. Each subsequent row is one timestamp with concatenated bins per channel.</p>
<pre>[trial_s, global_s, ch1_bin1..ch1_binN, ch2_bin1..ch2_binN, ..., ch8_bin1..ch8_binN]</pre>

<h3>PSD (Power Spectral Density)</h3>
<p>Same structure as FFT, but values are power per frequency bin. Frequency header included.</p>
        """
        
        dialog = self.create_custom_dialog("CSV Data Structure Guide", csv_guide_text, 800, 600)
        dialog.exec_()

    def show_signal_processing_guide_dialog(self):
        text = """
<h2>Signal Processing Guide</h2>

<h3>Always-On: Environmental Noise Removal</h3>
<p>Before any user-selected processing, the app applies <b>50/60 Hz removal</b> via BrainFlow's <code>remove_environmental_noise(NoiseTypes.FIFTY_AND_SIXTY)</code> to every EEG channel. This step is <b>not optional</b> and eliminates mains hum automatically.</p>

<h3>Detrend</h3>
<ul>
  <li><b>Control:</b> DetrendOnOff checkbox.</li>
  <li><b>Method:</b> BrainFlow linear detrend (<code>DetrendOperations.LINEAR</code>). Subtracts a best-fit line to remove slow DC drift.</li>
  <li><b>When to use:</b> Electrode drift, very low-frequency content not of interest.</li>
</ul>

<h3>Band-Pass Filtering (Low / High / Band)</h3>
<p><b>User Controls:</b></p>
<ul>
  <li><b>BandPassOnOff:</b> Master enable.</li>
  <li><b>NumberBandPass (0–2):</b> Number of filter slots.</li>
  <li><b>BP1Start / BP1End, BP2Start / BP2End:</b> Frequency ranges (Hz). Blank/zero start → low-pass; blank/zero end → high-pass; both present (start < end) → band-pass.</li>
  <li><b>BPTypeFIR_IIR:</b> Choose IIR or FIR.</li>
  <li><b>FIRWindowType (if FIR selected):</b> Hamming, Hann, Blackman, Kaiser (β=8), Flat Top.</li>
</ul>
<p><b>Implementation Details:</b></p>
<ul>
  <li><b>IIR Mode:</b> Butterworth, <code>order=4</code>, <code>ripple=0</code>. Uses BrainFlow <code>perform_bandpass/lowpass/highpass</code> with <code>FilterTypes.BUTTERWORTH</code>.</li>
  <li><b>FIR Mode:</b> Windowed FIR with <code>numtaps=101</code>, zero-phase via <code>scipy.signal.filtfilt</code>. Windows are applied via <code>scipy.signal.firwin</code>. Preserves array length and avoids phase shift.</li>
  <li><b>Not User-Controlled:</b> IIR order (4), FIR taps (101), zero-phase method, invalid range guards.</li>
</ul>

<h3>Band-Stop (Notch) Filtering</h3>
<p><b>User Controls:</b></p>
<ul>
  <li><b>BandStopOnOff:</b> Master enable.</li>
  <li><b>NumberBandStop (0–2):</b> Number of notch slots.</li>
  <li><b>BStop1Start / BStop1End, BStop2Start / BStop2End:</b> Frequency ranges. Blank/zero start → high-pass; blank/zero end → low-pass; both present → notch.</li>
  <li>Same FIR/IIR and window options as Band-Pass.</li>
</ul>
<p><b>Implementation Details:</b></p>
<ul>
  <li><b>IIR:</b> Butterworth, <code>order=4</code>, <code>ripple=0</code>. Uses BrainFlow <code>perform_bandstop/highpass/lowpass</code>.</li>
  <li><b>Not User-Controlled:</b> Same constraints as Band-Pass.</li>
</ul>

<h3>Smoothing Filters</h3>
<p><b>User Controls:</b></p>
<ul>
  <li><b>Average:</b> Checkbox; applies BrainFlow <code>perform_rolling_filter(window, AggOperations.MEAN)</code>.</li>
  <li><b>Median:</b> Checkbox; applies BrainFlow <code>perform_rolling_filter(window, AggOperations.MEDIAN)</code>.</li>
  <li><b>Window:</b> Spin box; number of samples in the rolling window.</li>
  <li><b>Mutually Exclusive:</b> Enabling Average unchecks Median and vice versa.</li>
</ul>

<h3>Independent Component Analysis (ICA)</h3>
<p><b>Requirements:</b></p>
<ul>
  <li>≥ <b>2</b> channels (Channel Dial). The FastICA checkbox is disabled if <2 channels; enabled automatically when ≥2 channels and board is on.</li>
</ul>
<p><b>User Controls:</b></p>
<ul>
  <li><b>FastICA Checkbox:</b> Enable/disable.</li>
  <li><b>ICACalibSecs:</b> Calibration duration in seconds (range 3–30; default <b>8</b>).</li>
</ul>
<p><b>Implementation (sklearn FastICA):</b></p>
<ul>
  <li><b>Algorithm:</b> FastICA fixed-point with the following hyperparameters:
    <ul>
      <li><code>n_components</code> = number of active channels.</li>
      <li><code>whiten='unit-variance'</code></li>
      <li><code>max_iter=200</code></li>
      <li><code>tol=1e-4</code></li>
      <li><code>random_state=42</code></li>
    </ul>
  </li>
  <li><b>Workflow:</b>
    <ol>
      <li>Check FastICA; app enters <b>CALIBRATING</b> state.</li>
      <li>Collects data for the specified calibration period.</li>
      <li>Fits ICA model (learns unmixing matrix).</li>
      <li>Enters <b>ACTIVE</b> state: transforms incoming data, suppresses artifacts automatically, inverse-transforms back to channel space.</li>
    </ol>
  </li>
  <li><b>Artifact Suppression:</b> Components with |kurtosis| > <b>10.0</b> are zeroed automatically (kurtosis measures non-Gaussianity; high kurtosis often = eye blinks or muscle artifacts).</li>
  <li><b>Not User-Controlled:</b> All hyperparameters above, kurtosis threshold (10.0), component selection heuristic.</li>
  <li><b>Fallback:</b> If sklearn unavailable, ICA gracefully disables.</li>
  <li><b>Minimum samples:</b> <b>100</b> valid (non-NaN) samples required to fit ICA; otherwise the fit fails and checkbox unchecks.</li>
</ul>

<h3>Typical EEG Frequency Bands</h3>
<ul>
  <li><b>Delta:</b> 0.5–4 Hz (deep sleep)</li>
  <li><b>Theta:</b> 4–7 Hz (drowsiness, meditation)</li>
  <li><b>Alpha:</b> 8–13 Hz (relaxed wakefulness, eyes closed; strongest occipitally)</li>
  <li><b>Beta:</b> 13–30 Hz (active thinking, motor cortex activity)</li>
  <li><b>Gamma:</b> >30 Hz (cognitive tasks, sensory processing)</li>
</ul>
        """
        dialog = self.create_custom_dialog("Signal Processing Guide", text, 850, 680)
        dialog.exec_()

    def show_recording_guide_dialog(self):
        text = """
<h2>Recording Guide</h2>

<h3>Timing Parameters (User Controls)</h3>
<ul>
  <li><b>BeforeOnset (QSpinBox):</b> Seconds before movement onset (anticipation window). Default <b>3</b>, minimum <b>1</b>.</li>
  <li><b>AfterOnset (QSpinBox):</b> Seconds after onset (response window). Default <b>3</b>, minimum <b>1</b>.</li>
  <li><b>TimeBetweenTrials (QSpinBox):</b> Buffer interval between trials. Default <b>3</b>.</li>
  <li><b>NumOfTrials (QLineEdit, integer-only):</b> Total trials per run. Default <b>5</b>.</li>
</ul>

<h3>Timing Engine (Not User-Controlled)</h3>
<ul>
  <li><b>Master Cadence:</b> <b>125 Hz</b> (8 ms tick) via QTimer PreciseTimer.</li>
  <li><b>Phases:</b> trial | buffer | idle.</li>
  <li><b>Timers:</b> <code>QElapsedTimer</code> for global run time and trial-relative time.</li>
  <li><b>trial_s:</b> Computed as <code>(trial_timer.elapsed() / 1000.0) - BeforeOnset</code>.</li>
  <li><b>global_s:</b> Run-elapsed time in seconds (resets per run).</li>
  <li><b>Signals:</b> <code>tick_8ms(now_ms, sched_ms)</code>, <code>state_changed(run_active, recording_enabled)</code>, <code>phase_changed(phase, trial_index)</code>, <code>trial_started(trial_index)</code>, <code>run_completed()</code>.</li>
</ul>

<h3>Timeline Visualizer (Embedded Mode)</h3>
<ul>
  <li><b>Blue Bar:</b> Fills from left (-BeforeOnset) to right (+AfterOnset) as the trial progresses.</li>
  <li><b>Orange Buffer Bar (Vertical):</b> Fills upward during buffer interval.</li>
  <li><b>Labels:</b> <b>Total Time</b> (run-elapsed), <b>Trial Time</b> (onset-relative, can be negative during anticipation).</li>
  <li><b>Reset:</b> On stop or completion, labels → "0s", bars emptied, fractions cleared.</li>
</ul>

<h3>Black Screen Timer (Cue-Based Paradigm Window)</h3>
<ul>
  <li><b>Symbols:</b>
    <ul>
      <li><b>✚:</b> Anticipation phase (trial_time < 0).</li>
      <li><b>→, ←, ↑, ↓, 🟢:</b> Configurable cue at onset (trial_time crosses 0).</li>
      <li><b>⬛:</b> Buffer between trials.</li>
      <li><b>✅:</b> Completion (shows for 2s, then → ⚙️).</li>
      <li><b>🛑:</b> Stop pressed during run/recording (shows 2s, then → ⚙️).</li>
      <li><b>⚙️:</b> Idle (no active run).</li>
    </ul>
  </li>
  <li><b>Cue Configuration:</b> Collapsible legend/config panel; choose separate cues for odd/even trials and order mode (Alternating / Fixed / Random).</li>
  <li><b>Always-Visible Controls:</b> Record/Stop buttons; work identically to main dashboard buttons.</li>
  <li><b>Mutual Exclusion:</b>
    <ul>
      <li>Opening: If a run is active, stops and resets. Freezes Timeline visuals (setUpdatesEnabled(False)) and disables main Record/Stop buttons.</li>
      <li>Closing: Stops/resets run if active, unfreezes Timeline visuals, re-enables main Record/Stop.</li>
      <li>Minimizing/hiding does <b>not</b> re-enable Timeline; only actual close does.</li>
    </ul>
  </li>
</ul>

<h3>Data Selection & Export</h3>
<ul>
  <li><b>RawData (µV):</b> Time-domain samples per channel.</li>
  <li><b>FFTData:</b> Frequency-domain amplitude bins.</li>
  <li><b>PSDData:</b> Power per frequency bin.</li>
  <li><b>FileType:</b> CSV only (at present).</li>
  <li><b>Export Destination:</b> Folder path; persisted in <code>backend_logic/export_destination.txt</code>; validated on app startup.</li>
  <li><b>Export Button:</b> Saves cached data to <code>record{Type}_{datetime}.csv</code> (one file per selected type).</li>
  <li><b>Data Cache Behavior:</b> <b>Important:</b> Starting a new recording session clears all previously cached data. If you record muV first, then start a new recording for FFT, the muV data is lost. Export data immediately after each recording session, or record all desired data types in a single session.</li>
</ul>

<h3>Status Messages</h3>
<ul>
  <li><b>StatusBar (main):</b>
    <ul>
      <li>"Recording started" if board on + valid settings.</li>
      <li>"Board OFF: Timer only (not recording)" if board off.</li>
      <li>"Recording stopped" on stop.</li>
      <li>"All Trials Completed!" on natural run completion.</li>
      <li>"Nothing to stop!" if stop clicked with no active run/recording.</li>
    </ul>
  </li>
  <li><b>ExportStatus:</b> Shows "Recording complete - Ready to export" <b>only</b> if <code>is_recording</code> was True and data types were selected.</li>
</ul>
        """
        dialog = self.create_custom_dialog("Recording Guide", text, 880, 700)
        dialog.exec_()

    def show_timing_cues_guide_dialog(self):
        text = """
<h2>Timing & Cues Guide</h2>

<h3>TimingEngine (125 Hz Master)</h3>
<p>A centralized <code>TimingEngine</code> drives all timing via <code>QTimer</code> with <code>PreciseTimer</code> type at <b>8 ms intervals</b> (125 Hz). It emits signals for trial/buffer transitions and tick updates.</p>
<ul>
  <li><b>Phases:</b> trial | buffer | idle.</li>
  <li><b>Timers:</b> <code>global_timer</code> (run-elapsed) and <code>trial_timer</code> (trial-elapsed) using <code>QElapsedTimer</code> for millisecond precision.</li>
  <li><b>Trial time calculation:</b> <code>trial_s = (trial_timer.elapsed() ms / 1000.0) - BeforeOnset</code>; negative values during anticipation.</li>
  <li><b>Signals:</b>
    <ul>
      <li><code>tick_8ms(now_ms, sched_ms)</code>: Emitted every 8 ms; drives UI and recording sampling.</li>
      <li><code>state_changed(run_active, recording_enabled)</code></li>
      <li><code>phase_changed(phase, trial_index)</code></li>
      <li><code>trial_started(trial_index)</code></li>
      <li><code>run_completed()</code></li>
    </ul>
  </li>
</ul>

<h3>Black Screen Cue Logic (Onset Detection)</h3>
<p>The dialog monitors <code>trial_timer</code> and <code>BeforeOnset</code> to compute <code>trial_time_ms</code>. Symbol updates occur on threshold crossings:</p>
<ul>
  <li><b>trial_time < 0:</b> ✚ (anticipation).</li>
  <li><b>trial_time crosses 0 (prev < 0, now ≥ 0):</b> Instant switch to configured cue (→, ←, ↑, ↓, 🟢).</li>
  <li><b>Buffer phase:</b> ⬛ (engine.phase == "buffer").</li>
  <li><b>Run complete:</b> ✅ for 2 s, then ⚙️.</li>
  <li><b>Stop clicked (while run active):</b> 🛑 for 2 s, then ⚙️.</li>
</ul>

<h3>Cue Configuration Options</h3>
<ul>
  <li><b>Odd Trials Cue:</b> Dropdown (Right →, Left ←, Up ↑, Down ↓, Go 🟢). Default: Right →.</li>
  <li><b>Even Trials Cue:</b> Same dropdown. Default: Left ←.</li>
  <li><b>Order:</b>
    <ul>
      <li><b>Alternating:</b> Odd-indexed trials (1-based) show odd cue; even-indexed show even cue.</li>
      <li><b>Fixed:</b> Every trial shows the odd cue.</li>
      <li><b>Random:</b> Each trial selects a random cue from the map.</li>
    </ul>
  </li>
</ul>
        """
        dialog = self.create_custom_dialog("Timing & Cues Guide", text, 820, 660)
        dialog.exec_()

    def show_fft_psd_guide_dialog(self):
        text = """
<h2>FFT & PSD Explained</h2>

<h3>FFT (Fast Fourier Transform)</h3>
<p>For each EEG channel, we compute the <b>Discrete Fourier Transform (DFT)</b> to convert time-domain signals into the frequency domain. Mathematically:</p>
<pre>X[k] = Σ_{n=0}^{N-1} x[n] e^{-j 2π kn / N}</pre>
<p>where <code>x[n]</code> is the time-domain signal and <code>X[k]</code> is the complex frequency component at bin <code>k</code>.</p>
<ul>
  <li><b>Display:</b> We show the magnitude <code>|X[k]|</code> (amplitude) for each frequency bin.</li>
  <li><b>Nyquist Limit:</b> Maximum frequency is <b>Fs/2 = 62.5 Hz</b> (Fs = 125 Hz).</li>
  <li><b>Windowing/Scaling:</b> Applied internally to reduce spectral leakage and normalize amplitudes for visualization.</li>
</ul>

<h3>PSD (Power Spectral Density)</h3>
<p>PSD estimates <b>signal power distribution</b> across frequency bins, typically via Welch's method:</p>
<ol>
  <li>Segment the signal into overlapping windows.</li>
  <li>Compute FFT per window.</li>
  <li>Square magnitudes to get power.</li>
  <li>Average across windows.</li>
  <li>Normalize by bin width to yield power density.</li>
</ol>
<p>The UI displays power (in appropriate units) vs frequency for each channel.</p>

<h3>Frequency Bands (Typical EEG)</h3>
<ul>
  <li><b>Delta (0.5–4 Hz):</b> Deep sleep, unconscious processes.</li>
  <li><b>Theta (4–7 Hz):</b> Drowsiness, meditation, memory encoding.</li>
  <li><b>Alpha (8–13 Hz):</b> Relaxed wakefulness, eyes closed; strongest in occipital regions (visual cortex).</li>
  <li><b>Beta (13–30 Hz):</b> Active thinking, focused attention, motor cortex activity.</li>
  <li><b>Gamma (>30 Hz):</b> Higher cognitive tasks, sensory binding, consciousness.</li>
</ul>

<h3>Interpreting Peaks</h3>
<p>Prominent FFT/PSD peaks in specific bands correlate with brain states. For example, a strong alpha peak (8–13 Hz) during eyes-closed rest is expected. Motor imagery often modulates beta (13–30 Hz) over sensorimotor cortex.</p>
        """
        dialog = self.create_custom_dialog("FFT & PSD Explained", text, 840, 660)
        dialog.exec_()

    def show_data_shapes_dialog(self):
        text = """
<h2>Data Shapes & Structures</h2>

<h3>Raw µV (Microvolt Time Domain)</h3>
<p><b>Internal Cache (in-memory):</b></p>
<ul>
  <li>Stored as list of row vectors, each: <code>[ch1, ch2, ch3, ch4, ch5, ch6, ch7, ch8, global_s, trial_s]</code> (10 elements).</li>
  <li>Collected samples vstack to shape <b>(N_samples, 10)</b>, then transposed to <b>(10, N_samples)</b> for export prep.</li>
</ul>
<p><b>CSV Export:</b></p>
<ul>
  <li>Transposed again to <b>(N_samples, 10)</b> so each row is one sample timestamp.</li>
  <li><b>Header:</b> <code>ch1,ch2,ch3,ch4,ch5,ch6,ch7,ch8,global_s,trial_s</code></li>
  <li><b>Data Rows:</b> Each row = one 125 Hz sample; floating-point with 10 decimal places.</li>
  <li><b>Buffer Indication:</b> When <code>engine.phase == 'buffer'</code>, the <code>trial_s</code> cell is prefixed with <b>"B - "</b> (e.g., "B - -2.9920000000").</li>
  <li><b>Result:</b> Long-format CSV; many rows (one per sample), 10 columns. Compatible with spreadsheet tools like Excel that handle rows >> columns.</li>
</ul>

<h3>FFT (Frequency Amplitude Spectrum)</h3>
<p><b>Internal Cache:</b></p>
<ul>
  <li>Each sample tick: collect amplitude bins for all 8 channels, concatenate to form a row: <code>[trial_s, global_s, ch1_bin1..ch1_binN, ch2_bin1..ch2_binN, ..., ch8_bin1..ch8_binN]</code>.</li>
  <li>Shape: <b>(N_samples, 2 + 8 × num_freq_bins)</b>.</li>
</ul>
<p><b>CSV Export:</b></p>
<ul>
  <li><b>Header Line 1 (Frequency Hz):</b> <code># Frequencies (Hz),,[f1,f2,...,fN repeated 8 times]</code></li>
  <li><b>Header Line 2 (Bin Labels):</b> <code>trial_s,global_s,bin1,bin2,...,binN (repeated per channel)</code></li>
  <li><b>Header Line 3 (Channel Labels):</b> <code>,,ch1,ch1,...,ch1 (N bins),ch2,ch2,...,ch2,...,ch8,ch8,...,ch8</code></li>
  <li><b>Data Rows:</b> Each row = one timestamp; floating-point with 10 decimals.</li>
  <li><b>Result:</b> Wide CSV; many bins per channel. Rows = timestamps; columns = 2 + (8 × num_freq_bins).</li>
</ul>

<h3>PSD (Power Spectral Density)</h3>
<p><b>Structure:</b> Identical to FFT (same headers, same bin layout), but values represent power instead of amplitude.</p>
<ul>
  <li><b>Shape:</b> <b>(N_samples, 2 + 8 × num_freq_bins)</b>.</li>
  <li>Same frequency header, bin labels, channel labels as FFT.</li>
</ul>

<h3>Visual Summary</h3>
<pre>
µV:  N_samples × 10                 [rows = samples; cols = ch1..8, global_s, trial_s]
FFT: N_samples × (2 + 8×bins)       [rows = samples; cols = trial_s, global_s, bins for all channels]
PSD: N_samples × (2 + 8×bins)       [rows = samples; cols = trial_s, global_s, bins for all channels]
</pre>
        """
        dialog = self.create_custom_dialog("Data Shapes", text, 900, 720)
        dialog.exec_()
