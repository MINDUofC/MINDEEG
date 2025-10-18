# MINDStream EEG - User Guide

<p align="center">
  <img src="MINDStream/_internal/resources/MIND LOGO Transparent.png" alt="MIND Logo" width="200"/>
</p>

Welcome to **MINDStream**, your comprehensive EEG signal processing and visualization tool!

---

## 📖 Quick Start Guide

### Running the Application

**IMPORTANT**: Do NOT move `MINDStream.exe` out of the `MINDStream` folder!

The executable needs to stay in its folder to access required files. Instead:

#### Create a Desktop Shortcut (Recommended)

**Windows:**
1. Right-click on `MINDStream.exe`
2. Select **Send to** → **Desktop (create shortcut)**
3. Now you can launch from your desktop!

**Alternative**: Pin to taskbar
1. Right-click `MINDStream.exe`
2. Select **Pin to taskbar**

---

## 🧠 What is MINDStream?

MINDStream is a professional EEG (Electroencephalography) data acquisition and analysis platform designed for:

- **Researchers** conducting brain-computer interface (BCI) experiments
- **Students** learning about EEG signals and neuroscience
- **Developers** building neurofeedback applications
- **Clinicians** exploring brain signal patterns

### Key Features

✨ **Real-Time EEG Visualization**
- Live signal monitoring in microvolts (µV)
- Frequency analysis (FFT - Fast Fourier Transform)
- Power spectral density (PSD) visualization

🔧 **Advanced Signal Processing**
- Bandpass and bandstop filtering
- Independent Component Analysis (ICA) for artifact removal
- Detrending and noise reduction
- Built-in 50/60 Hz notch filters

⏱️ **Precise Timing & Recording**
- Millisecond-accurate timing for experiments
- Visual timeline for event marking
- Export data in multiple formats (CSV, NPY, MAT)

🤖 **AI-Powered Assistant**
- Built-in chatbot to answer EEG questions
- Explains features and processing methods
- No internet required - runs locally!

---

## 🔌 Compatible Hardware

### Currently Supported

- **Neuropawn EEG System** (Board ID: 57)
  - 1-8 channel configuration
  - Serial (COM port) connection
  - Support for common reference (RLD)

### Coming Soon
- Additional BrainFlow-compatible devices
- Check for updates at https://minduofc.ca/

---

## 🚀 Getting Started

### 1. Connect Your Hardware

1. Plug in your Neuropawn device via USB
2. Wait for Windows to recognize the device
3. Note the COM port (e.g., COM3, COM4)

### 2. Launch MINDStream

Double-click `MINDStream.exe` (or use your shortcut)

### 3. Configure Your Board

On the left panel:
- **Board ID**: Enter `57` for Neuropawn
- **Port**: Select your device's COM port from dropdown
- **Channels**: Use the dial to select number of active channels (1-8)
- **Common Ref**: Check if using common reference electrode (RLD)

### 4. Turn On the Board

Click the **Power button** (⚡) to connect to your device.  
Status will change from "OFF" to "ON" when ready.

### 5. Start Visualizing

Switch between tabs at the bottom:
- **NoPlot**: Minimal resource usage (recommended for recording)
- **µV Plot**: See real-time brain signals
- **FFT**: View frequency spectrum
- **PSD**: Analyze power distribution

### 6. Apply Filters (Optional)

Adjust preprocessing settings:
- **Bandpass**: Keep only desired frequency range (e.g., 8-30 Hz for motor imagery)
- **Bandstop**: Remove specific frequencies (e.g., 50 Hz power line noise)
- **Detrend**: Remove DC offset and linear trends
- **ICA**: Remove artifacts like eye blinks (requires calibration)

### 7. Record Data

1. Set your export folder (click folder icon 📁)
2. Enter a filename
3. Click **Record** button to start/stop
4. Data saves automatically when stopped

---

## 💡 Tips & Tricks

### For Best Performance

- Use **NoPlot** tab when recording to avoid performance issues
- Close other resource-heavy applications
- For long recordings (>10 minutes), ensure adequate disk space

### Signal Quality

- Check electrode impedance (lower is better, <10 kΩ ideal)
- Minimize movement during recording
- Use ICA to remove eye blink artifacts
- Apply bandpass filter to focus on relevant frequencies

### Timing Experiments

- Use the **Timeline Widget** to mark events
- Click **Black Screen Timer** for full-screen timing (minimizes distractions)
- Recording timestamps are precise to the millisecond

### Need Help?

1. **Use the Dropdown Menu** (top-left): Comprehensive guides on every feature
2. **Ask the Chatbot** (click chat button): Get instant answers about EEG and signal processing
3. **Check the FAQ**: Common questions answered

