import sys
import os
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QIcon, QKeyEvent
from PyQt5 import uic
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtGui import QIntValidator, QGradient
from PyQt5.QtWidgets import QLineEdit, QWidget, QPushButton, QTextEdit, QVBoxLayout, QDialog, QGraphicsOpacityEffect, QMessageBox, QScrollArea, QHBoxLayout, QFrame, QSizePolicy, QApplication
from PyQt5.QtCore import Qt, QUrl, QPoint
from PyQt5.QtGui import QDesktopServices, QPainter, QLinearGradient, QColor, QBrush, QPen, QTextOption
from backend_logic.chatbot.chatbotBE import ChatbotBE
from PyQt5.QtCore import QThread, QObject, pyqtSignal, pyqtSlot

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

        # Scrollable chat history
        self.chat_history_scroll = QScrollArea()
        self.chat_history_scroll.setWidgetResizable(True)
        self.chat_history_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chat_history_scroll.setFrameShape(QFrame.NoFrame)
        self.chat_history_scroll.setStyleSheet(
            """
            QScrollArea { border-radius: 5px; border: 2px solid #0047B2; background: #FFFFFF; }
            QScrollArea > QWidget { background: transparent; }
            QScrollArea > QWidget > QWidget { background: transparent; }
            QScrollArea.viewport { background-color: #FFFFFF; }
            """
        )

        self.chat_history_container = QWidget()
        self.chat_history_container.setStyleSheet("background-color: transparent; font-family: 'Montserrat SemiBold';border: 0px")
        self.chat_history_layout = QVBoxLayout(self.chat_history_container)
        # Remove extra whitespace
        self.chat_history_layout.setContentsMargins(0, 0, 0, 0)
        self.chat_history_layout.setSpacing(0)

        self.chat_history_scroll.setWidget(self.chat_history_container)
        

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
        self.chat_layout.addWidget(self.chat_history_scroll)
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
            # Expand UI first (no backend checks here)
            self.expanded = True
            self.resize(int(0.25*self.parentWidget().width()),int(0.30*self.parentWidget().height()))
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
            self.reposition()
            self.toggle_button.raise_()

            # Disable input and defer backend init so UI is responsive
            if not hasattr(self, 'chatbot_be'):
                try:
                    self.input_box.setEnabled(False)
                    self.input_box.setPlaceholderText("Initializing chatbot...")
                except Exception:
                    pass
                QTimer.singleShot(300, self._ensure_backend_ready_after_show)
            else:
                try:
                    self.input_box.setEnabled(True)
                    self.input_box.setPlaceholderText("Enter your message here...")
                except Exception:
                    pass

    def _ensure_backend_ready_after_show(self):
        # If backend already exists or is initializing, ensure input is enabled and return
        if hasattr(self, 'chatbot_be') and self.chatbot_be is not None:
            try:
                self.input_box.setEnabled(True)
                self.input_box.setPlaceholderText("Enter your message here...")
            except Exception:
                pass
            return

        # Decide whether to prompt purely via filesystem check (no GPT4All calls)
        if ChatbotBE.model_exists_locally():
            # Start backend in background without prompt
            self._start_backend_worker()
        else:
            # Prompt user to allow initialization/download
            try:
                msg = QMessageBox(self)
                msg.setStyleSheet(
                    """
                        QMessageBox { background-color: #F5F9FF; border-radius: 12px; }
                        QLabel { font-family: 'Montserrat SemiBold'; color: #0A1F44; border: none; }
                        QPushButton { font-family: 'Montserrat SemiBold'; color: #0A1F44; background-color: #FFFFFF; border: 2px solid #0047B2; min-width: 44px; min-height: 44px; border-radius: 22px; padding: 0; }
                        QPushButton:hover { background-color: #F5F9FF; border-color: #1E63D0; }
                        QPushButton:pressed { background-color: #EAF4FF; }
                        QScrollArea, QScrollArea > QWidget > QWidget, QFrame { background: transparent; border: none; }
                    """
                )
                msg.setIcon(QMessageBox.Question)
                msg.setWindowTitle("Initialize Local LLM?")
                msg.setText("This feature will need to run a Local LLM on your device. Would you like to proceed and install it?")
                msg.setInformativeText("Installing may take a few minutes. Also note that the model is ~4.66 GB. Also note it is HIGHLY RECOMMENDED to have a NVIDIA CUDA-enabled GPU for this feature. Proceed?")
                msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                msg.setDefaultButton(QMessageBox.No)
                result = msg.exec_()
                if result != QMessageBox.Yes:
                    try:
                        self.input_box.setEnabled(False)
                        self.input_box.setPlaceholderText("Backend not initialized.")
                    except Exception:
                        pass
                    return
            except Exception:
                pass

            self.toggle_button.setEnabled(False)
            self.new_conversation_button.setEnabled(False)
            self._start_backend_worker_LLM_installation()

    class _BackendInitWorker(QObject):
        finished = pyqtSignal(object)
        error = pyqtSignal(str)

        @pyqtSlot()
        def run(self):
            try:
                be = ChatbotBE()
                self.finished.emit(be)
            except Exception as e:
                self.error.emit(str(e))

    def _start_backend_worker_LLM_installation(self):
        try:
            self._backend_thread = QThread()
            self._backend_worker = ChatbotFE._BackendInitWorker()
            self._backend_worker.moveToThread(self._backend_thread)
            self._backend_thread.started.connect(self._backend_worker.run)
            self._backend_worker.finished.connect(self._on_backend_ready_LLM_installation)
            self._backend_worker.error.connect(self._on_backend_failed_LLM_installation)
            self._backend_worker.finished.connect(self._backend_thread.quit)
            self._backend_worker.error.connect(self._backend_thread.quit)
            self._backend_thread.finished.connect(self._clear_backend_worker_refs)
            self._backend_thread.start()
        except Exception:
            self._on_backend_failed_LLM_installation("Failed to start backend thread")


    def _start_backend_worker(self):
        try:
            self._backend_thread = QThread()
            self._backend_worker = ChatbotFE._BackendInitWorker()
            self._backend_worker.moveToThread(self._backend_thread)
            self._backend_thread.started.connect(self._backend_worker.run)
            self._backend_worker.finished.connect(self._on_backend_ready)
            self._backend_worker.error.connect(self._on_backend_failed)
            self._backend_worker.finished.connect(self._backend_thread.quit)
            self._backend_worker.error.connect(self._backend_thread.quit)
            self._backend_thread.finished.connect(self._clear_backend_worker_refs)
            self._backend_thread.start()
        except Exception:
            self._on_backend_failed("Failed to start backend thread")

    def _clear_backend_worker_refs(self):
        self._backend_thread = None
        self._backend_worker = None

    @pyqtSlot(object)
    def _on_backend_ready(self, be):
        self.chatbot_be = be
        try:
            self.input_box.setEnabled(True)
            self.input_box.setPlaceholderText("Enter your message here...")
        except Exception:
            pass

    @pyqtSlot(object)
    def _on_backend_ready_LLM_installation(self, be):
        self.chatbot_be = be
        try:
            self.toggle_button.setEnabled(True)
            self.new_conversation_button.setEnabled(True)
            self.input_box.setEnabled(True)
            self.input_box.setPlaceholderText("Enter your message here...")
        except Exception:
            pass



    @pyqtSlot(str)
    def _on_backend_failed(self, err):
        try:
            self.input_box.setEnabled(False)
            self.input_box.setPlaceholderText("Initialization failed.")
        except Exception:
            pass


    @pyqtSlot(str)
    def _on_backend_failed_LLM_installation(self, err):
        try:
            self.toggle_button.setEnabled(True)
            self.new_conversation_button.setEnabled(True)
            self.input_box.setEnabled(False)
            self.input_box.setPlaceholderText("Initialization failed.")
        except Exception:
            pass


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
        # Update bubble widths responsively
        self._update_all_bubble_widths()


    def closeEvent(self, event):
        """Clean up event filter when closing."""
        if self.parentWidget():
            self.parentWidget().removeEventFilter(self)
        super().closeEvent(event)


    def handle_user_input(self):
        text = self.input_box.text().strip()
        if not text:
            return

        if not hasattr(self, 'chatbot_be'):
            try:
                self.chatbot_be = ChatbotBE()
            except Exception:
                return
                
        self.format_new_human_message(text, self.chat_history_container)
        self.input_box.clear()
        
        try:
            chatbot_response = self.chatbot_be.handle_LLM_cycle(text)
        except Exception:
            chatbot_response = "Sorry, something went wrong."
        self.format_new_chatbot_message(chatbot_response, self.chat_history_container)


    def format_new_chatbot_message(self, message: str, chatbot_history: QWidget):
        bubble = self._create_message_bubble(message, is_assistant=True)
        self._append_message_row(bubble, align_left=True)
        QTimer.singleShot(500, self._auto_scroll_to_bottom)
        
        

    def format_new_human_message(self, message: str, chatbot_history: QWidget):
        bubble = self._create_message_bubble(message, is_assistant=False)
        self._append_message_row(bubble, align_left=False)
        QTimer.singleShot(250, self._auto_scroll_to_bottom)

    def _create_message_bubble(self, message: str, is_assistant: bool) -> QWidget:
        text = QTextEdit(message)
        text.setReadOnly(True)
        text.setFrameStyle(QFrame.NoFrame)
        text.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        text.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        text.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        text.setLineWrapMode(QTextEdit.WidgetWidth)
        text.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)

        if is_assistant:
            # Chatbot bubble: light grey
            text.setStyleSheet(
                "background-color: #D7D7D7; border-radius: 12px; border: 1px solid #0047B2; padding: 8px; color: #0A1F44; font-family: 'Montserrat SemiBold';"
            )
        else:
            # Human bubble: light blue
            text.setStyleSheet(
                "background-color: #D0E7FF; border-radius: 12px; border: 1px solid #0047B2; padding: 8px; color: #0A1F44; font-family: 'Montserrat SemiBold';"
            )

        # Auto-grow when content changes (e.g., if updated incrementally)
        self._enable_auto_grow(text)
        self._fit_bubble_to_content(text)
        return text

    def _append_message_row(self, bubble: QWidget, align_left: bool) -> None:
        row = QWidget(self.chat_history_container)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 2, 0, 2)
        row_layout.setSpacing(0)

        if align_left:
            row_layout.addWidget(bubble, 0, Qt.AlignLeft)
            row_layout.addStretch(1)
        else:
            row_layout.addStretch(1)
            row_layout.addWidget(bubble, 0, Qt.AlignRight)

        self.chat_history_layout.addWidget(row)
        self._fit_bubble_to_content(bubble)
        # Re-fit once the layout has finalized to ensure correct size on right/left alignments
        QTimer.singleShot(0, lambda b=bubble: self._fit_bubble_to_content(b))

    def _auto_scroll_to_bottom(self) -> None:
        try:
            bar = self.chat_history_scroll.verticalScrollBar()
            bar.setValue(bar.maximum())
        except Exception:
            pass

    def _set_bubble_max_width(self, widget: QWidget) -> None:
        # Deprecated: kept for backward compatibility
        self._fit_bubble_to_content(widget)

    def _fit_bubble_to_content(self, widget: QTextEdit) -> None:
        try:
            viewport_width = max(50, self.chat_history_scroll.viewport().width())
            cap_width = int(viewport_width * 0.72)

            doc = widget.document()
            # Reset to unconstrained to measure ideal width (no wrap)
            doc.setTextWidth(-1)
            ideal = int(doc.idealWidth())
            # Add some padding to account for bubble padding and rounding
            ideal_with_padding = ideal + 16
            width = min(cap_width, max(80, ideal_with_padding))

            # Now set text width to the final bubble width minus inner padding for correct height
            doc.setTextWidth(width - 16)
            content_height = int(doc.size().height())
            height = content_height + 16

            widget.setFixedWidth(width)
            widget.setFixedHeight(height)
            widget.updateGeometry()
        except Exception:
            pass

    def _enable_auto_grow(self, widget: QTextEdit) -> None:
        try:
            # Recompute size when content changes (programmatic updates)
            widget.document().contentsChanged.connect(lambda: self._fit_bubble_to_content(widget))
        except Exception:
            pass

    def _update_all_bubble_widths(self) -> None:
        try:
            for i in range(self.chat_history_layout.count()):
                item = self.chat_history_layout.itemAt(i)
                row_widget = item.widget()
                if not isinstance(row_widget, QWidget):
                    continue
                row_layout = row_widget.layout()
                if not isinstance(row_layout, QHBoxLayout):
                    continue
                for j in range(row_layout.count()):
                    sub_item = row_layout.itemAt(j)
                    bubble = sub_item.widget()
                    if isinstance(bubble, QTextEdit):
                        self._fit_bubble_to_content(bubble)
        except Exception:
            pass

    def new_conversation(self):
        try:
            for i in reversed(range(self.chat_history_layout.count())):
                item = self.chat_history_layout.itemAt(i)
                w = item.widget()
                if w is not None:
                    w.setParent(None)
        except Exception:
            pass
        if hasattr(self, 'chatbot_be'):
            try:
                self.chatbot_be.handle_new_conversation()
            except Exception:
                pass
    