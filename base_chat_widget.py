# base_chat_widget.py
import os, json, base64, asyncio
from datetime import datetime
from io import BytesIO
from PIL import Image
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QScrollArea, QFrame, QSizePolicy, QFileDialog
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt, QTimer

class BaseChatWidget(QWidget):
    def __init__(self, username, websocket=None, peer=None):
        super().__init__()
        self.username = username
        self.websocket = websocket
        self.peer = peer  # 개인 채팅용 상대방 이름
        self.profile_image = None
        self.message_map = {}
        self.thinking_timers = {}

        self._init_ui()

    def _init_ui(self):
        self.layout = QVBoxLayout()

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.chat_layout = QVBoxLayout(self.scroll_content)
        self.chat_layout.setSpacing(0)
        self.chat_layout.addStretch(1)
        self.scroll_area.setWidget(self.scroll_content)
        self.layout.addWidget(self.scroll_area)

        input_layout = QHBoxLayout()
        self.input_line = QLineEdit()
        self.send_button = QPushButton("전송")

        input_layout.addWidget(self.input_line)
        input_layout.addWidget(self.send_button)
        self.layout.addLayout(input_layout)
        self.setLayout(self.layout)

        self.send_button.clicked.connect(self.send_message)
        self.input_line.returnPressed.connect(self.send_message)

    async def send_message(self):
        message = self.input_line.text().strip()
        if message and self.websocket:
            packet = {
                "sender": self.username,
                "message": message,
                "profile": self.profile_image
            }

            if self.peer:
                packet["type"] = "private_room"
                packet["receiver"] = self.peer

            await self.websocket.send(json.dumps(packet))
            self.add_message(self.username, message, from_self=True, profile=self.profile_image)
            self.input_line.clear()

    def add_message(self, sender, text, from_self=False, profile=None):
        time_str = datetime.now().strftime("%H:%M")
        bubble = QLabel(text.strip())
        bubble.setWordWrap(True)
        bubble.setMaximumWidth(340)
        bubble.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        bubble.setStyleSheet(f"""
            background-color: {'#FFCF71' if from_self else '#ffffff'};
            padding: 8px 10px;
            border-radius: 14px;
            color: black;
        """)

        time_label = QLabel(time_str)
        time_label.setStyleSheet("color: gray; font-size: 10px; margin: 1px;")

        bubble_container = QVBoxLayout()
        bubble_container.addWidget(bubble)
        bubble_container.addWidget(time_label, alignment=Qt.AlignRight if from_self else Qt.AlignLeft)

        profile_label = QLabel()
        profile_label.setFixedSize(36, 36)
        pixmap = QPixmap(os.path.join(os.path.dirname(__file__), "images/face.png"))
        if profile:
            try:
                pixmap.loadFromData(base64.b64decode(profile))
            except:
                pass
        profile_label.setPixmap(pixmap.scaled(36, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        frame = QFrame()
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 4, 10, 4)

        if from_self:
            layout.addStretch()
            layout.addLayout(bubble_container)
            layout.addWidget(profile_label)
        else:
            layout.addWidget(profile_label)
            layout.addLayout(bubble_container)
            layout.addStretch()

        self.chat_layout.insertWidget(self.chat_layout.count() - 1, frame)
        QTimer.singleShot(10, self.scroll_to_bottom)

    def scroll_to_bottom(self):
        scroll_bar = self.scroll_area.verticalScrollBar()
        if scroll_bar:
            scroll_bar.setValue(scroll_bar.maximum())