---

## 📊 Understanding Your Data

### File Formats

**CSV** (Comma-Separated Values)
- Easy to open in Excel, MATLAB, Python
- Human-readable
- Best for general use

**NPY** (NumPy Array)
- Fast loading in Python
- Preserves data types
- Recommended for Python users

**MAT** (MATLAB)
- Compatible with MATLAB/Octave
- Best for MATLAB workflows

### Data Structure

Exported files contain:
- **Rows**: Time samples (at your device's sampling rate)
- **Columns**: EEG channels (Ch1, Ch2, ..., Ch8)
- Each value represents voltage in microvolts (µV)

---

## ⚙️ System Requirements

### Minimum
- Windows 10 or later
- 4 GB RAM
- Dual-core processor
- 500 MB free disk space
- USB 2.0 port

### Recommended
- Windows 10/11
- 8 GB RAM
- Quad-core processor
- 2 GB free disk space
- USB 3.0 port
- Dedicated GPU (for smoother visualizations)

---

## 🔧 Troubleshooting

### "Board won't connect"
- Verify correct COM port selected (try refreshing the dropdown)
- Check Board ID is `57` for Neuropawn
- Ensure device is plugged in and powered on
- Try a different USB port
- Restart the application

### "No signal/flat line"
- Check electrode connections
- Verify channel dial is set correctly (1-8, not 0)
- Ensure electrodes have good contact with skin
- Check if board is turned ON

### "Application won't start"
- Don't move `MINDStream.exe` out of its folder
- Check antivirus isn't blocking it
- Run as Administrator (right-click → Run as administrator)
- Reinstall from original package

### "Plots are laggy"
- Switch to **NoPlot** tab
- Close other applications
- Reduce number of active channels
- Disable unnecessary filters

### "Can't find my data"
- Check the export destination (folder icon)
- Look in `Documents/MINDStream_Data/` (default location)
- Data only saves after clicking **Record** again to stop

---

## 📚 Learn More

### In-App Resources

- **Menu Dropdown** (top-left): Detailed explanations of all features
- **Chatbot**: Ask questions about EEG, filtering, ICA, and more
- **Status Bar** (bottom-left): Real-time feedback on actions

### External Resources

- **BrainFlow Documentation**: https://brainflow.readthedocs.io/
- **MIND Design Team**: https://minduofc.ca/
- **Instagram**: [@mind.uofc](https://instagram.com/mind.uofc)
- **LinkedIn**: [MIND Design Team](https://linkedin.com/company/mind-uofc)

### EEG Basics

**What are brain waves?**
- **Delta (0.5-4 Hz)**: Deep sleep
- **Theta (4-8 Hz)**: Meditation, creativity
- **Alpha (8-12 Hz)**: Relaxed wakefulness
- **Beta (12-30 Hz)**: Active thinking, focus
- **Gamma (30-100 Hz)**: High-level processing

**Common Applications:**
- Motor imagery (imagining movement)
- Alpha rhythm detection (eyes open/closed)
- Eye blink detection
- Attention monitoring
- Meditation feedback

---

## 📞 Support & Feedback

### Need Help?

1. Check the **in-app menu** (most questions answered there!)
2. Ask the **chatbot** for technical EEG questions
3. Contact the MIND Design Team: https://minduofc.ca/

### Report Bugs

Found a problem? Let us know! Include:
- What you were doing when the error occurred
- Error messages (if any)
- Your Windows version
- Hardware being used

### Feature Requests

Have ideas for new features? We'd love to hear them! Contact us through our website.

---

## 📄 About

**MINDStream** was developed by the **MIND Design Team** at the University of Calgary.

**Lead Developer**: Taha Malik, Cofounder  
**Organization**: MIND Design Team, University of Calgary  
**Website**: https://minduofc.ca/

### Mission

We build accessible EEG, EMG, and ECG tools to advance neuroscience research and education. Our goal is to make brain-computer interfaces available to students, researchers, and innovators worldwide.

### Version Information

Check the **About** section in the app menu for current version.

---

## ⚖️ Disclaimer

This software is intended for **research and educational purposes only**.  
It is **not a medical device** and should not be used for clinical diagnosis or treatment.

Always follow proper EEG safety protocols and consult qualified professionals for medical advice.

---

**Thank you for using MINDStream!** 🧠✨

We hope this tool empowers your neuroscience research and learning journey.

*— The MIND Design Team*

---

## 🔗 Quick Links

- **Website**: https://minduofc.ca/
- **Instagram**: https://instagram.com/mind.uofc
- **LinkedIn**: https://linkedin.com/company/mind-uofc
- **Support**: Contact via website

---

*Last Updated: October 2024*

