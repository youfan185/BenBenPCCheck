from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel


class AIStatusIndicator(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(10, 10)
        self.setCursor(Qt.PointingHandCursor)
        self.set_status(False)

    def set_status(self, success: bool, tooltip: str = ""):
        color = "#34C759" if success else "#FF3B30"
        self.setStyleSheet(
            f"""
            QLabel {{
                background-color: {color};
                border-radius: 5px;
                border: 1px solid rgba(255,255,255,0.8);
            }}
            """
        )
        self.setToolTip(
            tooltip
            or (
                "gpt-5.5 分析成功，本页结果由 AI 生成"
                if success
                else "AI 分析未成功，本页结果为本地规则或未分析状态"
            )
        )
