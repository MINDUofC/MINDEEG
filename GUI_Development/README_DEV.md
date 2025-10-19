# MINDStream EEG - Developer Guide

## 📋 Table of Contents
- [Overview](#overview)
- [Application Architecture](#application-architecture)
- [PyQt5 Deep Dive](#pyqt5-deep-dive)
- [Project Structure](#project-structure)
- [Core Components](#core-components)
- [Lazy Loading Implementation](#lazy-loading-implementation)
- [Development Setup](#development-setup)
- [Building the Application](#building-the-application)
- [PyInstaller Hooks System](#pyinstaller-hooks-system)
- [DLL & Dependency Management](#dll--dependency-management)
- [Adding New Features](#adding-new-features)
- [Performance Optimization](#performance-optimization)
- [Troubleshooting](#troubleshooting)

---

## Overview

**MINDStream** is a comprehensive EEG signal processing and visualization platform built for real-time brain signal analysis. Developed by the MIND Design Team at the University of Calgary, it provides researchers and developers with powerful tools for:

- **Real-time EEG data acquisition** from BrainFlow-compatible devices
- **Advanced signal preprocessing** (bandpass/bandstop filtering, ICA, detrending)
- **Live visualization** (time-domain µV plots, FFT, PSD)
- **Precise timing and recording** for experiments
- **Data export** in multiple formats (CSV, NPY, MAT)
- **AI-powered chatbot** for biosignals assistance

The application is built with Python and PyQt5, utilizing BrainFlow for hardware interfacing and various scientific libraries for signal processing.

### Technology Stack

- **GUI Framework**: PyQt5 (Qt Designer for UI, dynamic loading with uic)
- **Hardware Interface**: BrainFlow (multi-board EEG support)
- **Signal Processing**: SciPy, NumPy, scikit-learn
- **Visualization**: VisPy (GPU-accelerated), PyQtGraph
- **AI/ML**: GPT4All (local LLM), RapidFuzz (fuzzy matching)
- **Build System**: PyInstaller with custom hooks

---

## Application Architecture

### High-Level Design

MINDStream follows a **Model-View-Controller (MVC)**-inspired architecture with clear separation between frontend, backend logic, and data handling:

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                            FRONTEND LAYER                                        │
│                                                                                  │
│  ┌────────────────┐    ┌──────────────────┐    ┌──────────────────┐              │
│  │   main.py      │◄───│ frontend_design  │    │  chatbotFE.py    │              │
│  │  (MainApp)     │    │  (fe module)     │    │  (ChatbotFE)     │              │
│  │                │    │ - minimize()     │    │  - chat widget   │              │
│  │ - Loads .ui    │    │ - fullscreen()   │    │  - AI responses  │              │
│  │ - Connects     │    │ - paintEvent()   │    └────────┬─────────┘              │
│  │   signals      │    │ - drag window    │             │                        │
│  │ - Manages      │    │ - validation     │    ┌────────▼─────────┐              │
│  │   state        │    └──────────────────┘    │  menu_handler.py │              │
│  └───────┬────────┘                             │  (MenuHandler)   │             │
│          │                                      │  - Help dialogs  │             │
│          │                                      │  - Dropdown menu │             │
│          │                                      └──────────────────┘             │
└──────────┼───────────────────────────────────────────────────────────────────────┘
           │
           ▼ (calls backend functions via signal/slot)
┌──────────────────────────────────────────────────────────────────────────────────┐
│                           BACKEND LOGIC LAYER                                    │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐         │
│  │                          Board Setup                                │         │
│  │  backend_eeg.py: turn_on_board(), turn_off_board()                  │         │
│  │  ↓ Creates BoardShim object, starts EEG streaming                   │         │
│  └──────────────────────────────┬──────────────────────────────────────┘         │
│                                  │                                               │
│  ┌───────────────────────────────▼─────────────────────────────────────┐         │
│  │                       Data Handling Pipeline                        │         │
│  │                                                                     │         │
│  │  ┌───────────────────┐  ┌────────────────────┐  ┌──────────────┐    │         │
│  │  │ data_collector.py │◄─│ data_processing.py │◄─│ ica_manager  │    │         │
│  │  │ (Centralized      │  │                    │  │    .py       │    │         │ 
│  │  │  DataCollector)   │  │ - get_filtered_    │  │              │    │         │
│  │  │                   │  │   data()           │  │ - FastICA    │    │         │
│  │  │ - collect_data_   │  │ - bandpass_        │  │ - artifact   │    │         │
│  │  │   muV()           │  │   filters()        │  │   removal    │    │         │
│  │  │ - collect_data_   │  │ - bandstop_        │  │              │    │         │
│  │  │   FFT()           │  │   filters()        │  │              │    │         │
│  │  │ - collect_data_   │  │ - detrend_signal() │  │              │    │         │
│  │  │   PSD()           │  │ - mean/median      │  │              │    │         │
│  │  │                   │  │   smoothing()      │  │              │    │         │
│  │  └─────────┬─────────┘  └────────────────────┘  └──────────────┘    │         │
│  │            │                                                        │         │
│  └────────────┼────────────────────────────────────────────────────────┘         │
│               │                                                                  │
│  ┌────────────▼────────────────────────────────────────────────────────┐         │
│  │                         Visualizer                                  │         │
│  │                                                                     │         │
│  │  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐        │         │
│  │  │ live_plot_muV   │ │ live_plot_FFT   │ │ live_plot_PSD   │        │         │
│  │  │     .py         │ │     .py         │ │     .py         │        │         │
│  │  │                 │ │                 │ │                 │        │         │ 
│  │  │ - VisPy/OpenGL  │ │ - FFT spectrum  │ │ - Welch PSD     │        │         │
│  │  │ - Stacked       │ │ - Frequency     │ │ - Power by      │        │         │
│  │  │   channels      │ │   analysis      │ │   frequency     │        │         │
│  │  │ - GPU accel.    │ │ - Brain wave    │ │ - Multi-channel │        │         │
│  │  │                 │ │   bands         │ │                 │        │         │
│  │  └─────────────────┘ └─────────────────┘ └─────────────────┘        │         │
│  └─────────────────────────────────────────────────────────────────────┘         │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐         │
│  │                    Timing & Recording                               │         │
│  │                                                                     │         │
│  │  ┌──────────────┐  ┌──────────────────┐  ┌──────────────────┐       │         │
│  │  │ timing_      │  │ recording_       │  │ export_manager   │       │         │
│  │  │ engine.py    │  │ manager.py       │  │     .py          │       │         │
│  │  │              │  │                  │  │                  │       │         │
│  │  │ - QTimer     │◄─│ - Precise        │◄─│ - Browse folder  │       │         │
│  │  │ - 8ms ticks  │  │   Recording      │  │ - Save CSV/      │       │         │
│  │  │ - Trials     │  │   Manager        │  │   NPY/MAT        │       │         │
│  │  │ - Buffer     │  │ - Start/stop     │  │                  │       │         │
│  │  │   phases     │  │ - Buffer data    │  │                  │       │         │
│  │  │              │  │                  │  │                  │       │         │
│  │  └──────────────┘  └──────┬───────────┘  └──────────────────┘       │         │
│  │                            │                                        │         │
│  │                   ┌────────▼──────────┐                             │         │
│  │                   │  TimerGUI.py      │                             │         │ 
│  │                   │  (TimelineWidget) │                             │         │
│  │                   │  - Visual timeline│                             │         │
│  │                   │  - Trial markers  │                             │         │ 
│  │                   └───────────────────┘                             │         │ 
│  └─────────────────────────────────────────────────────────────────────┘         │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐         │
│  │                         AI Chatbot                                  │         │
│  │  chatbotBE.py                                                       │         │
│  │  ├─ FAQ fuzzy matching (RapidFuzz) ──► Fast, local                  │         │
│  │  └─ LLM generation (GPT4All) ────────► Slow, fallback               │         │
│  │     - Lazy-loaded (4.66 GB model)                                   │         │
│  │     - Context management (1200 chars)                               │         │
│  └─────────────────────────────────────────────────────────────────────┘         │
└──────────────────────────────────┬───────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                           HARDWARE/DATA LAYER                                    │
│                                                                                  │
│  BrainFlow BoardShim ──► Serial Communication ──► Neuropawn EEG Device           │
│  (Board ID: 57)          (COM Port)              (1-8 channels @ 125/250 Hz)     │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Detailed File Interactions

#### Frontend Interactions

**1. main.py ↔ frontend_design.py (imported as `fe`)**
```python
# main.py imports frontend_design as fe module
import frontend.frontend_design as fe

# main.py calls fe functions for window management:
self.minimize_button.clicked.connect(lambda: fe.minimize_window(self))
self.close_button.clicked.connect(lambda: fe.close_window(self))
self.fullscreen_button.clicked.connect(lambda: fe.toggle_fullscreen(self, self.chatbot))

# main.py uses fe for dragging
self.taskbar.mousePressEvent = lambda event: fe.start_drag(self, event)
self.taskbar.mouseMoveEvent = lambda event: fe.move_window(self, event, self.chatbot)

# main.py uses fe for UI utilities
fe.toggle_settings_visibility(self)  # Show/hide filter settings
fe.set_integer_only(self.BoardID, 0, 57)  # Validate inputs
fe.paintEvent(self, event)  # Custom window border drawing
```

**2. main.py ↔ chatbotFE.py**
```python
# main.py creates chatbot widget
from frontend.chatbotFE import ChatbotFE
self.chatbot = ChatbotFE(self)  # Pass parent window

# Chatbot repositions when window moves/resizes
fe.move_window(self, event, self.chatbot)  # Updates chatbot position
self.chatbot.reposition()  # Chatbot adjusts its location
```

**3. main.py ↔ menu_handler.py**
```python
# main.py creates menu handler for dropdown
from frontend.menu_handler import MenuHandler
self.menu_handler = MenuHandler(self, self.MenuOptions)

# MenuOptions dropdown triggers dialogs:
# "How to Use" → shows comprehensive guide
# "FAQ" → shows common questions
# "About" → shows version info
```

#### Backend Interactions

**4. main.py → backend_eeg.py (Board Control)**
```python
# main.py lazy-loads when power button clicked
def toggle_board(self):
    if not self.isBoardOn:
        import backend_logic.board_setup.backend_eeg as beeg
        from brainflow.board_shim import BoardShim
        
        # Turn on board
        beeg.turn_on_board(
            board_id_input=self.BoardID,
            port_input=self.Port,
            channel_dial=self.ChannelDial,
            common_ref_checkbox=self.CommonRef,
            status_bar=self.StatusBar
        )
    else:
        beeg.turn_off_board(self.board_shim, self.StatusBar)
```

**5. backend_eeg.py → BoardShim → Hardware**
```python
# backend_eeg.py creates BrainFlow board object
from brainflow.board_shim import BoardShim, BrainFlowInputParams

params = BrainFlowInputParams()
params.serial_port = "COM3"  # From dropdown
params.timeout = 15

board_shim = BoardShim(board_id=57, params=params)  # Neuropawn
board_shim.prepare_session()  # Initialize hardware
board_shim.start_stream()  # Begin EEG streaming

# Configure channels via serial commands
board_shim.config_board("x1060110X")  # Enable channel 1
```

**6. BoardShim → CentralizedDataCollector**
```python
# data_collector.py polls data from board
from brainflow.board_shim import BoardShim

class CentralizedDataCollector:
    def __init__(self, board_shim, eeg_channels, preprocessing, ica_manager):
        self.board_shim = board_shim
        self.sampling_rate = BoardShim.get_sampling_rate(board_shim.get_board_id())
    
    def collect_data_muV(self):
        # Gets latest data from BrainFlow buffer
        return dp.get_filtered_data_with_ica(
            self.board_shim, 
            self.nump_muV,  # 4 seconds of data
            self.eeg_channels, 
            self.preprocessing,
            self.ica_manager
        )
```

**7. CentralizedDataCollector → data_processing.py**
```python
# data_collector calls processing functions
import backend_logic.data_handling.data_processing as dp

# In collect_data_muV():
data = dp.get_filtered_data_with_ica(board_shim, num_points, ...)

# data_processing.py applies filters:
def get_filtered_data_with_ica(board_shim, num_points, eeg_channels, preprocessing, ica_manager):
    # 1. Get raw data from board
    data = board_shim.get_current_board_data(num_points)
    
    # 2. Remove 50/60 Hz noise
    DataFilter.remove_environmental_noise(signal, ...)
    
    # 3. Detrend if enabled
    if preprocessing["DetrendOnOff"].isChecked():
        signal = detrend_signal(signal)
    
    # 4. Bandpass filter
    if preprocessing["BandPassOnOff"].isChecked():
        signal = bandpass_filters(signal, preprocessing, ...)
    
    # 5. Bandstop filter
    if preprocessing["BandStopOnOff"].isChecked():
        signal = bandstop_filters(signal, preprocessing, ...)
    
    # 6. Apply ICA if enabled
    if ica_manager and ica_manager.is_ica_enabled():
        data_array = ica_manager.apply_ica(data_array)
    
    return processed_data
```

**8. data_processing.py ↔ ica_manager.py**
```python
# data_processing calls ICA manager
if ica_manager and ica_manager.is_ica_enabled():
    data_array = ica_manager.apply_ica(data_array)

# ica_manager.py uses scikit-learn
from sklearn.decomposition import FastICA

class ICAManager:
    def fit_ica(self, calibration_data):
        """Train ICA on calibration data (e.g., 30 seconds)"""
        self.ica = FastICA(n_components=n_channels, max_iter=1000)
        self.ica.fit(calibration_data.T)
    
    def apply_ica(self, data):
        """Remove artifacts (eye blinks, muscle noise)"""
        sources = self.ica.transform(data.T)
        # User manually disables artifact components (e.g., component 0)
        sources[:, self.disabled_components] = 0
        return self.ica.inverse_transform(sources).T
```

**9. CentralizedDataCollector → Visualizers**
```python
# main.py connects data collector to graphs
self.data_collector = CentralizedDataCollector(
    self.board_shim, 
    self.eeg_channels, 
    self.preprocessing,
    self.ica_manager
)

# µV graph updates
def update_muV_graph(self):
    data = self.data_collector.collect_data_muV()  # Get processed data
    if data and self.muV_loaded:
        self.muV_graph.update_graph(data)  # Draw on screen

# FFT graph updates
def update_FFT_graph(self):
    data = self.data_collector.collect_data_FFT()  # Includes FFT computation
    if data and self.FFT_loaded:
        self.FFT_graph.update_graph(data)
```

**10. Visualizers Use VisPy/PyQtGraph**
```python
# live_plot_muV.py uses VisPy for GPU rendering
from vispy import scene
from vispy.scene import LinePlot

class MuVGraphVispyStacked(QWidget):
    def __init__(self, parent, data_processor):
        self.canvas = scene.SceneCanvas(parent=parent)
        self.view = self.canvas.central_widget.add_view()
        
        # Create line plot for each channel
        self.lines = []
        for ch in range(8):
            line = LinePlot(data=np.zeros((100, 2)), color=(0.2, 0.6, 1.0))
            self.view.add(line)
            self.lines.append(line)
    
    def update_graph(self, data_dict):
        """Update line positions with new EEG data"""
        for idx, ch in enumerate(self.eeg_channels):
            signal = data_dict[ch]
            # Offset channels vertically for stacked view
            y_offset = idx * self.spacing
            points = np.column_stack((x_axis, signal + y_offset))
            self.lines[idx].set_data(points)
        
        self.canvas.update()  # Redraw
```

**11. Timing & Recording Pipeline**
```python
# timing_engine.py emits signals at precise intervals
class TimingEngine(QObject):
    tick_8ms = pyqtSignal(int, int)  # Emits every 8ms (125 Hz)
    trial_started = pyqtSignal(int)
    run_completed = pyqtSignal()
    
    def __init__(self):
        self._timer = QTimer()
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(8)  # 8ms interval
    
    def _on_tick(self):
        # Update trial phase (before onset, trial, buffer)
        self.tick_8ms.emit(now_ms, scheduled_ms)

# main.py connects timing to recording
self.timing_engine = TimingEngine()
self.recording_manager = PreciseRecordingManager()

self.timing_engine.tick_8ms.connect(self.recording_manager.on_tick)
self.timing_engine.trial_started.connect(lambda: self.recording_manager.start_recording())

# recording_manager.py buffers data during recording
class PreciseRecordingManager:
    def on_tick(self, now_ms, sched_ms):
        if self.is_recording:
            # Get current data from board
            data = self.board_shim.get_current_board_data(num_samples)
            self.buffer.append((now_ms, data))  # Store with timestamp
    
    def stop_recording_and_export(self):
        # Save to file
        export_manager.save_data(self.buffer, filename, format='csv')
```

**12. ChatbotBE Two-Stage System**
```python
# chatbotBE.py has two response mechanisms
class ChatbotBE:
    def get_response(self, user_query):
        # Stage 1: Try FAQ fuzzy matching (fast)
        normalized_query = self._normalize_text(user_query)
        best_match = process.extractOne(
            normalized_query, 
            self.questions, 
            scorer=fuzz.WRatio
        )
        
        if best_match and best_match[1] >= 70:  # 70% similarity
            idx = self.questions.index(best_match[0])
            return self.faq_data[idx]['a']  # Return FAQ answer
        
        # Stage 2: Fall back to LLM (slower)
        self._ensure_model_loaded()  # Lazy load 4.66 GB model
        response = self.model.generate(
            prompt=self._build_prompt(user_query),
            max_tokens=192
        )
        return response

# chatbotFE.py provides UI
class ChatbotFE(QWidget):
    def __init__(self, parent):
        self.backend = ChatbotBE(load_model_immediately=False)
        self.chat_display = QTextEdit()  # Shows conversation
        self.input_box = QLineEdit()  # User types here
    
    def send_message(self):
        user_text = self.input_box.text()
        response = self.backend.get_response(user_text)  # Call backend
        self.chat_display.append(f"You: {user_text}")
        self.chat_display.append(f"AI: {response}")
```

### Data Flow Diagram

```
User Action (GUI)
       │
       ▼
┌──────────────────────────────────────┐
│  main.py (MainApp)                   │
│  - Handles user input                │
│  - Routes to appropriate backend     │
└──────────┬───────────────────────────┘
           │
           ├─────────────┐
           │             │
           ▼             ▼
    [Power Button]  [Record Button]
           │             │
           ▼             ▼
  backend_eeg.py   recording_manager.py
           │             │
           ▼             ▼
    BoardShim.start() timing_engine
           │          .start()
           │             │
           ▼             ▼
   ┌──────────────────────────────┐
   │  Hardware Streaming          │
   │  125/250 Hz EEG Data         │
   └──────────┬───────────────────┘
              │
              ▼
   ┌──────────────────────────────┐
   │  CentralizedDataCollector    │
   │  - Polls board buffer        │
   │  - Calls data_processing     │
   └──────────┬───────────────────┘
              │
              ▼
   ┌──────────────────────────────┐
   │  data_processing.py          │
   │  1. Remove 50/60 Hz noise    │
   │  2. Detrend                  │
   │  3. Bandpass filter          │
   │  4. Bandstop filter          │
   │  5. Smoothing                │
   └──────────┬───────────────────┘
              │
              ├───────────┬───────────┬───────────┐
              ▼           ▼           ▼           ▼
         [with ICA]  [Visualizer] [Recording] [Export]
              │           │           │           │
              ▼           │           │           │
      ica_manager.py      │           │           │
      - FastICA fit       │           │           │
      - Transform         │           │           │
      - Inverse           │           │           │
              │           │           │           │
              └─────┬─────┘           │           │
                    ▼                 ▼           ▼
            ┌───────────────┐  ┌──────────┐  ┌──────────┐
            │  Visualizers  │  │ Recording│  │  Export  │
            │  - muV plot   │  │  buffer  │  │ CSV/NPY/ │
            │  - FFT plot   │  │          │  │   MAT    │
            │  - PSD plot   │  │          │  │          │
            └───────────────┘  └──────────┘  └──────────┘
                    │                 │            │
                    └─────────────────┴────────────┘
                                      │
                                      ▼
                              User sees results
```

### Thread Model

- **Main Thread (Qt Event Loop)**: 
  - Handles all UI updates
  - Processes user clicks, typing, etc.
  - Calls backend functions via signals/slots
  - **Never blocks** (all heavy work done in background)

- **BrainFlow Internal Thread**:
  - Started by `board_shim.start_stream()`
  - Continuously receives data from hardware
  - Fills ring buffer (45 seconds capacity)
  - Independent of Python code

- **Data Collection (Implicit)**:
  - QTimer triggers every frame (30-60 FPS)
  - `collect_data_muV()` pulls from BrainFlow buffer
  - Processing happens synchronously but fast (<10ms)

- **Visualization Thread (VisPy)**:
  - OpenGL context on separate thread
  - GPU renders lines, colors, transforms
  - Synchronized with main thread via Qt signals

- **Chatbot Response (Async)**:
  - LLM generation runs in background (QThread or asyncio)
  - FAQ matching is synchronous (fast, <1ms)
  - UI remains responsive during generation

---

## PyQt5 Deep Dive

### Why PyQt5?

PyQt5 provides Python bindings for the Qt framework, offering:
- **Cross-platform compatibility** (Windows, macOS, Linux)
- **Native look and feel**
- **Rich widget library** (buttons, sliders, combo boxes, etc.)
- **Qt Designer** for visual UI design
- **Signals & Slots** for event-driven programming
- **Resource system** for embedded images/icons

### UI Loading: Dynamic vs Compiled

**We use dynamic loading** (`uic.loadUi()`) instead of compiling `.ui` to `.py`:

```python
# main.py line 60-61
ui_file = os.path.join(os.path.dirname(__file__), "GUI Design.ui")
uic.loadUi(ui_file, self)
```

**Advantages:**
- Faster iteration (edit `.ui` file, no recompilation needed)
- Smaller Python files
- Easier to maintain

**Disadvantages:**
- Slightly slower startup (~0.1s)
- Requires `.ui` file in distribution

**Alternative (compiled)**:
```bash
pyuic5 "GUI Design.ui" -o gui_design_compiled.py
```
Then import and use in `main.py`. We chose dynamic loading for development flexibility.

### Signals & Slots Pattern

Qt uses **signals and slots** for event handling:

```python
# Signal: User clicks button
self.minimize_button.clicked.connect(lambda: fe.minimize_window(self))
#                     ^^^^^^^ signal
#                              ^^^^^^^ slot (callback function)

# Signal: Value changes
self.NumBandPass.valueChanged.connect(lambda: fe.toggle_settings_visibility(self))
#                ^^^^^^^^^^^^ signal emitted when spinbox value changes
```

**Key Points:**
- **Signals** are events emitted by widgets
- **Slots** are functions that respond to signals
- `connect()` links them together
- Supports **lambda functions** for inline callbacks
- Automatically **thread-safe** when crossing thread boundaries

### Frameless Window Implementation

We use a **custom frameless window** with custom title bar:

```python
# main.py line 62-63
self.setWindowFlags(Qt.FramelessWindowHint)
self.setAttribute(Qt.WA_TranslucentBackground)
```

**Custom Features Implemented:**
1. **Dragging**: Capture mouse events on taskbar
2. **Resizing**: Edge detection with 8px margin (see `frontend_design.py`)
3. **Custom buttons**: Minimize, maximize/restore, close
4. **Window state persistence**: Remember fullscreen state after minimize

**Dragging Implementation** (`frontend_design.py` lines 46-102):
- `start_drag()`: Store initial cursor position
- `move_window()`: Calculate delta and move window
- `stop_drag()`: Clear drag state
- **Smart detection**: Don't drag if clicking interactive elements (buttons, dropdowns)

### Resource System (Qt Resources)

**Why use Qt resources?**
- Embeds images/icons into the application
- No need for external files (cleaner distribution)
- Fast loading (compiled into Python module)
- Cross-platform paths

**Workflow:**
1. Define resources in `resources.qrc`:
   ```xml
   <RCC>
       <qresource prefix="/images">
           <file>checkmark.png</file>
           <file>MIND LOGO Transparent.ico</file>
       </qresource>
   </RCC>
   ```

2. Compile to Python:
   ```bash
   pyrcc5 resources/resources.qrc -o resources_rc.py
   ```

3. Import in `main.py`:
   ```python
   import resources_rc  # Makes resources available
   ```

4. Use in code/stylesheets:
   ```python
   QIcon(":/images/checkmark.png")  # Note the :/ prefix
   ```

**IMPORTANT**: Always use `:/prefix/file` format in compiled resources, **not** relative paths like `resources/file.png`.

### Qt Designer Tips

- **Layout Management**: Use QHBoxLayout, QVBoxLayout, QGridLayout for responsive designs
- **Spacers**: Add stretchy spacers to push widgets to edges
- **Size Policies**: Set minimum/maximum sizes to control widget growth
- **Object Names**: Give meaningful names (they become Python variable names)
- **Style Sheets**: Use CSS-like syntax for custom styling
- **Tab Order**: Set logical tab order for keyboard navigation

---

## Project Structure

```
GUI_Development/
│
├── main.py                          # Application entry point
├── GUI Design.ui                    # Qt Designer UI file (XML)
├── resources_rc.py                  # Compiled Qt resources (auto-generated)
│
├── frontend/                        # Frontend components
│   ├── __init__.py
│   ├── frontend_design.py           # UI helper functions (drag, resize, paint)
│   ├── chatbotFE.py                 # Chat interface widget
│   └── menu_handler.py              # Dropdown menu & help dialogs
│
├── backend_logic/                   # Core backend modules
│   │
│   ├── board_setup/                 # Hardware interfacing
│   │   └── backend_eeg.py           # BrainFlow board initialization & control
│   │
│   ├── data_handling/               # Data pipeline
│   │   ├── data_collector.py        # Centralized data collection from board
│   │   ├── data_processing.py       # Signal processing (filters, detrend, etc.)
│   │   └── ica_manager.py           # Independent Component Analysis
│   │
│   ├── visualizer/                  # Real-time plots
│   │   ├── live_plot_muV.py         # Time-domain µV visualization (VisPy)
│   │   ├── live_plot_FFT.py         # Fast Fourier Transform plot
│   │   └── live_plot_PSD.py         # Power Spectral Density plot
│   │
│   ├── timing_and_recording/        # Experiment control
│   │   ├── timing_engine.py         # Precise timing system
│   │   ├── TimerGUI.py              # Timeline widget
│   │   ├── recording_manager.py     # Recording state & buffer management
│   │   ├── export_manager.py        # File export functionality
│   │   ├── export_destination.txt   # Saved export path
│   │   └── black_screen_timer.py    # Full-screen timer for experiments
│   │
│   └── chatbot/                     # AI assistant
│       ├── chatbotBE.py             # GPT4All integration (lazy-loaded)
│       ├── faq.json                 # FAQ database for fuzzy matching
│       └── SystemPrompt.txt         # Chatbot system instructions
│
├── resources/                       # Images, icons, UI assets
│   ├── resources.qrc                # Qt resource definition (XML)
│   ├── MIND LOGO Transparent.png    # Application logo (PNG)
│   ├── MIND LOGO Transparent.ico    # Application icon (ICO, multi-resolution)
│   ├── checkmark.png                # Checkbox indicator
│   ├── MINDStream SplashScreen.png  # Splash screen image
│   └── *.png, *.jpg                 # Other UI assets
│
└── build_management/                # Executable building
    ├── build_exe.py                 # PyInstaller build script (582 lines)
    ├── build_config.json            # Build configuration (393 lines)
    ├── MINDStream.spec              # PyInstaller spec file (auto-generated)
    ├── hooks/                       # Custom PyInstaller hooks
    │   ├── hook-brainflow.py        # BrainFlow DLL collection
    │   ├── hook-gpt4all.py          # GPT4All model & DLL handling
    │   ├── hook-PyQt5.py            # PyQt5 plugins & Qt libs
    │   ├── hook-vispy.py            # VisPy shader files (GLSL)
    │   ├── hook-scipy.py            # SciPy binary dependencies
    │   └── hook-rapidfuzz.py        # RapidFuzz C extensions
    ├── build/                       # Temporary build files
    └── dist/                        # Final executable output
        └── MINDStream/
            ├── MINDStream.exe       # Main executable
            └── _internal/           # All dependencies
```

---

## Core Components

### 1. **Main Application** (`main.py`)

The entry point that orchestrates the entire application.

**Initialization Flow:**
1. **Setup window** (line 52-74): Load UI, set frameless window, configure appearance
2. **Bind UI elements** (line 77-228): Connect all widgets to instance variables
3. **Initialize managers** (line 231-246): Create timing, recording, ICA managers
4. **Connect signals** (line 279-350): Wire up all button clicks, value changes, etc.
5. **Apply lazy loading** (line 24-34): Comment out heavy imports, load on-demand
6. **Show window** (line 1084): Display GUI and enter Qt event loop

**Key Patterns:**
- **`findChild()` for widget access**:
  ```python
  self.BandPassOnOff = self.findChild(QCheckBox, "BandPassOnOff")
  ```
  Gets widget by object name (set in Qt Designer)

- **Lambda for inline callbacks**:
  ```python
  self.close_button.clicked.connect(lambda: fe.close_window(self))
  ```
  Wraps function call without creating named function

- **State management**:
  ```python
  self.isBoardOn = False
  self.isRecording = False
  self.muV_loaded = False  # Track lazy-loaded modules
  ```

**Tab Switching Logic** (line 538-597):
```python
def on_visualizer_tab_changed(self, index):
    if index == 0:  # µV tab
        if not self.muV_loaded:
            # Lazy load heavy VisPy module (saves ~3s startup)
            from backend_logic.visualizer.live_plot_muV import MuVGraphVispyStacked as MuVGraph
            self.muV_graph = MuVGraph(self.muVPlot, self.data_processor)
            self.muV_loaded = True
```

### 2. **Board Setup** (`backend_logic/board_setup/backend_eeg.py`)

Handles all hardware interfacing via BrainFlow API.

**Key Functions:**

**`get_available_ports()`** (line 12-15):
```python
def get_available_ports():
    """Returns a list of available serial ports."""
    ports = list(device_ports.comports())
    return [port.device for port in ports]
```
Uses `serial.tools.list_ports` to detect COM ports.

**`turn_on_board()`** (line 30-140):
1. **Validate inputs**: Check Board ID, port, channel count
2. **Setup BrainFlow parameters**:
   ```python
   params = BrainFlowInputParams()
   params.serial_port = port
   params.timeout = 15
   ```
3. **Initialize board**:
   ```python
   board_shim = BoardShim(board_id, params)
   board_shim.prepare_session()
   board_shim.start_stream()
   ```
4. **Configure channels**: Send serial commands to hardware
5. **Enable common reference (RLD)** if checked
6. **Update UI**: Change status bar, button colors

**Hardware Communication**:
- Uses BrainFlow's `BoardShim.write()` to send commands to Neuropawn
- Commands like `!` (stop streaming), `b` (start streaming), `x1060100X` (channel config)
- **Important**: Different boards have different command protocols

### 3. **Data Collection** (`backend_logic/data_handling/data_collector.py`)

**`CentralizedDataCollector` Class**:
- **Singleton pattern**: One instance for entire app
- **Threaded polling**: Continuously pulls data from BrainFlow buffer
- **Thread-safe access**: Uses locks for concurrent reads

**Key Methods:**
```python
def get_latest_data(self, num_samples):
    """Get most recent N samples from buffer"""
    with self.lock:
        return self.data_buffer[:, -num_samples:]

def start_collection(self, board_shim, sampling_rate):
    """Start background thread to poll board"""
    self.thread = threading.Thread(target=self._collect_loop)
    self.thread.start()
```

**Why threading?**
- BrainFlow buffer is limited (~45 seconds at 250 Hz)
- Must continuously pull data to avoid overflow
- Separate thread prevents UI blocking

### 4. **Data Processing** (`backend_logic/data_handling/data_processing.py`)

**Signal Processing Pipeline**:

1. **Bandpass Filtering** (FIR or IIR):
   ```python
   from scipy.signal import butter, filtfilt, firwin, lfilter
   
   # IIR Butterworth
   b, a = butter(order, [low_cut, high_cut], btype='band', fs=sampling_rate)
   filtered = filtfilt(b, a, data, axis=1)  # Zero-phase filtering
   
   # FIR window method
   taps = firwin(numtaps, [low_cut, high_cut], window='hamming', fs=sampling_rate, pass_zero=False)
   filtered = lfilter(taps, 1.0, data, axis=1)
   ```

2. **Detrending**: Remove DC offset and linear trends
   ```python
   from scipy.signal import detrend
   detrended = detrend(data, axis=1, type='linear')
   ```

3. **ICA (Independent Component Analysis)**:
   ```python
   from sklearn.decomposition import FastICA
   ica = FastICA(n_components=n_channels, max_iter=1000, random_state=42)
   sources = ica.fit_transform(data.T).T  # Unmix signals
   reconstructed = ica.inverse_transform(sources.T).T  # Reconstruct with artifacts removed
   ```

4. **Averaging/Smoothing**: Reduce noise in visualization
   ```python
   from scipy.ndimage import uniform_filter1d
   smoothed = uniform_filter1d(data, size=window_size, axis=1)
   ```

**Why `axis=1`?**
- Data shape: `(n_channels, n_samples)`
- Process along time axis (samples)
- Keep channels separate

### 5. **Visualization** (`backend_logic/visualizer/`)

**VisPy for GPU Acceleration**:
- Uses OpenGL for real-time rendering
- Can handle 8 channels @ 250 Hz smoothly
- Custom shaders for line rendering

**µV Plot** (`live_plot_muV.py`):
- Stacked channel view (offset by spacing)
- Scrolling time window
- Auto-scaling based on data range
- Color-coded channels

**FFT Plot** (`live_plot_FFT.py`):
- Frequency spectrum (0-125 Hz typical)
- Logarithmic or linear scale
- Highlights brain wave bands (delta, theta, alpha, beta, gamma)

**PSD Plot** (`live_plot_PSD.py`):
- Power spectral density using Welch's method
- Shows power distribution across frequencies
- Useful for band power analysis

**Performance Tips:**
- Downsample if needed: `data[:, ::2]` (every 2nd sample)
- Limit update rate: Max 30-60 FPS
- Use smaller time windows: 5-10 seconds instead of 30+

### 6. **Recording Manager** (`backend_logic/timing_and_recording/`)

**`PreciseRecordingManager`**:
- Handles start/stop recording state
- Buffers data during recording
- Timestamps every sample
- Exports in multiple formats

**`TimingEngine`**:
- Millisecond-accurate timing
- Supports multi-trial experiments
- Event markers for analysis

**Export Formats**:
- **CSV**: Human-readable, Excel-compatible
- **NPY**: Fast NumPy binary format
- **MAT**: MATLAB-compatible (using `scipy.io.savemat`)

### 7. **Chatbot** (`backend_logic/chatbot/chatbotBE.py`)

**Two-Stage Response System**:

1. **FAQ Fuzzy Matching** (fast, local):
   ```python
   from rapidfuzz import process, fuzz
   best_match = process.extractOne(query, self.questions, scorer=fuzz.WRatio)
   if best_match[1] >= 70:  # 70% similarity threshold
       return faq_answer
   ```

2. **LLM Generation** (slower, fallback):
   ```python
   from gpt4all import GPT4All
   model = GPT4All("Meta-Llama-3-8B-Instruct.Q4_0.gguf")
   response = model.generate(prompt, max_tokens=192)
   ```

**Lazy Loading**:
- LLM model (4.66 GB) only loaded when first LLM query made
- FAQ matching works immediately
- Saves ~5 seconds startup time

**Context Management**:
- Keeps last 1200 chars of conversation
- Prevents token limit overflow
- Maintains coherent multi-turn dialogue

### 8. **Frontend Design** (`frontend/`)

**Frameless Window Features**:

**Custom Paint Event** (`frontend_design.py` line 106-124):
```python
def paintEvent(self, event):
    painter = QPainter(self)
    painter.setRenderHint(QPainter.Antialiasing)
    
    # Gradient background
    gradient = QLinearGradient(QPointF(0, 1), QPointF(1, 0))
    gradient.setColorAt(0.00, QColor("#FFFFFF"))
    gradient.setColorAt(0.25, QColor("#85C7F2"))
    gradient.setColorAt(0.50, QColor("#5C8FFF"))
    # ... creates blue gradient border
```

**Resize Detection** (`main.py` line 969-1050):
- Detects cursor near edges (8px margin)
- Changes cursor icon: `Qt.SizeHorCursor`, `Qt.SizeVerCursor`, `Qt.SizeFDiagCursor`
- Tracks resize direction (N, S, E, W, NE, NW, SE, SW)
- Updates geometry on mouse move

**Menu Handler** (`menu_handler.py`):
- Creates scrollable help dialogs
- Rich text formatting with HTML
- Custom stylesheets for consistent look
- Dropdown menu integration

---

## Lazy Loading Implementation

**Problem**: Heavy modules (BrainFlow, VisPy, GPT4All) slow startup (~10-15 seconds).

**Solution**: Only import when actually needed.

### Example: Visualization Modules

**Before (slow startup)**:
```python
from backend_logic.visualizer.live_plot_muV import MuVGraphVispyStacked as MuVGraph
from backend_logic.visualizer.live_plot_FFT import FFTGraph
from backend_logic.visualizer.live_plot_PSD import PSDGraph
```
**Loads immediately** even if user never uses plots.

**After (fast startup)**:
```python
# Comment out imports at top
# from backend_logic.visualizer.live_plot_muV import MuVGraphVispyStacked as MuVGraph

# Import when tab clicked
def on_visualizer_tab_changed(self, index):
    if index == 0 and not self.muV_loaded:
        from backend_logic.visualizer.live_plot_muV import MuVGraphVispyStacked as MuVGraph
        self.muV_graph = MuVGraph(self.muVPlot, self.data_processor)
        self.muV_loaded = True
```
**Loads only when µV tab opened**.

### Example: Board Modules

```python
# main.py line 30-34 (commented out at startup)
# import backend_logic.board_setup.backend_eeg as beeg
# from brainflow.board_shim import BoardShim

# main.py line 318-322 (imported when power button clicked)
def toggle_board(self):
    if not self.isBoardOn:
        import backend_logic.board_setup.backend_eeg as beeg
        from brainflow.board_shim import BoardShim
        # ... now can use beeg.turn_on_board()
```

### Example: Chatbot LLM

```python
# chatbotBE.py line 22-24
self.model = None
self._model_loaded = False

# chatbotBE.py line 130-136 (loaded on first LLM query)
def _ensure_model_loaded(self):
    if not self._model_loaded:
        self.model = GPT4All(self.model_name)
        self._model_loaded = True
```

**Result**: Startup time reduced from ~15s to ~2s.

---

## Development Setup

### Prerequisites

- **Python 3.10+** (tested on 3.13)
- **pip** package manager
- **Git** (for version control)
- **Qt Designer** (optional, for UI editing)

### 1. Clone the Repository

```bash
git clone <repository-url>
cd MINDEEG/GUI_Development
```

### 2. Install Dependencies

Create a virtual environment (recommended):

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

Install required packages:

```bash
pip install PyQt5 pyqtgraph vispy numpy scipy brainflow gpt4all rapidfuzz scikit-learn Pillow pyinstaller pyserial
```

**Key Dependencies:**
- `PyQt5` (5.15.x): GUI framework
- `brainflow` (5.x): EEG hardware interface
- `vispy` (0.14.x): GPU-accelerated visualization
- `scipy` (1.11.x): Signal processing
- `numpy` (1.26.x): Array operations
- `gpt4all` (2.x): Local LLM for chatbot
- `rapidfuzz` (3.x): Fuzzy string matching
- `scikit-learn` (1.3.x): ICA implementation
- `pyinstaller` (6.x): Executable builder
- `pyserial` (3.5): Serial port communication

### 3. Compile Qt Resources

Whenever you modify `resources.qrc`, recompile:

```bash
cd GUI_Development
pyrcc5 resources/resources.qrc -o resources_rc.py
```

This creates `resources_rc.py` with embedded image data.

### 4. Edit UI (Optional)

Open Qt Designer:
```bash
designer  # On Windows: designer.exe (install Qt separately)
# Or use PyQt5 designer:
python -m PyQt5.uic.pyuic --help  # Check if available
```

Edit `GUI Design.ui` visually, save, then run app (no compilation needed due to dynamic loading).

### 5. Run the Application

```bash
python main.py
```

**First Run**:
- GPT4All will download Llama-3 model (~4.66 GB) to cache
- May take 5-10 minutes on first launch
- Subsequent runs use cached model

---

## Building the Application

### PyInstaller Overview

**What PyInstaller Does**:
1. **Analyzes** Python scripts to find all imports
2. **Collects** Python modules, DLLs, data files
3. **Bundles** everything into a single folder (or file)
4. **Creates** executable that unpacks and runs

**Challenge**: PyInstaller's auto-detection misses:
- Dynamic imports (lazy loading)
- Binary dependencies (DLLs)
- Data files (shaders, config files)
- C extensions in some packages

**Our Solution**: Custom hooks + explicit configuration.

### Build Script Architecture

`build_exe.py` is a 582-line wrapper around PyInstaller that:
1. Loads configuration from `build_config.json`
2. Auto-detects package locations
3. Generates custom hooks
4. Creates `.spec` file
5. Runs PyInstaller with proper options
6. Handles errors gracefully

### Using the Build Script

**Basic Build**:
```bash
cd GUI_Development/build_management
python build_exe.py
```

**Build Options**:
```bash
python build_exe.py --debug          # Build with console for debugging
python build_exe.py --clean          # Clean build (remove old files)
python build_exe.py --onefile        # Single .exe (slower startup, not recommended)
python build_exe.py --add-module scipy.special  # Add missing hidden import
python build_exe.py --analyze        # Just analyze dependencies, don't build
```

**Build Process**:
1. ✅ Load configuration
2. ✅ Validate paths
3. ✅ Generate custom hooks
4. ✅ Create `.spec` file
5. ✅ Run PyInstaller
6. ✅ Copy to `dist/MINDStream/`

**Output Structure**:
```
dist/MINDStream/
├── MINDStream.exe              # Main executable (~15 MB)
├── _internal/                  # All dependencies (~2 GB)
│   ├── Python313.dll           # Python runtime
│   ├── Qt5Core.dll             # Qt libraries
│   ├── Qt5Gui.dll
│   ├── Qt5Widgets.dll
│   ├── numpy/                  # NumPy package
│   ├── scipy/                  # SciPy package
│   ├── brainflow/              # BrainFlow with DLLs
│   ├── gpt4all/                # GPT4All with model
│   ├── vispy/                  # VisPy with shaders
│   ├── resources/              # Images, icons
│   ├── GUI Design.ui           # UI file
│   └── ... (thousands of files)
└── README.md                   # User guide
```

### Configuration (`build_config.json`)

**Structure**:
```json
{
  "app_name": "MINDStream",
  "main_script": "../main.py",
  "icon": "../resources/MIND LOGO Transparent.ico",
  "splash_image": "../resources/MINDStream SplashScreen.png",
  "hidden_imports": [...],      // Modules PyInstaller misses
  "data_files": [...],           // Non-Python files to include
  "binary_files": [...],         // DLLs and shared libraries
  "dll_directories": [],         // Additional DLL search paths
  "exclude_modules": [...],      // Modules to explicitly exclude
  "upx_exclude": [...],          // DLLs not to compress with UPX
  "package_specific_settings": {...},
  "pyinstaller_options": {...}
}
```

**Hidden Imports** (line 7-60):
Modules that PyInstaller can't detect automatically:
```json
"hidden_imports": [
  "PyQt5",
  "PyQt5.QtCore",
  "PyQt5.QtGui",
  "PyQt5.QtWidgets",
  "brainflow.board_shim",
  "brainflow.data_filter",
  "gpt4all",
  "scipy.signal",
  "scipy.special._ufuncs",        // Missed due to lazy import
  "vispy.scene",
  "rapidfuzz.fuzz",
  // ... many more
]
```

**Data Files** (line 61-90):
Non-Python files that must be included:
```json
"data_files": [
  {"source": "../GUI Design.ui", "destination": "."},
  {"source": "../resources", "destination": "resources"},
  {"source": "../backend_logic/chatbot/faq.json", "destination": "backend_logic/chatbot"},
  {"source": "<python>/vispy/glsl/*", "destination": "vispy/glsl"}  // GLSL shaders
]
```

**Binary Files** (line 91-340):
DLLs and shared libraries:
```json
"binary_files": [
  {"source": "<python>/gpt4all/llmodel.dll", "destination": "gpt4all"},
  {"source": "<python>/brainflow/lib/BoardController.dll", "destination": "brainflow"},
  {"source": "<python>/brainflow/lib/DataHandler.dll", "destination": "brainflow"},
  // ... 50+ DLLs for BrainFlow, GPT4All, etc.
]
```

**Exclude Modules** (line 342-351):
Large packages we don't use (saves 500+ MB):
```json
"exclude_modules": [
  "matplotlib",   // Plotting library (we use VisPy/PyQtGraph)
  "tkinter",      // Alternative GUI framework
  "pandas",       // Data analysis (overkill for our use)
  "pytest",       // Testing framework
  "jupyter"       // Notebook environment
]
```

**PyInstaller Options** (line 383-392):
```json
"pyinstaller_options": {
  "onefile": false,       // Create folder (faster startup)
  "console": false,       // No console window (GUI only)
  "clean": true,          // Clean build each time
  "windowed": true,       // GUI application
  "strip": false,         // Don't strip symbols (easier debugging)
  "upx": false,           // Don't compress with UPX (faster, larger)
  "debug": false          // No debug output
}
```

---

## PyInstaller Hooks System

### What Are Hooks?

**Hooks** are Python scripts that tell PyInstaller how to properly package specific libraries. They run during the analysis phase.

**Hook Functions**:
- `collect_all(package)`: Collect everything from a package
- `collect_dynamic_libs(package)`: Collect only DLLs
- `collect_data_files(package)`: Collect non-Python files
- `collect_submodules(package)`: Find all submodules

### Why We Need Custom Hooks

Many packages have issues with PyInstaller:
- **BrainFlow**: DLLs in `lib/` subfolder (not standard)
- **GPT4All**: Needs specific DLL patterns, model files
- **VisPy**: GLSL shader files not collected
- **SciPy**: Complex binary dependencies
- **PyQt5**: Plugins and Qt libraries

### Our Custom Hooks

Located in `build_management/hooks/`:

#### 1. `hook-brainflow.py`

**Problem**: BrainFlow has 30+ DLLs in `lib/` subfolder that PyInstaller misses.

**Solution**:
```python
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs, collect_data_files

# Collect everything (Python files, DLLs, data)
datas, binaries, hiddenimports = collect_all('brainflow')

# Explicitly collect DLLs (redundant but safe)
binaries += collect_dynamic_libs('brainflow')

# Hidden imports that PyInstaller misses
hiddenimports += [
    'brainflow.board_shim',
    'brainflow.data_filter',
    'brainflow.ml_model',
    'brainflow.exit_codes'
]
```

**Why Both `collect_all()` and `collect_dynamic_libs()`?**
- `collect_all()` should get everything, but sometimes misses edge cases
- Explicitly calling `collect_dynamic_libs()` ensures DLLs are found
- Better to be redundant than miss a critical DLL

**What Gets Collected**:
- `BoardController.dll` - Main board interface
- `DataHandler.dll` - Signal processing utilities
- `BrainFlowBluetooth.dll` - Bluetooth support
- `GanglionLib.dll`, `MuseLib.dll`, `BrainBitLib.dll` - Specific board drivers
- 30+ more DLLs for different boards and platforms

#### 2. `hook-gpt4all.py`

**Problem**: GPT4All uses custom DLL loading, model files in specific locations.

**Solution**:
```python
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs, collect_data_files

datas, binaries, hiddenimports = collect_all('gpt4all')

# Collect DLLs from llmodel_DO_NOT_MODIFY/build/
binaries += collect_dynamic_libs('gpt4all')

# Additional data files (model metadata, configs)
datas += collect_data_files('gpt4all', include_py_files=False)

hiddenimports += [
    'gpt4all._pyllmodel',          // C++ bindings
    'gpt4all.pyllmodel'            // Alternative import path
]
```

**Critical DLLs**:
- `llmodel.dll` - Core LLM runtime
- `llamamodel-mainline-cuda.dll` - CUDA acceleration (if available)
- `llamamodel-mainline-kompute.dll` - Vulkan acceleration
- `fmt.dll` - Formatting library dependency

**Model Handling**:
- Models (~4.66 GB) stored in user cache: `~/.cache/gpt4all/`
- **Not included in build** (too large)
- Downloaded on first run
- Hook only includes runtime, not model files

#### 3. `hook-vispy.py`

**Problem**: VisPy uses GLSL shader files (`.vert`, `.frag`) not detected by PyInstaller.

**Solution**:
```python
from PyInstaller.utils.hooks import collect_all, collect_data_files

datas, binaries, hiddenimports = collect_all('vispy')

# Explicitly collect shader files
datas += collect_data_files('vispy', include_py_files=False)

# Include all VisPy submodules
hiddenimports += [
    'vispy.scene',
    'vispy.color',
    'vispy.app',
    'vispy.gloo',              // OpenGL Object Oriented interface
    'vispy.visuals',
    'vispy.util.fonts'
]
```

**Shader Collection**:
The build script also explicitly adds shader directories in `build_config.json`:
```json
{
  "source": "C:/.../vispy/glsl/*",
  "destination": "vispy/glsl"
},
{
  "source": "C:/.../vispy/visuals/glsl/*",
  "destination": "vispy/visuals/glsl"
}
```

**Why Shaders Matter**:
- VisPy renders using OpenGL
- Shaders define how graphics are drawn
- Missing shaders = blank/broken visualizations

#### 4. `hook-PyQt5.py`

**Problem**: PyQt5 has plugins (image formats, platforms) in non-standard locations.

**Solution**:
```python
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs

datas, binaries, hiddenimports = collect_all('PyQt5')

# Collect Qt plugins (image formats, platforms, styles)
binaries += collect_dynamic_libs('PyQt5')

hiddenimports += [
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
    'PyQt5.uic',               // UI loader
    'PyQt5.QtPrintSupport'
]
```

**Qt Plugins Collected**:
- `platforms/qwindows.dll` - Windows platform integration
- `imageformats/qjpeg.dll`, `qpng.dll`, `qico.dll` - Image loading
- `styles/qwindowsvistastyle.dll` - Native Windows styling

#### 5. `hook-scipy.py`

**Problem**: SciPy has complex binary dependencies, Fortran libraries.

**Solution**:
```python
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas, binaries, hiddenimports = collect_all('scipy')

# Collect all SciPy submodules (many not auto-detected)
hiddenimports += collect_submodules('scipy')

# Explicitly list critical submodules
hiddenimports += [
    'scipy.signal',
    'scipy.special',
    'scipy.special._ufuncs',      // C extensions
    'scipy.special._ufuncs_cxx',
    'scipy.linalg',
    'scipy.linalg.cython_blas',   // Fortran/C libraries
    'scipy.linalg.cython_lapack',
    'scipy._lib.messagestream'
]
```

**Why So Many Hidden Imports?**
- SciPy uses Cython (compiled Python)
- Imports are hidden in compiled code
- Must explicitly tell PyInstaller

#### 6. `hook-rapidfuzz.py`

**Problem**: RapidFuzz has C++ extensions not detected.

**Solution**:
```python
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs

datas, binaries, hiddenimports = collect_all('rapidfuzz')

binaries += collect_dynamic_libs('rapidfuzz')

hiddenimports += [
    'rapidfuzz.fuzz',
    'rapidfuzz.process',
    'rapidfuzz.distance',
    'rapidfuzz.utils'
]
```

### How Hooks Are Used

**Automatic Hook Discovery**:
PyInstaller looks for hooks in:
1. Built-in hooks (shipped with PyInstaller)
2. `--additional-hooks-dir` (our custom hooks)

**In `build_exe.py`** (line 255):
```python
f.write(f"    additional_hooks_dir=[r'{hooks_dir}'],\n")
```

**Execution Order**:
1. PyInstaller analyzes `main.py`
2. Finds import `brainflow`
3. Looks for `hook-brainflow.py`
4. Executes hook
5. Collects specified files
6. Repeats for all imports

---

## DLL & Dependency Management

### Why DLLs Are Problematic

**The Challenge**:
- Python packages often include compiled binaries (DLLs on Windows)
- PyInstaller uses `ctypes`, `cffi`, or import analysis to find DLLs
- **But**: Many packages use **custom loading mechanisms** that hide DLLs

**Common Issues**:
1. **Non-standard locations**: DLLs in `lib/`, `bin/`, `data/` instead of package root
2. **Dynamic loading**: `ctypes.CDLL()` loads DLL by path at runtime (not detected)
3. **Dependency chains**: DLL A needs DLL B, B needs C, but only A is collected
4. **Platform-specific**: Different DLLs for Windows/Linux/Mac (PyInstaller on Windows doesn't see Linux .so files)

### Our Explicit Inclusion Strategy

**Rather than rely on auto-detection, we explicitly list every critical DLL.**

**In `build_config.json`** (line 91-340):
```json
"binary_files": [
  // BrainFlow (30+ DLLs)
  {
    "source": "C:/Python313/Lib/site-packages/brainflow/lib/BoardController.dll",
    "destination": "brainflow"
  },
  {
    "source": "C:/Python313/Lib/site-packages/brainflow/lib/DataHandler.dll",
    "destination": "brainflow"
  },
  // ... repeat for all BrainFlow DLLs
  
  // GPT4All (5+ DLLs)
  {
    "source": "C:/Python313/Lib/site-packages/gpt4all/llmodel_DO_NOT_MODIFY/build/llmodel.dll",
    "destination": "gpt4all"
  },
  // ... repeat for all GPT4All DLLs
]
```

**Why Absolute Paths?**
- Build script running from `build_management/` directory
- Relative paths would be ambiguous
- Build script converts to proper format for `.spec` file

### DLL Discovery Process

**Manual Method** (when adding new package):
1. Install package: `pip install newpackage`
2. Find install location:
   ```python
   import newpackage
   print(newpackage.__file__)  # Shows path
   ```
3. Navigate to package folder
4. Search for DLLs: `*.dll`, `*.so`, `*.dylib`
5. Test: Build without DLLs, run exe, note missing DLL errors
6. Add missing DLLs to `binary_files`

**Automated Method** (used by `build_exe.py`):
```python
def auto_detect_gpt4all_dlls(self):
    """Automatically detect and add gpt4all DLLs"""
    gpt4all_path = self.find_package_location("gpt4all")
    if not gpt4all_path:
        return
    
    dll_dir = gpt4all_path / "llmodel_DO_NOT_MODIFY" / "build"
    for dll_file in dll_dir.glob("*.dll"):
        self.add_binary_file(str(dll_file), "gpt4all")
```

### Dependency Chains

**Example**: BrainFlow → Bluetooth → SimpleBLE → System Bluetooth

**Problem**: If you include `BrainFlowBluetooth.dll` but not `simpleble-c.dll`, it crashes.

**Solution**: Include entire dependency chain:
```json
{
  "source": ".../BrainFlowBluetooth.dll",
  "destination": "brainflow"
},
{
  "source": ".../simpleble-c.dll",
  "destination": "brainflow"
}
```

**How to Find Dependencies**:
- Use **Dependency Walker** (Windows): http://www.dependencywalker.com/
- Load DLL, see what it requires
- Recursively add all dependencies

### UPX Compression

**UPX** (Ultimate Packer for eXecutables) compresses DLLs to reduce size.

**Problem**: Some DLLs break when compressed (especially Qt, Python runtime).

**Solution**: Exclude problematic DLLs from UPX in `build_config.json`:
```json
"upx_exclude": [
  "vcruntime140.dll",    // Visual C++ runtime (breaks if compressed)
  "msvcp140.dll",
  "python*.dll",          // Python runtime
  "Qt5Core.dll",          // Qt libraries (large, slow to decompress)
  "Qt5Gui.dll",
  "Qt5Widgets.dll"
]
```

**Trade-off**:
- **With UPX**: Smaller exe (~30% reduction), slower startup (~2x)
- **Without UPX**: Larger exe, faster startup
- **We chose**: No UPX (better user experience)

### Testing DLL Inclusion

**After building**:
1. Copy `dist/MINDStream/` to different computer (without Python)
2. Run `MINDStream.exe`
3. Test all features:
   - Board connection (BrainFlow DLLs)
   - Visualizations (VisPy, OpenGL)
   - Chatbot (GPT4All DLLs)
   - Export (SciPy DLLs)
4. Check Windows Event Viewer for DLL load errors
5. Add missing DLLs to `build_config.json`

---

## Adding New Features

### Adding a New Visualization

**1. Create visualization file**: `backend_logic/visualizer/live_plot_spectrogram.py`

```python
from PyQt5.QtWidgets import QWidget
import pyqtgraph as pg
import numpy as np

class SpectrogramGraph(QWidget):
    def __init__(self, parent, data_processor):
        super().__init__(parent)
        self.data_processor = data_processor
        
        # Create PyQtGraph widget
        self.plot_widget = pg.PlotWidget(parent=self)
        self.image_item = pg.ImageItem()
        self.plot_widget.addItem(self.image_item)
        
        # Setup
        layout = QVBoxLayout(self)
        layout.addWidget(self.plot_widget)
        
    def update_plot(self, data):
        """Called every frame to update spectrogram"""
        # Compute spectrogram
        f, t, Sxx = scipy.signal.spectrogram(data, fs=250)
        self.image_item.setImage(np.log10(Sxx), autoLevels=True)
```

**2. Add tab in Qt Designer**:
- Open `GUI Design.ui`
- Add new tab to `Visualizer` QTabWidget
- Name it `SpectrogramPlot`
- Add widget placeholder (will be replaced in code)

**3. Add lazy loading in `main.py`**:
```python
# Top of file (line 28)
# from backend_logic.visualizer.live_plot_spectrogram import SpectrogramGraph

# In __init__ (line 220)
self.SpectrogramPlot = self.findChild(QWidget, "SpectrogramPlot")
self.spectrogram_loaded = False

# In on_visualizer_tab_changed (line 585)
elif index == 3:  # Spectrogram tab
    if not self.spectrogram_loaded:
        from backend_logic.visualizer.live_plot_spectrogram import SpectrogramGraph
        self.spectrogram_graph = SpectrogramGraph(self.SpectrogramPlot, self.data_processor)
        self.spectrogram_loaded = True
        self.active_graphs.append(self.spectrogram_graph)
```

**4. Update build config** (if new dependencies):
```json
"hidden_imports": [
  "scipy.signal.spectrogram"  // Add if PyInstaller misses it
]
```

### Adding a New Signal Processing Method

**1. Add function to `data_processing.py`**:
```python
def apply_wavelet_denoising(data, wavelet='db4', level=5, sampling_rate=250):
    """
    Apply wavelet denoising to EEG data.
    
    Args:
        data: ndarray of shape (n_channels, n_samples)
        wavelet: Wavelet type ('db4', 'sym4', 'coif4')
        level: Decomposition level
        sampling_rate: Sampling rate in Hz
    
    Returns:
        Denoised data
    """
    import pywt
    
    denoised_data = np.zeros_like(data)
    for ch in range(data.shape[0]):
        # Decompose signal
        coeffs = pywt.wavedec(data[ch], wavelet, level=level)
        
        # Threshold detail coefficients
        threshold = np.std(coeffs[-1]) * np.sqrt(2 * np.log(len(data[ch])))
        coeffs[1:] = [pywt.threshold(c, threshold, mode='soft') for c in coeffs[1:]]
        
        # Reconstruct signal
        denoised_data[ch] = pywt.waverec(coeffs, wavelet)
    
    return denoised_data
```

**2. Add UI controls in Qt Designer**:
- Add `QCheckBox` named `WaveletDenoiseOnOff`
- Add `QComboBox` named `WaveletType` with options: db4, sym4, coif4
- Add `QSpinBox` named `WaveletLevel` (range 1-10)

**3. Connect in `main.py`**:
```python
# In __init__ (line 200)
self.WaveletDenoiseOnOff = self.findChild(QCheckBox, "WaveletDenoiseOnOff")
self.WaveletType = self.findChild(QComboBox, "WaveletType")
self.WaveletLevel = self.findChild(QSpinBox, "WaveletLevel")

# In data processing logic (line 450)
if self.WaveletDenoiseOnOff.isChecked():
    wavelet = self.WaveletType.currentText()
    level = self.WaveletLevel.value()
    processed_data = apply_wavelet_denoising(processed_data, wavelet, level, sampling_rate)
```

**4. Install new dependency**:
```bash
pip install PyWavelets
```

**5. Update build config**:
```json
"hidden_imports": [
  "pywt",
  "pywt._extensions",
  "pywt._extensions._pywt"
]
```

### Adding a New Hardware Board

**1. Find BrainFlow Board ID**:
- Visit: https://brainflow.readthedocs.io/en/stable/SupportedBoards.html
- Example: OpenBCI Cyton = 0, Ganglion = 1, Muse = 22

**2. Update `backend_eeg.py` if needed**:
```python
def configure_new_board(board_shim, board_id):
    """Special configuration for new board"""
    if board_id == 22:  # Muse
        # Muse-specific settings
        board_shim.config_board("p50")  # Enable PPG
    elif board_id == 0:  # Cyton
        # Cyton uses different commands
        board_shim.config_board("xN0160110X")  # Channel settings
```

**3. Update UI**:
- Add board ID to documentation
- Update dropdown/help text
- Test with actual hardware

**4. Document compatibility**:
- Update README.md (user guide)
- Add to supported boards list
- Note any special requirements (drivers, firmware)

---

## Performance Optimization

### Startup Time Optimization

**Techniques Used**:
1. **Lazy Loading**: Import heavy modules only when needed (saves ~10s)
2. **Async Model Loading**: Defer GPT4All model load (saves ~5s)
3. **UI Caching**: Don't recreate widgets unnecessarily
4. **Minimal Imports**: Only import what's needed at startup

**Measurement**:
```python
import time
start = time.time()
# ... code to measure
print(f"Elapsed: {time.time() - start:.2f}s")
```

### Runtime Performance

**Data Processing**:
- Use NumPy vectorized operations (100x faster than Python loops)
- Process in chunks (e.g., 1 second at a time)
- Cache filter coefficients (don't recalculate every frame)

**Visualization**:
- Limit update rate: 30-60 FPS max
- Downsample for display: `data[:, ::2]` (show every 2nd sample)
- Use smaller time windows: 5-10 seconds instead of 30+
- GPU acceleration with VisPy (10x faster than CPU)

**Memory Management**:
- Use ring buffers for continuous data
- Limit recording buffer size (auto-save if too large)
- Release old data: `del old_data; gc.collect()`

### Build Size Optimization

**Current Size**: ~2 GB (mostly due to SciPy, Qt, VisPy)

**Reduction Strategies**:
1. **Exclude unused modules** (line 342 in `build_config.json`):
   ```json
   "exclude_modules": ["matplotlib", "pandas", "tkinter"]
   ```
   Saves ~500 MB

2. **UPX compression** (trade-off: slower startup):
   ```json
   "upx": true
   ```
   Saves ~30% (600 MB)

3. **Onefile mode** (single exe, slower):
   ```json
   "onefile": true
   ```
   Smaller distribution, but unpacks on every run

4. **Remove debug symbols**:
   ```json
   "strip": true
   ```
   Saves ~50 MB

**We chose**: Folder mode, no UPX, with excluded modules = fast startup, reasonable size.

---

## Troubleshooting

### Development Issues

**1. "Module not found" when running `main.py`**
- Check virtual environment activated
- Run `pip list` to verify packages installed
- Check `sys.path` includes project root

**2. Resources not loading (images missing)**
- Recompile resources: `pyrcc5 resources/resources.qrc -o resources_rc.py`
- Check `import resources_rc` in `main.py`
- Verify paths use `:/images/` prefix (not `resources/`)

**3. Qt Designer won't open `.ui` file**
- Ensure Qt Designer installed (separate from PyQt5)
- Or use Qt Creator (includes Designer)
- Or edit XML manually (not recommended)

**4. Board won't connect**
- Check Board ID correct (Neuropawn = 57)
- Verify COM port: Device Manager → Ports (COM & LPT)
- Try different USB port
- Check drivers: `dmesg` (Linux), Device Manager (Windows)
- Test with BrainFlow examples first

**5. Plots not displaying**
- Check GPU drivers (VisPy needs OpenGL 2.1+)
- Test OpenGL: `python -c "from vispy import app; app.use_app('pyqt5')"`
- Switch to PyQtGraph backend (modify visualizer code)
- Reduce sampling rate if performance issue

**6. Chatbot not responding**
- First run downloads model (~5-10 min)
- Check cache: `~/.cache/gpt4all/` or `C:\Users\<user>\AppData\Local\gpt4all\`
- Verify `faq.json` exists
- Test GPT4All separately: `python -c "from gpt4all import GPT4All; m = GPT4All('Meta-Llama-3-8B-Instruct.Q4_0.gguf')"`

### Build Issues

**1. "Module not found" in built executable**
- Add to `hidden_imports` in `build_config.json`
- Check spelling (case-sensitive on Linux)
- Try `--add-module` flag: `python build_exe.py --add-module scipy.special`

**2. "DLL load failed" or "Missing DLL"**
- Find missing DLL name (usually in error message)
- Locate DLL: Search Python site-packages
- Add to `binary_files` in `build_config.json`
- Use Dependency Walker to find DLL dependencies

**3. "Failed to execute script"**
- Build with `--debug` flag to see console output
- Check `warn-MINDStream.txt` in `build/MINDStream/`
- Common cause: Missing data file (`.ui`, `.json`, `.txt`)
- Add missing files to `data_files`

**4. Executable won't start (no error message)**
- Run from command line: `cmd` → `cd dist\MINDStream` → `MINDStream.exe`
- Check Windows Event Viewer: Application logs
- Try `--console` mode: `python build_exe.py --debug`
- Test on clean VM (no Python installed)

**5. "Import Error: No module named 'PyQt5.sip'"**
- PyQt5 version mismatch
- Reinstall: `pip uninstall PyQt5 PyQt5-sip PyQt5-Qt5; pip install PyQt5`
- Or add to hidden imports: `PyQt5.sip`

**6. Build takes forever / hangs**
- Normal first build: 5-10 minutes
- Subsequent builds: 2-3 minutes
- If hanging >15 min: Ctrl+C, check error
- Try `--clean` flag: `python build_exe.py --clean`
- Check antivirus not scanning build folder (whitelist)

**7. "UnicodeDecodeError" during build**
- File has non-ASCII characters (accents, emoji)
- Use UTF-8 encoding in all source files
- Add encoding declaration: `# -*- coding: utf-8 -*-`

### Runtime Issues (Built Executable)

**1. Slow startup (>30 seconds)**
- Normal first run (GPT4All model loading)
- If every run slow: UPX compression issue (disable in config)
- Or virus scanner blocking (whitelist exe)

**2. High CPU usage**
- Visualization running in background
- Switch to "NoPlot" tab to reduce load
- Lower update rate in visualization code

**3. Memory leak (RAM keeps growing)**
- Likely in data collection or visualization loop
- Use `tracemalloc` to find leak:
  ```python
  import tracemalloc
  tracemalloc.start()
  # ... run code
  snapshot = tracemalloc.take_snapshot()
  for stat in snapshot.statistics('lineno')[:10]:
      print(stat)
  ```

**4. Crashes on specific actions**
- Check logs (if logging enabled)
- Reproduce in Python (not exe) for better error messages
- Use `--debug` build for console output
- Wrap risky code in try-except:
  ```python
  try:
      risky_operation()
  except Exception as e:
      print(f"Error: {e}")
      # Log or handle gracefully
  ```

---

## Contributing

### Code Style

- Follow **PEP 8** Python style guide
- Use **type hints** where appropriate:
  ```python
  def process_data(data: np.ndarray, sampling_rate: int) -> np.ndarray:
      ...
  ```
- Document functions with **docstrings**:
  ```python
  def apply_filter(data, low_cut, high_cut, sampling_rate):
      """
      Apply bandpass filter to EEG data.
      
      Args:
          data: ndarray of shape (n_channels, n_samples)
          low_cut: Low cutoff frequency in Hz
          high_cut: High cutoff frequency in Hz
          sampling_rate: Sampling rate in Hz
      
      Returns:
          Filtered data of same shape
      """
  ```
- Keep functions small: <50 lines ideally
- Use meaningful variable names: `sampling_rate` not `sr`

### Git Workflow

1. **Create feature branch**:
   ```bash
   git checkout -b feature/add-wavelet-denoising
   ```

2. **Make changes and commit**:
   ```bash
   git add .
   git commit -m "Add wavelet denoising to data processing pipeline"
   ```

3. **Push and create pull request**:
   ```bash
   git push origin feature/add-wavelet-denoising
   ```

4. **Code review**: Wait for approval

5. **Merge to main**: After review

### Testing Checklist

Before committing:
- [ ] Test with real hardware (if available)
- [ ] Test with synthetic board (Board ID -1)
- [ ] Test all visualizations (µV, FFT, PSD)
- [ ] Test recording and export
- [ ] Test chatbot functionality
- [ ] Run linter: `pylint main.py`
- [ ] Build executable: `python build_exe.py`
- [ ] Test built exe on different computer
- [ ] Check for console errors
- [ ] Update documentation if needed

---

## Additional Resources

- **BrainFlow Documentation**: https://brainflow.readthedocs.io/
- **PyQt5 Documentation**: https://www.riverbankcomputing.com/static/Docs/PyQt5/
- **VisPy Documentation**: http://vispy.org/documentation.html
- **SciPy Signal Processing**: https://docs.scipy.org/doc/scipy/reference/signal.html
- **PyInstaller Manual**: https://pyinstaller.org/en/stable/
- **GPT4All Docs**: https://docs.gpt4all.io/
- **MIND Design Team**: https://minduofc.ca/

---

## License & Contact

**Developer**: Taha Malik, Cofounder of MIND Design Team  
**Organization**: University of Calgary - MIND Design Team  
**Website**: https://minduofc.ca/

For bugs, feature requests, or contributions, please contact the MIND Design Team.

---

**Happy Coding!! 🧠⚡**
