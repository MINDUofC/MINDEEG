import sys
import os
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QKeyEvent
from PyQt5 import uic
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtGui import QIntValidator, QGradient
from PyQt5.QtWidgets import QLineEdit, QWidget
from PyQt5.QtCore import Qt, QUrl, QPointF
from PyQt5.QtGui import QDesktopServices, QPainter, QLinearGradient, QColor, QBrush, QPen


class ChatbotFE(QWidget):
    def __init__(self):
        super().__init__()
        self.expanded = False
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setWindowFlags(Qt.WindowStaysOnTopHint)
        self.setWindowFlags(Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(100,100)
        

    def 