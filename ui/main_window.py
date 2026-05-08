from datetime import datetime

from qt_bootstrap import configure_qt


configure_qt()

from PyQt5.QtCore import QPoint, QThread, Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config import AI_PROMPT_TEMPLATE
from core.cleaner import scan_cleanable_items
from core.diagnosis_engine import build_diagnosis
from core.disk_scanner import list_partitions, scan_common_folders
from core.hardware_info import get_cpu_info, get_memory_info, get_system_info
from core.process_monitor import high_usage_processes, top_processes
from core.report_generator import export_json, export_txt
from core.score_engine import calculate_score
from core.startup_manager import get_startup_items


class ScanWorker(QThread):
    progress = pyqtSignal(str)
    scan_finished = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def run(self):
        try:
            self.progress.emit("开始体检，正在初始化扫描环境...")
            self.progress.emit("读取系统版本、电脑名称和基础信息")
            system = get_system_info()

            self.progress.emit("检测 CPU 当前占用和核心数量")
            cpu = get_cpu_info()

            self.progress.emit("检测内存容量、可用空间和占用比例")
            mem = get_memory_info()

            self.progress.emit("读取磁盘分区容量，判断 C 盘空间风险")
            partitions = list_partitions()

            self.progress.emit("扫描常见大目录：桌面、下载、缓存、微信、QQ、Adobe")
            folders = scan_common_folders(self.progress.emit)

            self.progress.emit("扫描当前运行程序，筛选高 CPU / 高内存进程")
            process_rows = top_processes()
            process_summary = high_usage_processes(process_rows)

            self.progress.emit("读取注册表自启动项，生成启动项建议")
            startup_items = get_startup_items()

            self.progress.emit("扫描安全可清理项：Windows Temp、用户 Temp、回收站")
            cleanable = scan_cleanable_items(self.progress.emit)

            report = {
                "report_version": "1.0",
                "software_name": "BenBen PC Check",
                "software_version": "1.0.0",
                "scan_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "computer": system,
                "hardware": {"cpu": cpu, "memory": mem, "gpu": [], "disks": []},
                "disk_partitions": partitions,
                "large_folders": folders,
                "cleanable_items": cleanable,
                "process_list": process_rows,
                "processes": process_summary,
                "startup_items": {"total_count": len(startup_items), "items": startup_items},
            }

            self.progress.emit("计算本地评分，生成状态结论")
            score_pack = calculate_score(report)
            report["score"] = {
                "total_score": score_pack["total_score"],
                "level": score_pack["level"],
                "sub_scores": score_pack["sub_scores"],
            }
            report["ip_status"] = score_pack["ip_status"]

            self.progress.emit("应用本地诊断规则，整理主要问题和建议")
            report["diagnosis"] = build_diagnosis(report)

            self.progress.emit("体检完成，报告已生成到界面")
            self.scan_finished.emit(report)
        except Exception as exc:
            self.failed.emit(str(exc))


