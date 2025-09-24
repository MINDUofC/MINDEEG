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

<p><b>Developer:</b> Taha Malik was the sole developer of this project</p>

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

<p><b>Getting Started:</b></p>
<ol>
<li><b>Connect Hardware:</b> Connect your NeuroPawn EEG device to your computer via USB</li>
<li><b>Select Port:</b> Click the Port dropdown to automatically detect and select your device's COM port</li>
<li><b>Configure Channels:</b> Use the Channel Dial to set the number of active EEG channels (1-8)</li>
<li><b>Turn On Board:</b> Check the "Board On/Off" checkbox to establish connection</li>
</ol>

<p><b>Data Visualization:</b></p>
<ul>
<li><b>µV Tab:</b> View real-time EEG signals in microvolts</li>
<li><b>FFT Tab:</b> Analyze frequency domain data with Fast Fourier Transform</li>
<li><b>PSD Tab:</b> Examine Power Spectral Density for frequency band analysis</li>
</ul>

<p><b>Signal Processing:</b></p>
<ul>
<li><b>Bandpass Filters:</b> Enable filtering to focus on specific frequency ranges</li>
<li><b>Bandstop Filters:</b> Remove unwanted frequency components (like 60Hz noise)</li>
<li><b>FastICA:</b> Apply Independent Component Analysis for artifact removal (requires 2+ channels)</li>
<li><b>Smoothing:</b> Use Average or Median smoothing for cleaner signals</li>
</ul>

<p><b>Recording Data:</b></p>
<ol>
<li>Select data types to record (Raw µV, FFT, PSD)</li>
<li>Choose export destination folder</li>
<li>Select file format (CSV)</li>
<li>Configure trial parameters (duration, intervals)</li>
<li>Click Record to start data collection</li>
<li>Use Export to save recorded data</li>
</ol>

<p><b>AI Assistant:</b> Use the chatbot in the bottom-right for real-time help and technical support.</p>

<p><b>Tips:</b> Ensure good electrode contact, minimize movement during recording, and check signal quality before starting experiments.</p>
        """
        
        dialog = self.create_custom_dialog("How to Use MINDStream EEG", how_to_text, 700, 500)
        dialog.exec_()
