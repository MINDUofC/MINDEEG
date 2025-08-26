import sys
import os
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QIcon, QKeyEvent
from PyQt5 import uic
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtGui import QIntValidator, QGradient
from PyQt5.QtWidgets import QLineEdit, QWidget, QPushButton, QTextEdit, QVBoxLayout, QDialog, QGraphicsOpacityEffect, QMessageBox
from PyQt5.QtCore import Qt, QUrl, QPoint
from PyQt5.QtGui import QDesktopServices, QPainter, QLinearGradient, QColor, QBrush, QPen
from backend_logic.chatbot.chatbotBE import ChatbotBE

class ChatbotFE(QWidget):
    def __init__(self, parent: QDialog):
        super().__init__(parent)
        
        self.expanded = False
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Initialize with safe defaults
        self._last_parent_size = None
        self._repositioning = False
        
        # Use a timer to handle delayed repositioning for smoother transitions
        self.reposition_timer = QTimer()
        self.reposition_timer.setSingleShot(True)
        self.reposition_timer.timeout.connect(self._delayed_reposition)
        
        self.resize(int(0.05*self.parentWidget().width()),int(0.05*self.parentWidget().height()))  # Start collapsed
        self.setStyleSheet("background-color: #5C8FFF; border-radius: 15px; border: 2px solid #0047B2;")
        
        self.toggle_button = QPushButton("💬", self)
        self.toggle_button.resize(int(0.03*self.parentWidget().width()),int(0.03*self.parentWidget().height()))
        self.toggle_button.setStyleSheet(
            f"""
QPushButton {{
  border-radius: 50px;
  background-color: #85C7F2;
  font-size: {int(0.025*self.parentWidget().width())}px;
  border: 2px solid #0047B2;
  padding: 6px;
}}
QPushButton:hover {{
  background-color: #6DBAF0;
  border-color: #0047B2;
}}
QPushButton:pressed {{
  background-color: #4FA7E8;
  padding-top: 7px;
  padding-bottom: 5px;
}}
            """
        )
        self.toggle_button.clicked.connect(self.toggle_chatbot)

        

        # Chatbox
        self.chat_box = QWidget(self)
        self.chat_layout = QVBoxLayout(self.chat_box)
        self.chat_layout.setContentsMargins(5, 5, 5, 45)  # Leave space at bottom for toggle button
        self.chat_layout.setSpacing(5)

        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setStyleSheet("background-color: #FFFFFF; border-radius: 15px; border: 2px solid #0047B2; font-family: 'Montserrat SemiBold';")

        self.input_box = QLineEdit()
        self.input_box.setStyleSheet("background-color: #FFFFFF; border-radius: 10px; border: 2px solid #0047B2; font-family: 'Montserrat SemiBold';")
        self.input_box.setPlaceholderText("Enter your message here...")
        self.input_box.returnPressed.connect(self.handle_user_input)

        self.new_conversation_button = QPushButton("New Conversation", self)
        self.new_conversation_button.setStyleSheet(
            """
QPushButton {
  background-color: #FFFFFF;
  border-radius: 10px;
  border: 2px solid #0047B2;
  font-family: 'Montserrat SemiBold';
  color: #0A1F44;
  padding: 6px 12px;
}
QPushButton:hover {
  background-color: #F5F9FF;
  border-color: #1E63D0;
}
QPushButton:pressed {
  background-color: #EAF4FF;
  padding-top: 7px;
  padding-bottom: 5px;
}
            """
        )
        self.new_conversation_button.clicked.connect(self.new_conversation)
    
        self.chat_layout.addWidget(self.new_conversation_button)
        self.chat_layout.addWidget(self.chat_history)
        self.chat_layout.addWidget(self.input_box)

        # Opacity effect + animation (non-intrusive, keeps your styling)
        self.chat_opacity = QGraphicsOpacityEffect(self.chat_box)
        self.chat_box.setGraphicsEffect(self.chat_opacity)
        self.chat_opacity.setOpacity(0.0)
        self.fade = QPropertyAnimation(self.chat_opacity, b"opacity", self)
        self.fade.setDuration(100)  # 50–100ms
        self.fade.setEasingCurve(QEasingCurve.InOutQuad)

        self.chat_box.hide()
        
        # Install event filter on parent to catch resize events
        if self.parentWidget():
            self.parentWidget().installEventFilter(self)
        
        self.reposition()
        # Show the widget
        self.show()

    def toggle_chatbot(self):
        if self.expanded:
            # Collapse
            self.expanded = False
            # fade out first to avoid visual artifact, then resize/hide in callback
            self.toggle_button.raise_()
            try:
                self.fade.stop()
                self.fade.setStartValue(self.chat_opacity.opacity())
                self.fade.setEndValue(0.0)
                # disconnect previous connections safely
                try:
                    self.fade.finished.disconnect()
                except TypeError:
                    pass
                self.fade.finished.connect(self._finish_collapse)
                self.fade.start()
            except Exception:
                self._finish_collapse()

        elif self.expanded == False:
            # Prompt if local LLM is not installed yet (~4.66GB)
            try:
                if not ChatbotBE.is_model_installed():
                    msg = QMessageBox(self)
                    msg.setStyleSheet(
                        """
QMessageBox {
  background-color: #F5F9FF;
  border-radius: 12px;
}
QLabel {
  font-family: 'Montserrat SemiBold';
  color: #0A1F44;
  border: none;
}
QPushButton {
  font-family: 'Montserrat SemiBold';
  color: #0A1F44;
  background-color: #FFFFFF;
  border: 2px solid #0047B2;
  min-width: 44px;
  min-height: 44px;
  border-radius: 22px; /* circular */
  padding: 0;
}
QPushButton:hover {
  background-color: #F5F9FF;
  border-color: #1E63D0;
}
QPushButton:pressed {
  background-color: #EAF4FF;
}
QScrollArea, QScrollArea > QWidget > QWidget, QFrame {
  background: transparent;
  border: none;
}
                        """
                    )
                    msg.setIcon(QMessageBox.Question)
                    msg.setWindowTitle("Install Local LLM?")
                    msg.setText("This feature can run a Local LLM on your device.")
                    msg.setInformativeText("Download size is approximately 4.66 GB. Do you want to install it now to run the chatbot locally?")
                    msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                    msg.setDefaultButton(QMessageBox.No)
                    result = msg.exec_()
                    if result != QMessageBox.Yes:
                        # Keep hidden and abort expansion
                        self.expanded = False
                        return
                    # TODO: Initialize local LLM backend here (model install/setup)
            except Exception:
                # If the check or dialog fails, proceed safely without blocking UI
                pass

            # Expand
            self.expanded = True
            self.resize(int(0.25*self.parentWidget().width()),int(0.30*self.parentWidget().height()))
            # show then fade in
            try:
                self.chat_box.show()
                self.fade.stop()
                self.fade.setStartValue(self.chat_opacity.opacity())
                self.fade.setEndValue(1.0)
                try:
                    self.fade.finished.disconnect()
                except TypeError:
                    pass
                self.fade.start()
            except Exception:
                self.chat_box.show()
            self.reposition()  # Reposition after resize
            self.toggle_button.raise_()

    def _finish_collapse(self):
        """Hide chat box and then resize/reposition cleanly after fade-out."""
        try:
            self.chat_box.hide()
        except Exception:
            pass
        # Now resize to collapsed size and reposition
        try:
            self.resize(int(0.05*self.parentWidget().width()),int(0.05*self.parentWidget().height()))
        except Exception:
            pass
        self.reposition()
        self.toggle_button.raise_()
            
    def reposition(self):
        """Repositions the chatbot with comprehensive error handling and state validation."""
        if self._repositioning:
            return  # Prevent recursive calls
            
        self._repositioning = True
        
        try:
            p = self.parentWidget()
            if not p or not self.isVisible():
                return
                
            # Ensure parent has valid dimensions
            if p.width() <= 0 or p.height() <= 0:
                return
                
            # Store current parent size for comparison
            current_parent_size = (p.width(), p.height())
            
            # Calculate sizes based on current parent dimensions
            if self.expanded:
                new_width = max(200, int(0.25 * p.width()))  # Minimum 200px width
                new_height = max(150, int(0.30 * p.height()))  # Minimum 150px height
                button_size = max(30, int(0.035 * min(p.width(), p.height())))  # Square button
            else:
                button_size = max(30, int(0.035 * min(p.width(), p.height())))  # Square button
                new_width = button_size
                new_height = button_size
            
            # Resize the chatbot widget
            self.resize(new_width, new_height)
            
            # Fixed 10 pixel margins from bottom and right
            margin_x = 10
            margin_y = 10
            
            # Calculate position ensuring it stays within parent bounds
            x = max(0, p.width() - self.width() - margin_x)
            y = max(0, p.height() - self.height() - margin_y)
            
            # Move the chatbot
            self.move(x, y)
            
            # Resize and reposition toggle button
            self.toggle_button.resize(button_size, button_size)
            font_size = max(12, int(0.02 * min(p.width(), p.height())))
            self.toggle_button.setStyleSheet(
                f"""
QPushButton {{
  border-radius: {button_size//2}px;
  background-color: #85C7F2;
  font-size: {font_size}px;
  border: 2px solid #0047B2;
  padding: 6px;
}}
QPushButton:hover {{
  background-color: #6DBAF0;
  border-color: #0047B2;
}}
QPushButton:pressed {{
  background-color: #4FA7E8;
  padding-top: 7px;
  padding-bottom: 5px;
}}
                """
            )
            
            if self.expanded:
                # Position toggle button at bottom right of chatbox
                btn_x = max(0, self.width() - self.toggle_button.width() - 5)
                btn_y = max(0, self.height() - self.toggle_button.height() - 5)
                self.toggle_button.move(btn_x, btn_y)
                
                # Resize chat box to account for toggle button
                if hasattr(self, 'chat_box') and self.chat_box:
                    self.chat_box.resize(self.width(), self.height())
            else:
                # Position toggle button at center of collapsed chatbox
                self.toggle_button.move(0, 0)
                
            # Update stored parent size
            self._last_parent_size = current_parent_size
            
        except Exception as e:
            print(f"Error in chatbot reposition: {e}")
        finally:
            self._repositioning = False
            
    def _delayed_reposition(self):
        """Delayed repositioning to handle rapid resize events smoothly."""
        self.reposition()
        
    def eventFilter(self, obj, event):
        """Filter events from parent widget to catch resize events."""
        if obj == self.parentWidget():
            if event.type() == event.Resize:
                # Use timer to debounce rapid resize events
                self.reposition_timer.start(50)  # 50ms delay
            elif event.type() == event.Show:
                # Handle parent show events
                self.reposition_timer.start(100)
            elif event.type() == event.WindowStateChange:
                # Handle fullscreen/windowed state changes
                self.reposition_timer.start(100)
                
        return super().eventFilter(obj, event)
        
    def showEvent(self, event):
        """Handle show events to ensure proper positioning."""
        super().showEvent(event)
        # Delay repositioning to ensure parent is fully rendered
        self.reposition_timer.start(100)
        
    def resizeEvent(self, event):
        """Handle resize events for the chatbot itself."""
        super().resizeEvent(event)
        if hasattr(self, 'chat_box') and self.chat_box and self.expanded:
            # Ensure chat box fills the widget properly
            self.chat_box.resize(self.width(), self.height())
            
    def closeEvent(self, event):
        """Clean up event filter when closing."""
        if self.parentWidget():
            self.parentWidget().removeEventFilter(self)
        super().closeEvent(event)

    def new_conversation(self):
        pass

    def handle_user_input(self):
        pass