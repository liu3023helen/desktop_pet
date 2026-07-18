"""独立测试气泡组件 — 极简版"""
import sys
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt, QTimer
from bubble_widget import BubbleWidget

app = QApplication(sys.argv)

# 创建一个简单的红色方块作为"宠物"
pet = QWidget()
pet.setFixedSize(256, 256)
pet.setStyleSheet("background-color: rgba(255, 0, 0, 120);")
pet.setWindowTitle("Pet (red square)")
pet.move(400, 300)
# 无边框+置顶，模拟真实宠物窗口
pet.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
pet.setAttribute(Qt.WA_TranslucentBackground)

# 创建气泡
bubble = BubbleWidget(pet_window=pet)

pet.show()

print(f"pet.pos() = {pet.pos()}")
print(f"pet.geometry() = {pet.geometry()}")
print(f"bubble._pet_window = {bubble._pet_window}")

# 2秒后显示气泡
def show_it():
    print("\n--- Showing bubble ---")
    bubble.show_bubble("Hello! \u8fd9\u662f\u4e00\u4e2a\u6d4b\u8bd5\u6c14\u6ce1", duration_ms=8000)
    print(f"bubble.isVisible() = {bubble.isVisible()}")
    print(f"bubble.pos() = {bubble.pos()}")
    print(f"bubble.text() = {bubble.text()}")

QTimer.singleShot(2000, show_it)

print("\nTest window opened. Bubble should appear in 2 seconds.")
sys.exit(app.exec_())
