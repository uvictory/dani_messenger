import os
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = os.path.join(os.path.dirname(__file__), "platforms")

import sys
import asyncio
import websockets
import json
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QLabel, QDialog, QDialogButtonBox, QScrollArea, QFrame,
    QSizePolicy, QGraphicsDropShadowEffect  # 수정된 부분
)
from PyQt5.QtGui import QFont, QFontDatabase
from PyQt5.QtCore import Qt, QTimer, QPoint, QPropertyAnimation, QEasingCurve
from qasync import QEventLoop, asyncSlot


class NicknameDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("닉네임 입력")
        self.setFixedSize(300, 100)

        layout = QVBoxLayout()
        self.label = QLabel("닉네임을 입력하세요:")
        self.input = QLineEdit()
        self.input.setPlaceholderText("예: 홍길동")

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(self.label)
        layout.addWidget(self.input)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def get_nickname(self):
        if self.exec_() == QDialog.Accepted:
            return self.input.text()
        else:
            return None


class PopupNotification(QWidget):
    def __init__(self, title: str, message: str, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(300, 80)

        self.label = QLabel(f"{title}: {message}", self)
        self.label.setFixedSize(280, 60)
        self.label.setWordWrap(False)
        self.label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.label.setTextInteractionFlags(Qt.NoTextInteraction)
        self.label.setToolTip(f"{title}\n{message}")
        self.label.setStyleSheet("""
            QLabel {
                background-color: white;
                border-radius: 10px;
                padding: 10px;
                border: 1px solid #ccc;
                color: black;
            }
        """)

        screen = QApplication.primaryScreen().geometry()
        x = screen.width() - self.width() - 20
        y = screen.height() - self.height() - 60
        self.move(QPoint(x, y))

        self.setWindowOpacity(0.0)
        self.fade_in = QPropertyAnimation(self, b"windowOpacity")
        self.fade_in.setDuration(300)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.InOutQuad)
        self.fade_in.start()

        QTimer.singleShot(2500, self.close)


class ChatClient(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("✨ 내부 메신저")
        self.resize(420, 550)

        # Style for the window
        self.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
                border-radius: 15px;
            }
        """)

        # Set shadow effect for the main window
        shadow_effect = QGraphicsDropShadowEffect(self)  # 변경된 부분
        shadow_effect.setBlurRadius(20)
        shadow_effect.setOffset(0, 5)
        self.setGraphicsEffect(shadow_effect)

        self.server_url = "ws://192.168.1.12:8000/ws/"

        nickname_dialog = NicknameDialog()
        self.username = nickname_dialog.get_nickname()
        if not self.username:
            sys.exit()

        self.websocket = None

        font_path = os.path.join("fonts", "NanumSquareRound.ttf")
        if os.path.exists(font_path):
            QFontDatabase.addApplicationFont(font_path)
            self.setFont(QFont("NanumSquareRound", 10))
        else:
            self.setFont(QFont("Arial", 10))

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
        self.input_line.setPlaceholderText("메시지를 입력하세요...")
        self.send_button = QPushButton("전송")
        
        # Styling the input field and send button
        self.input_line.setStyleSheet("""
            QLineEdit {
                background-color: white;
                border-radius: 10px;
                padding: 8px;
                font-size: 14px;
            }
        """)

        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: #ffd700;
                border-radius: 10px;
                padding: 8px 20px;
                font-size: 14px;
                color: black;
            }
        """)

        input_layout.addWidget(self.input_line)
        input_layout.addWidget(self.send_button)

        self.layout.addLayout(input_layout)
        self.setLayout(self.layout)

        self.send_button.clicked.connect(self.send_message)
        self.input_line.returnPressed.connect(self.send_message)

    async def connect(self):
        try:
            self.websocket = await websockets.connect(self.server_url + self.username)
            self.add_message("✅ 서버에 연결되었습니다.", is_system=True)
            await self.receive_messages()
        except Exception as e:
            self.add_message(f"❌ 연결 실패: {e}", is_system=True)

    @asyncSlot()
    async def send_message(self):
        message = self.input_line.text().strip()
        if message and self.websocket:
            try:
                await self.websocket.send(message)
                self.add_message(message, from_self=True)
                self.input_line.clear()
            except Exception as e:
                self.add_message(f"❌ 전송 오류: {e}", is_system=True)

    async def receive_messages(self):
        try:
            async for raw in self.websocket:
                try:
                    packet = json.loads(raw)
                    sender = packet["sender"]
                    message = packet["message"]

                    if sender == self.username:
                        continue

                    self.add_message(f"{sender}: {message}", from_self=False)

                    popup = PopupNotification(sender, message)
                    popup.show()
                except Exception as e:
                    self.add_message(f"❌ 메시지 파싱 실패: {e}", is_system=True)
        except Exception as e:
            self.add_message(f"❌ 연결 종료: {e}", is_system=True)

    def add_message(self, text, from_self=False, is_system=False):
        time_str = datetime.now().strftime("%H:%M")

        bubble = QLabel()
        bubble.setTextFormat(Qt.PlainText)
        bubble.setText(text.strip())
        bubble.setWordWrap(True)
        bubble.setMaximumWidth(280)
        bubble.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        bubble.setStyleSheet(f"""
            background-color: {'#ffe400' if from_self else '#e0e0e0'};
            padding: 10px 14px;
            border-radius: 14px;
            color: black;
        """)

        bubble_frame = QFrame()
        layout = QHBoxLayout(bubble_frame)
        layout.setContentsMargins(10, 0, 10, 0)

        if is_system:
            bubble.setWordWrap(False)
            bubble.setAlignment(Qt.AlignCenter)
            bubble.setFixedWidth(300)
            bubble.setStyleSheet("color: gray; padding: 5px;")
            layout.addWidget(bubble, alignment=Qt.AlignCenter)
        else:
            time_label = QLabel(time_str)
            time_label.setStyleSheet("color: gray; font-size: 10px; margin: 2px;")

            bubble_container = QVBoxLayout()
            bubble_container.setSpacing(2)
            bubble_container.addWidget(bubble)
            bubble_container.addWidget(time_label, alignment=Qt.AlignRight if from_self else Qt.AlignLeft)

            inner = QWidget()
            inner.setLayout(bubble_container)

            if from_self:
                layout.addStretch()
                layout.addWidget(inner, alignment=Qt.AlignRight)
            else:
                layout.addWidget(inner, alignment=Qt.AlignLeft)
                layout.addStretch()

        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble_frame)
        QTimer.singleShot(10, self.scroll_to_bottom)

    def scroll_to_bottom(self):
        self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        )


def main():
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    client = ChatClient()
    client.show()

    with loop:
        loop.create_task(client.connect())
        loop.run_forever()


if __name__ == "__main__":
    main()