class StatCard(QFrame):
    def __init__(self, title: str, value: str = "--", note: str = "等待检测"):
        super().__init__()
        self.setObjectName("statCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)
        self.title = QLabel(title)
        self.title.setObjectName("cardTitle")
        self.value = QLabel(value)
        self.value.setObjectName("cardValue")
        self.note = QLabel(note)
        self.note.setObjectName("cardNote")
        self.note.setWordWrap(True)
        layout.addWidget(self.title)
        layout.addStretch(1)
        layout.addWidget(self.value)
        layout.addWidget(self.note)

    def set_data(self, value: str, note: str = ""):
        self.value.setText(value)
        self.note.setText(note)


class MetricPanel(QFrame):
    def __init__(self, title: str):
        super().__init__()
        self.setObjectName("panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        self.heading = QLabel(title)
        self.heading.setObjectName("panelTitle")
        layout.addWidget(self.heading)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("BenBen 电脑体检助手")
        self.resize(1320, 820)
        self.current_report = None
        self.worker = None
        self._drag_pos = QPoint()

        outer = QWidget()
        outer.setObjectName("outer")
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(12, 12, 12, 12)
        self.setCentralWidget(outer)

        self.shell = QFrame()
        self.shell.setObjectName("shell")
        shadow = QGraphicsDropShadowEffect(self.shell)
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, 18)
        self.shell.setGraphicsEffect(shadow)
        outer_layout.addWidget(self.shell)

        root_layout = QVBoxLayout(self.shell)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.top_bar = self._build_top_bar()
        root_layout.addWidget(self.top_bar)

        body = QWidget()
        body.setObjectName("body")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        root_layout.addWidget(body, 1)

        self.menu = QListWidget()
        self.menu.setObjectName("sidebar")
        self.menu.setFixedWidth(220)
        for text in ["体检概览", "硬件信息", "运行程序", "空间分析", "自启动管理", "AI 分析报告"]:
            QListWidgetItem(text, self.menu)
        body_layout.addWidget(self.menu)

        self.stack = QStackedWidget()
        self.stack.setObjectName("stack")
        body_layout.addWidget(self.stack, 1)

        self.home_page = self._build_home_page()
        self.hardware_page, self.hardware_table = self._build_table_page("硬件信息", "系统、CPU、内存与基础硬件状态")
        self.process_page, self.process_table = self._build_table_page("运行程序", "按资源占用排序，快速发现可疑进程")
        self.disk_page, self.disk_table = self._build_table_page("空间分析", "磁盘分区、常见大目录与缓存占用")
        self.startup_page, self.startup_table = self._build_table_page("自启动管理", "开机启动项与保留/禁用建议")
        self.ai_page = self._build_ai_page()

        for page in [
            self.home_page,
            self.hardware_page,
            self.process_page,
            self.disk_page,
            self.startup_page,
            self.ai_page,
        ]:
            self.stack.addWidget(page)

        self.menu.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.menu.setCurrentRow(0)
        self.setStyleSheet(APP_QSS)

    def _build_top_bar(self):
        top = QFrame()
        top.setObjectName("topBar")
        layout = QHBoxLayout(top)
        layout.setContentsMargins(18, 0, 14, 0)
        layout.setSpacing(10)

        logo = QLabel("BB")
        logo.setObjectName("logo")
        title = QLabel("BenBenPCCheck")
        title.setObjectName("appName")
        caption = QLabel("电脑体检助手")
        caption.setObjectName("appCaption")

        close_btn = QPushButton("")
        close_btn.setObjectName("closeDot")
        close_btn.setFixedSize(13, 13)
        close_btn.clicked.connect(self.close)
        min_btn = QPushButton("")
        min_btn.setObjectName("minDot")
        min_btn.setFixedSize(13, 13)
        min_btn.clicked.connect(self.showMinimized)

        layout.addWidget(close_btn)
        layout.addWidget(min_btn)
        layout.addSpacing(6)
        layout.addWidget(logo)
        layout.addWidget(title)
        layout.addWidget(caption)
        layout.addStretch(1)

        self.header_status = QLabel("待体检")
        self.header_status.setObjectName("headerStatus")
        layout.addWidget(self.header_status)
        return top

    def _build_home_page(self):
        page = QWidget()
        page.setObjectName("page")
        v = QVBoxLayout(page)
        v.setContentsMargins(24, 22, 24, 24)
        v.setSpacing(16)

        hero = QFrame()
        hero.setObjectName("hero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(28, 26, 28, 26)
        hero_layout.setSpacing(24)

        left = QVBoxLayout()
        left.setSpacing(12)
        self.status_kicker = QLabel("SYSTEM HEALTH")
        self.status_kicker.setObjectName("kicker")
        self.status_title = QLabel("准备开始体检")
        self.status_title.setObjectName("heroTitle")
        self.status_subtitle = QLabel("点击一键体检，扫描过程会在右侧实时输出。")
        self.status_subtitle.setObjectName("heroSub")
        self.scan_btn = QPushButton("一键体检")
        self.scan_btn.setObjectName("primaryButton")
        self.scan_btn.clicked.connect(self.run_scan)
        left.addWidget(self.status_kicker)
        left.addWidget(self.status_title)
        left.addWidget(self.status_subtitle)
        left.addStretch(1)
        left.addWidget(self.scan_btn, 0, Qt.AlignLeft)

        score_panel = QFrame()
        score_panel.setObjectName("scorePanel")
        score_layout = QVBoxLayout(score_panel)
        score_layout.setContentsMargins(22, 20, 22, 20)
        self.score_label = QLabel("--")
        self.score_label.setObjectName("score")
        self.score_note = QLabel("综合评分")
        self.score_note.setObjectName("scoreNote")
        self.score_bar = QProgressBar()
        self.score_bar.setObjectName("scoreBar")
        self.score_bar.setRange(0, 100)
        self.score_bar.setValue(0)
        score_layout.addWidget(self.score_note)
        score_layout.addWidget(self.score_label)
        score_layout.addWidget(self.score_bar)

        hero_layout.addLayout(left, 1)
        hero_layout.addWidget(score_panel)
        v.addWidget(hero)

        cards = QGridLayout()
        cards.setSpacing(12)
        self.cpu_card = StatCard("CPU", "--", "等待检测")
        self.mem_card = StatCard("内存", "--", "等待检测")
        self.disk_card = StatCard("磁盘 C:", "--", "等待检测")
        self.process_card = StatCard("高占用程序", "--", "等待检测")
        self.startup_card = StatCard("启动项", "--", "等待检测")
        self.clean_card = StatCard("可清理空间", "--", "等待检测")
        for index, card in enumerate(
            [self.cpu_card, self.mem_card, self.disk_card, self.process_card, self.startup_card, self.clean_card]
        ):
            cards.addWidget(card, index // 3, index % 3)
        v.addLayout(cards)

        bottom = QGridLayout()
        bottom.setSpacing(12)
        issues_panel = MetricPanel("主要问题")
        issues_panel.layout().addWidget(self._make_text_panel("issue_view", "体检后会显示优先处理项"))
        progress_panel = MetricPanel("体检过程")
        progress_panel.layout().addWidget(self._make_text_panel("progress_view", "扫描过程会持续输出在这里"))
        bottom.addWidget(issues_panel, 0, 0)
        bottom.addWidget(progress_panel, 0, 1)
        v.addLayout(bottom, 1)
        return page

    def _make_text_panel(self, attr_name: str, placeholder: str):
        text = QTextEdit()
        text.setObjectName("panelText")
        text.setReadOnly(True)
        text.setPlaceholderText(placeholder)
        setattr(self, attr_name, text)
        return text

    def _build_table_page(self, title: str, subtitle: str):
        page = QWidget()
        page.setObjectName("page")
        v = QVBoxLayout(page)
        v.setContentsMargins(24, 22, 24, 24)
        v.setSpacing(14)

        header = QVBoxLayout()
        label = QLabel(title)
        label.setObjectName("pageTitle")
        sub = QLabel(subtitle)
        sub.setObjectName("pageSub")
        header.addWidget(label)
        header.addWidget(sub)

        table = QTableWidget()
        table.setObjectName("dataTable")
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setShowGrid(False)
        v.addLayout(header)
        v.addWidget(table, 1)
        return page, table

    def _build_ai_page(self):
        page = QWidget()
        page.setObjectName("page")
        v = QVBoxLayout(page)
        v.setContentsMargins(24, 22, 24, 24)
        v.setSpacing(14)

        title = QLabel("AI 分析报告")
        title.setObjectName("pageTitle")
        sub = QLabel("导出报告或复制固定模板，交给 AI 做进一步分析。")
        sub.setObjectName("pageSub")
        actions = QHBoxLayout()
        export_json_btn = QPushButton("导出 JSON")
        export_txt_btn = QPushButton("导出 TXT")
        copy_btn = QPushButton("复制 AI 模板")
        export_json_btn.clicked.connect(self.on_export_json)
        export_txt_btn.clicked.connect(self.on_export_txt)
        copy_btn.clicked.connect(self.on_copy_prompt)
        actions.addWidget(export_json_btn)
        actions.addWidget(export_txt_btn)
        actions.addWidget(copy_btn)
        actions.addStretch(1)

        self.ai_prompt_view = QTextEdit()
        self.ai_prompt_view.setObjectName("panelTextLarge")
        self.ai_prompt_view.setReadOnly(True)
        self.ai_prompt_view.setPlainText(AI_PROMPT_TEMPLATE)
        v.addWidget(title)
        v.addWidget(sub)
        v.addLayout(actions)
        v.addWidget(self.ai_prompt_view, 1)
        return page

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.pos().y() <= 64:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and not self._drag_pos.isNull():
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = QPoint()
        event.accept()

    def run_scan(self):
        if self.worker and self.worker.isRunning():
            return
        self.progress_view.clear()
        self.issue_view.clear()
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText("体检中...")
        self.status_kicker.setText("SCANNING")
        self.status_title.setText("正在体检中")
        self.status_subtitle.setText("你可以继续操作窗口，扫描结果会逐步写入界面。")
        self.header_status.setText("扫描中")

        self.worker = ScanWorker()
        self.worker.progress.connect(self.append_progress)
        self.worker.scan_finished.connect(self.on_scan_finished)
        self.worker.failed.connect(self.on_scan_failed)
        self.worker.start()

    def append_progress(self, text: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.progress_view.append(f"[{timestamp}] {text}")

    def on_scan_finished(self, report: dict):
        self.current_report = report
        self._refresh_views(report)
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText("重新体检")
        self.header_status.setText("体检完成")

    def on_scan_failed(self, message: str):
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText("重新体检")
        self.header_status.setText("体检失败")
        self.append_progress(f"体检失败：{message}")
        QMessageBox.critical(self, "体检失败", message)

    def _refresh_views(self, report: dict):
        score = report.get("score", {})
        ip = report.get("ip_status", {})
        cpu = report.get("hardware", {}).get("cpu", {})
        mem = report.get("hardware", {}).get("memory", {})
        processes = report.get("processes", {})
        c_drive = next((d for d in report.get("disk_partitions", []) if str(d.get("drive", "")).upper().startswith("C:")), None)
        high_count = len(processes.get("high_cpu_processes", [])) + len(processes.get("high_memory_processes", []))
        cleanable_size = sum(i.get("size_gb", 0) for i in report.get("cleanable_items", []))
        startup_count = report.get("startup_items", {}).get("total_count", 0)
        total_score = score.get("total_score", 0)

        self.score_label.setText(str(total_score))
        self.score_bar.setValue(int(total_score))
        self.status_kicker.setText("SCAN COMPLETE")
        self.status_title.setText(f"电脑状态：{ip.get('display_name', '已体检')}")
        self.status_subtitle.setText(ip.get("message", "体检完成"))
        self.cpu_card.set_data(f"{cpu.get('current_usage_percent', 0)}%", f"{cpu.get('physical_cores', 0)} 核 / {cpu.get('logical_cores', 0)} 线程")
        self.mem_card.set_data(f"{mem.get('usage_percent', 0)}%", f"已用 {mem.get('used_gb', 0)} / {mem.get('total_gb', 0)} GB")
        if c_drive:
            self.disk_card.set_data(f"{c_drive.get('usage_percent', 0)}%", f"剩余 {c_drive.get('free_gb', 0)} GB")
        self.process_card.set_data(str(high_count), "CPU >30% 或内存 >2GB")
        self.startup_card.set_data(str(startup_count), "开机自启动项")
        self.clean_card.set_data(f"{round(cleanable_size, 1)} GB", "安全可清理项")

        issues = report.get("diagnosis", {}).get("main_issues", [])
        if issues:
            self.issue_view.setPlainText("\n".join(f"{i}. {x['title']}：{x['detail']}" for i, x in enumerate(issues, 1)))
        else:
            self.issue_view.setPlainText("暂未发现明显问题。")

        self._fill_table(self.hardware_table, ["项目", "内容"], self._hardware_rows(report))
        self._fill_table(self.process_table, ["程序", "PID", "CPU", "内存", "路径"], self._process_rows(report))
        self._fill_table(self.disk_table, ["名称", "路径/盘符", "容量/大小", "状态"], self._disk_rows(report))
        self._fill_table(self.startup_table, ["名称", "来源", "建议", "路径"], self._startup_rows(report))

    def _hardware_rows(self, report: dict):
        computer = report.get("computer", {})
        cpu = report.get("hardware", {}).get("cpu", {})
        mem = report.get("hardware", {}).get("memory", {})
        return [
            ["电脑名称", computer.get("computer_name", "")],
            ["系统", f"{computer.get('os_name', '')} {computer.get('system_type', '')}"],
            ["CPU", cpu.get("name", "")],
            ["核心/线程", f"{cpu.get('physical_cores', 0)} / {cpu.get('logical_cores', 0)}"],
            ["内存", f"{mem.get('total_gb', 0)} GB，占用 {mem.get('usage_percent', 0)}%"],
        ]

    def _process_rows(self, report: dict):
        rows = []
        for item in report.get("process_list", [])[:80]:
            rows.append([
                item.get("name", ""),
                item.get("pid", ""),
                f"{item.get('cpu_percent', 0)}%",
                f"{item.get('memory_mb', 0)} MB",
                item.get("path", ""),
            ])
        return rows

    def _disk_rows(self, report: dict):
        rows = []
        for item in report.get("disk_partitions", []):
            rows.append([
                "磁盘分区",
                item.get("drive", ""),
                f"{item.get('used_gb', 0)} / {item.get('total_gb', 0)} GB",
                f"剩余 {item.get('free_gb', 0)} GB，{item.get('risk_level', '')}",
            ])
        for item in report.get("large_folders", [])[:30]:
            rows.append([
                item.get("name", ""),
                item.get("path", ""),
                f"{item.get('size_gb', 0)} GB",
                item.get("suggestion", ""),
            ])
        return rows

    def _startup_rows(self, report: dict):
        return [
            [item.get("name", ""), item.get("source", ""), item.get("recommendation", ""), item.get("path", "")]
            for item in report.get("startup_items", {}).get("items", [])
        ]

    def _fill_table(self, table: QTableWidget, headers: list[str], rows: list[list[object]]):
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for col_index, value in enumerate(row):
                table.setItem(row_index, col_index, QTableWidgetItem(str(value)))

    def _require_report(self) -> bool:
        if not self.current_report:
            QMessageBox.warning(self, "提示", "请先执行一次体检")
            return False
        return True

    def on_export_json(self):
        if not self._require_report():
            return
        path = export_json(self.current_report)
        QMessageBox.information(self, "导出成功", f"JSON 已导出:\n{path}")

    def on_export_txt(self):
        if not self._require_report():
            return
        path = export_txt(self.current_report)
        QMessageBox.information(self, "导出成功", f"TXT 已导出:\n{path}")

    def on_copy_prompt(self):
        QApplication.clipboard().setText(AI_PROMPT_TEMPLATE)
        QMessageBox.information(self, "已复制", "AI 分析模板已复制到剪贴板")


def run_app():
    app = QApplication([])
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    app.exec_()


APP_QSS = """
QWidget#outer {
    background: transparent;
    font-family: "Microsoft YaHei UI", "Microsoft YaHei";
}
QFrame#shell {
    background: #050507;
    border: 1px solid #1d1d22;
    border-radius: 24px;
}
QFrame#topBar {
    background: #08080b;
    border-top-left-radius: 24px;
    border-top-right-radius: 24px;
    min-height: 56px;
    max-height: 56px;
}
QWidget#body, QStackedWidget#stack, QWidget#page {
    background: #050507;
    color: #f5f5f7;
}
QPushButton#closeDot {
    background: #ff5f57;
    border: none;
    border-radius: 6px;
}
QPushButton#minDot {
    background: #febc2e;
    border: none;
    border-radius: 6px;
}
QLabel#logo {
    background: #f5c94b;
    color: #0a0a0c;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 800;
    min-width: 34px;
    min-height: 30px;
    qproperty-alignment: AlignCenter;
}
QLabel#appName {
    color: #f5f5f7;
    font-size: 16px;
    font-weight: 700;
}
QLabel#appCaption, QLabel#headerStatus {
    color: #8e8e93;
    font-size: 13px;
}
QLabel#headerStatus {
    background: #141418;
    border: 1px solid #24242a;
    border-radius: 12px;
    padding: 7px 14px;
}
QListWidget#sidebar {
    background: #09090c;
    border: none;
    border-right: 1px solid #17171c;
    padding: 18px 12px 18px 14px;
    color: #a1a1aa;
    outline: none;
}
QListWidget#sidebar::item {
    height: 46px;
    padding-left: 18px;
    border-radius: 12px;
    margin: 2px 0;
}
QListWidget#sidebar::item:hover {
    background: #15151a;
    color: #ffffff;
}
QListWidget#sidebar::item:selected {
    background: #f5f5f7;
    color: #09090c;
    font-weight: 700;
}
QFrame#hero {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #16161c, stop:1 #0d0d11);
    border: 1px solid #27272f;
    border-radius: 22px;
}
QLabel#kicker {
    color: #9ca3af;
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 0px;
}
QLabel#heroTitle {
    color: #ffffff;
    font-size: 36px;
    font-weight: 800;
}
QLabel#heroSub, QLabel#pageSub, QLabel#cardNote {
    color: #9b9ba3;
    font-size: 14px;
}
QFrame#scorePanel {
    background: #0f0f14;
    border: 1px solid #2a2a31;
    border-radius: 20px;
    min-width: 210px;
}
QLabel#score {
    color: #ffffff;
    font-size: 64px;
    font-weight: 900;
}
QLabel#scoreNote {
    color: #9b9ba3;
    font-size: 13px;
}
QProgressBar#scoreBar {
    background: #222228;
    border: none;
    border-radius: 5px;
    height: 10px;
}
QProgressBar#scoreBar::chunk {
    background: #34c759;
    border-radius: 5px;
}
QFrame#statCard, QFrame#panel, QTextEdit#panelTextLarge, QTableWidget#dataTable {
    background: #101014;
    border: 1px solid #25252c;
    border-radius: 18px;
}
QFrame#statCard:hover {
    border: 1px solid #3a3a44;
    background: #131318;
}
QLabel#cardTitle {
    color: #9b9ba3;
    font-size: 13px;
}
QLabel#cardValue {
    color: #ffffff;
    font-size: 32px;
    font-weight: 850;
}
QLabel#panelTitle {
    color: #f5f5f7;
    font-size: 16px;
    font-weight: 750;
}
QLabel#pageTitle {
    color: #f5f5f7;
    font-size: 28px;
    font-weight: 850;
}
QPushButton {
    background: #1c1c22;
    color: #f5f5f7;
    border: 1px solid #303038;
    border-radius: 12px;
    padding: 10px 18px;
    font-weight: 650;
}
QPushButton:hover {
    background: #2a2a32;
}
QPushButton#primaryButton {
    background: #ffffff;
    color: #08080b;
    border: none;
    padding: 12px 28px;
}
QPushButton#primaryButton:hover {
    background: #e7e7ea;
}
QPushButton:disabled {
    background: #1a1a1f;
    color: #77777f;
}
QTextEdit#panelText, QTextEdit#panelTextLarge {
    background: #0b0b0e;
    border: 1px solid #202027;
    border-radius: 14px;
    color: #e8e8ed;
    padding: 12px;
    selection-background-color: #3a3a42;
}
QTextEdit#panelText {
    min-height: 190px;
}
QTableWidget#dataTable {
    color: #f5f5f7;
    alternate-background-color: #0b0b0e;
    selection-background-color: #2c2c34;
    gridline-color: transparent;
    padding: 8px;
}
QHeaderView::section {
    background: #17171c;
    color: #a1a1aa;
    border: none;
    border-radius: 8px;
    padding: 11px;
    font-weight: 700;
}
QScrollBar:vertical {
    background: transparent;
    width: 10px;
}
QScrollBar::handle:vertical {
    background: #2f2f37;
    border-radius: 5px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
"""


if __name__ == "__main__":
    run_app()
