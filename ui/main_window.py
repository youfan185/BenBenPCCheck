from datetime import datetime
from pathlib import Path

from qt_bootstrap import configure_qt


configure_qt()

from PyQt5.QtCore import QPoint, QThread, QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QIcon, QPixmap
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
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config import AI_PROMPT_TEMPLATE
from core.ai_analysis_service import analyze_report_with_ai
from core.ai_prompt_builder import build_ai_prompt
from core.ai_result_parser import build_local_ai_result, emotion_key
from core.cleaner import scan_cleanable_items
from core.diagnosis_engine import build_diagnosis
from core.disk_health import scan_disk_health
from core.disk_scanner import list_partitions, scan_common_folders
from core.gpu_info import get_gpu_info
from core.hardware_info import get_cpu_info, get_memory_info, get_system_info
from core.installed_software import scan_installed_software
from core.process_grouper import group_processes
from core.process_monitor import high_usage_processes, top_processes
from core.product_insights import build_product_insights
from core.report_schema import apply_v2_schema
from core.report_generator import export_json, export_txt
from core.risk_scanner import scan_stability_risk
from core.score_engine import calculate_score
from core.software_usage_tracker import build_user_software_profile, update_software_usage
from core.startup_manager import get_startup_items
from core.windows_settings_scanner import scan_windows_settings
from ui.ai_status_indicator import AIStatusIndicator


SCORE_CARD_META = [
    ("hardware_market_score", "硬件市场水平", "硬件在当前市场中的档次"),
    ("software_smoothness_score", "软件运行流畅度", "运行此电脑软件是否流畅"),
    ("system_usability_score", "系统可用性", "空间、缓存、后台、自启动是否拖后腿"),
]

DETAIL_DIMENSION_META = [
    ("space", "空间", "C 盘、缓存、大文件"),
    ("hardware", "硬件", "CPU、内存、显卡、硬盘"),
    ("common_software", "常用软件", "真实常用软件适配"),
    ("system_background", "后台自启", "进程和开机启动项"),
    ("windows_settings", "Windows 设置", "电源、更新、索引、同步"),
    ("stability_risk", "稳定风险", "运行时长、风险和日志"),
]


class ScanWorker(QThread):
    progress = pyqtSignal(str)
    scan_finished = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def run(self):
        try:
            self.progress.emit("开始一键扫描，先读取系统基础信息。")
            system = get_system_info()
            cpu = get_cpu_info()
            mem = get_memory_info()

            self.progress.emit("读取磁盘分区、C 盘剩余空间和常见大目录。")
            partitions = list_partitions()
            folders = scan_common_folders(self.progress.emit)
            cleanable = scan_cleanable_items(self.progress.emit)

            self.progress.emit("读取显卡信息，优先使用 nvidia-smi / PowerShell / WMIC。")
            gpu_rows, gpu_status = get_gpu_info()

            self.progress.emit("扫描当前进程、启动项和已安装软件。")
            process_rows = top_processes()
            process_groups = group_processes(process_rows)
            process_summary = high_usage_processes(process_rows)
            startup_items = get_startup_items()
            installed_software = scan_installed_software()

            scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.progress.emit("根据正在运行、已安装、启动项和历史记录生成常用软件画像。")
            software_usage = update_software_usage(process_rows, scan_time)
            software_profile = build_user_software_profile(process_rows, installed_software, startup_items, software_usage)

            self.progress.emit("检查 Windows 常见设置和轻量稳定性风险。")
            windows_settings = scan_windows_settings()
            stability_risk = scan_stability_risk(startup_items)
            disk_health = scan_disk_health()

            report = {
                "report_version": "2.0",
                "software_name": "BenBen AI 电脑诊断助手",
                "software_version": "2.0.0",
                "scan_time": scan_time,
                "computer": system,
                "hardware": {"cpu": cpu, "memory": mem, "gpu": gpu_rows, "disks": disk_health},
                "gpu_status": gpu_status,
                "disk_health": disk_health,
                "disk_partitions": partitions,
                "large_folders": folders,
                "cleanable_items": cleanable,
                "process_list": process_rows,
                "process_groups": process_groups,
                "processes": process_summary,
                "startup_items": {"total_count": len(startup_items), "items": startup_items},
                "installed_software": installed_software,
                "software_usage": software_usage,
                "user_software_profile": software_profile,
                "windows_settings": windows_settings,
                "stability_risk": stability_risk,
            }

            self.progress.emit("计算硬件状态、常用软件适配、系统可用性三大评分。")
            score_pack = calculate_score(report)
            report = apply_v2_schema(report, score_pack["hardware_score"], score_pack["system_usability_score"])
            report["score"] = {
                "total_score": score_pack["total_score"],
                "health_score": score_pack["health_score"],
                "optimization_score": score_pack["optimization_score"],
                "level": score_pack["level"],
                "display_level": score_pack["display_level"],
                "sub_scores": score_pack["sub_scores"],
                "hardware_score": score_pack["hardware_score"],
                "software_fit_score": report["scores"]["software_fit_score"],
                "system_usability_score": score_pack["system_usability_score"],
            }
            report["ip_status"] = score_pack["ip_status"]
            report["diagnosis"] = build_diagnosis(report)
            report["product"] = build_product_insights(report)
            report["six_dimensions"] = report["product"].get("six_dimensions", {})
            report["current_emotion"] = report["product"].get("current_emotion", {})
            report["top3_experience_issues"] = report["product"].get("top3_experience_issues", [])

            self.progress.emit("扫描完成，报告已生成。")
            self.scan_finished.emit(report)
        except Exception as exc:
            self.failed.emit(str(exc))


class AiWorker(QThread):
    progress = pyqtSignal(str)
    analysis_finished = pyqtSignal(dict)

    def __init__(self, report: dict):
        super().__init__()
        self.report = report

    def run(self):
        self.progress.emit("正在分析硬件是否需要升级...")
        self.progress.emit("正在评估硬件市场水平...")
        self.progress.emit("正在判断软件运行流畅度...")
        self.progress.emit("正在检查系统环境是否拖后腿...")
        self.progress.emit("正在生成优化引导...")
        analyze_report_with_ai(self.report, self.progress.emit)
        self.analysis_finished.emit(self.report)


class DimensionCard(QFrame):
    def __init__(self, title: str, note: str):
        super().__init__()
        self.setObjectName("dimensionCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        self.emotion = QLabel()
        self.emotion.setObjectName("cardEmotion")
        self.emotion.setFixedSize(54, 54)
        self.title = QLabel(title)
        self.title.setObjectName("cardTitle")
        self.score = QLabel("--")
        self.score.setObjectName("cardScore")
        self.status = QLabel("等待扫描")
        self.status.setObjectName("cardStatus")
        self.summary = QLabel(note)
        self.summary.setObjectName("cardSummary")
        self.summary.setWordWrap(True)
        head = QHBoxLayout()
        head.addWidget(self.title)
        head.addStretch(1)
        head.addWidget(self.emotion)
        layout.addLayout(head)
        layout.addWidget(self.score)
        layout.addWidget(self.status)
        layout.addWidget(self.summary, 1)
        self.set_data({"score": 0, "status": "等待扫描", "summary": note})

    def set_data(self, data: dict):
        self.score.setText(f"{data.get('score', '--')} 分")
        self.status.setText(data.get("status", "等待扫描"))
        self.summary.setText(data.get("summary", ""))
        self._set_emotion(data.get("emotion") or emotion_key(data.get("score", 0)))

    def _set_emotion(self, key: str):
        path = Path(__file__).resolve().parents[1] / "assets" / "emotion" / f"{key}.png"
        pixmap = QPixmap(str(path))
        if not pixmap.isNull():
            self.emotion.setPixmap(pixmap.scaled(54, 54, Qt.KeepAspectRatio, Qt.SmoothTransformation))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("YIDIS 伊迪斯设备检测")
        self.setWindowIcon(QIcon(str(Path(__file__).resolve().parents[1] / "assets" / "app_icon.ico")))
        self.resize(1280, 820)
        self.current_report = None
        self.current_ai_status = {"success": False, "source": "none", "message": "尚未进行 AI 分析"}
        self.worker = None
        self.ai_worker = None
        self._drag_pos = QPoint()

        outer = QWidget()
        outer.setObjectName("outer")
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(12, 12, 12, 12)
        self.setCentralWidget(outer)

        shell = QFrame()
        shell.setObjectName("shell")
        shadow = QGraphicsDropShadowEffect(shell)
        shadow.setBlurRadius(34)
        shadow.setColor(QColor(0, 0, 0, 140))
        shadow.setOffset(0, 14)
        shell.setGraphicsEffect(shadow)
        outer_layout.addWidget(shell)

        root = QVBoxLayout(shell)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_top_bar())

        body = QWidget()
        body.setObjectName("body")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        root.addWidget(body, 1)

        self.menu = QListWidget()
        self.menu.setObjectName("sidebar")
        self.menu.setFixedWidth(190)
        for text in ["首页", "扫描分析", "硬件详情", "软件流畅度", "系统详情", "简版报告", "优化引导", "历史记录", "设置"]:
            QListWidgetItem(text, self.menu)
        body_layout.addWidget(self.menu)

        self.stack = QStackedWidget()
        body_layout.addWidget(self.stack, 1)
        self.home_page = self._build_home_page()
        self.process_page = self._build_process_page()
        self.hardware_page = self._build_hardware_page()
        self.software_page = self._build_software_page()
        self.system_page = self._build_system_page()
        self.brief_page = self._build_brief_page()
        self.ai_page = self._build_ai_page()
        self.history_page = self._build_history_page()
        self.settings_page = self._build_settings_page()
        for page in [self.home_page, self.process_page, self.hardware_page, self.software_page, self.system_page, self.brief_page, self.ai_page, self.history_page, self.settings_page]:
            self.stack.addWidget(page)
        self.menu.currentRowChanged.connect(self.stack.setCurrentIndex)
        self._set_stage("loading")
        self.menu.setCurrentRow(1)
        QTimer.singleShot(1000, lambda: self.menu.setCurrentRow(0))
        self.setStyleSheet(APP_QSS)

    def _build_top_bar(self) -> QWidget:
        top = QFrame()
        top.setObjectName("topBar")
        layout = QHBoxLayout(top)
        layout.setContentsMargins(16, 0, 14, 0)
        layout.setSpacing(10)

        close_btn = QPushButton("")
        close_btn.setObjectName("closeDot")
        close_btn.setFixedSize(13, 13)
        close_btn.clicked.connect(self.close)
        min_btn = QPushButton("")
        min_btn.setObjectName("minDot")
        min_btn.setFixedSize(13, 13)
        min_btn.clicked.connect(self.showMinimized)
        logo = QLabel("YD")
        logo.setObjectName("logo")
        title = QLabel("YIDIS 伊迪斯设备检测")
        title.setObjectName("appName")
        caption = QLabel("AI Security Inspection")
        caption.setObjectName("appCaption")
        self.header_status = QLabel("等待扫描")
        self.header_status.setObjectName("headerStatus")
        self.ai_status_indicator = AIStatusIndicator()

        layout.addWidget(close_btn)
        layout.addWidget(min_btn)
        layout.addSpacing(6)
        layout.addWidget(logo)
        layout.addWidget(title)
        layout.addWidget(caption)
        layout.addStretch(1)
        layout.addWidget(self.ai_status_indicator)
        layout.addWidget(self.header_status)
        return top

    def _build_home_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(16)

        hero = QFrame()
        hero.setObjectName("hero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(26, 24, 26, 24)
        hero_layout.setSpacing(24)

        left = QVBoxLayout()
        left.setSpacing(10)
        self.status_title = QLabel("等待扫描")
        self.status_title.setObjectName("heroTitle")
        self.status_subtitle = QLabel("点击一键体检，判断硬件、常用软件和系统环境。")
        self.status_subtitle.setObjectName("heroSub")
        self.last_scan_label = QLabel("最近扫描：暂无")
        self.last_scan_label.setObjectName("muted")
        self.scan_btn = QPushButton("一键体检")
        self.scan_btn.setObjectName("primaryButton")
        self.scan_btn.clicked.connect(self.run_scan)
        brief_btn = QPushButton("查看简版报告")
        brief_btn.setObjectName("secondaryAction")
        brief_btn.clicked.connect(lambda: self.menu.setCurrentRow(5))
        ai_btn = QPushButton("查看优化引导")
        ai_btn.setObjectName("secondaryAction")
        ai_btn.clicked.connect(lambda: self.menu.setCurrentRow(6))
        button_row = QHBoxLayout()
        button_row.addWidget(self.scan_btn)
        button_row.addWidget(brief_btn)
        button_row.addWidget(ai_btn)
        button_row.addStretch(1)
        left.addWidget(self.status_title)
        left.addWidget(self.status_subtitle)
        left.addWidget(self.last_scan_label)
        left.addStretch(1)
        left.addLayout(button_row)

        score_panel = QFrame()
        score_panel.setObjectName("scorePanel")
        score_layout = QHBoxLayout(score_panel)
        score_layout.setContentsMargins(18, 18, 18, 18)
        score_layout.setSpacing(18)
        self.emotion_image = QLabel()
        self.emotion_image.setObjectName("emotionImage")
        self.emotion_image.setFixedSize(128, 128)
        self._set_emotion_image("assets/ip/90-100.png")
        score_text = QVBoxLayout()
        self.score_label = QLabel("--")
        self.score_label.setObjectName("score")
        self.score_status = QLabel("综合参考：等待扫描")
        self.score_status.setObjectName("scoreStatus")
        self.score_bar = QProgressBar()
        self.score_bar.setRange(0, 100)
        self.score_bar.setValue(0)
        self.score_bar.setObjectName("scoreBar")
        self.score_hint = QLabel("总分只作为参考，真正结论看三张独立评分卡。")
        self.score_hint.setObjectName("muted")
        self.score_hint.setWordWrap(True)
        score_text.addWidget(self.score_label)
        score_text.addWidget(self.score_status)
        score_text.addWidget(self.score_bar)
        score_text.addWidget(self.score_hint)
        score_layout.addWidget(self.emotion_image)
        score_layout.addLayout(score_text, 1)

        hero_layout.addLayout(left, 1)
        hero_layout.addWidget(score_panel)
        layout.addWidget(hero)

        grid = QGridLayout()
        grid.setSpacing(12)
        self.dimension_cards = {}
        for index, (key, title, note) in enumerate(SCORE_CARD_META):
            card = DimensionCard(title, note)
            self.dimension_cards[key] = card
            grid.addWidget(card, 0, index)
        layout.addLayout(grid)

        lower = QHBoxLayout()
        lower.setSpacing(12)
        hardware_panel = self._panel("硬件市场分布")
        self.hardware_chart = QTextEdit()
        self.hardware_chart.setObjectName("chartText")
        self.hardware_chart.setReadOnly(True)
        self.hardware_chart.setText("扫描后显示 CPU / 显卡 / 内存 / 硬盘 / 平台市场分。")
        hardware_panel.layout().addWidget(self.hardware_chart)
        pressure_panel = self._panel("当前软件压力概览")
        self.pressure_chart = QTextEdit()
        self.pressure_chart.setObjectName("chartText")
        self.pressure_chart.setReadOnly(True)
        self.pressure_chart.setText("扫描后显示聚合占用最高的软件组。")
        pressure_panel.layout().addWidget(self.pressure_chart)
        lower.addWidget(hardware_panel, 1)
        lower.addWidget(pressure_panel, 1)
        layout.addLayout(lower, 1)
        return page

    def _build_process_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("page")
        layout = QHBoxLayout(page)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(18)

        image_panel = QFrame()
        image_panel.setObjectName("visualPanel")
        image_layout = QVBoxLayout(image_panel)
        image_layout.setContentsMargins(0, 0, 0, 0)
        self.stage_image = QLabel()
        self.stage_image.setObjectName("stageImage")
        self.stage_image.setAlignment(Qt.AlignCenter)
        image_layout.addWidget(self.stage_image, 1)

        log_panel = self._panel("伊迪斯扫描中")
        self.stage_title = log_panel.findChild(QLabel)
        self.stage_text = QTextEdit()
        self.stage_text.setObjectName("panelTextLarge")
        self.stage_text.setReadOnly(True)
        log_panel.layout().addWidget(self.stage_text, 1)

        layout.addWidget(image_panel, 3)
        layout.addWidget(log_panel, 2)
        self._set_stage("scan")
        return page

    def _build_detail_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 22, 24, 24)
        title = QLabel("扫描详情")
        title.setObjectName("pageTitle")
        sub = QLabel("首页只放三大结论，原始硬件、软件、空间、进程和启动项数据统一放在这里。")
        sub.setObjectName("pageSub")
        self.detail_tabs = QTabWidget()
        self.detail_tabs.setObjectName("tabs")
        self.tables = {}
        for key, title_text, headers in [
            ("space", "空间", ["分类", "名称", "大小/容量", "说明", "建议"]),
            ("hardware", "硬件", ["模块", "状态", "影响", "建议"]),
            ("software", "常用软件", ["软件/分类", "常用分", "适配状态", "瓶颈", "建议"]),
            ("background", "后台与启动项", ["类型", "名称", "占用/来源", "说明", "建议"]),
            ("settings", "Windows 设置", ["设置", "当前值", "影响", "建议"]),
            ("risk", "稳定风险", ["项目", "状态", "风险", "建议"]),
        ]:
            table = self._make_table(headers)
            self.tables[key] = table
            self.detail_tabs.addTab(table, title_text)
        layout.addWidget(title)
        layout.addWidget(sub)
        layout.addWidget(self.detail_tabs, 1)
        return page

    def _build_hardware_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 22, 24, 24)
        title = QLabel("硬件详情")
        title.setObjectName("pageTitle")
        sub = QLabel("硬件市场水平只看硬件本身档次，不混入当前占用、后台和缓存。")
        sub.setObjectName("pageSub")
        self.hardware_table = self._make_table(["硬件", "得分", "档次", "原因"])
        layout.addWidget(title)
        layout.addWidget(sub)
        layout.addWidget(self.hardware_table, 1)
        return page

    def _build_software_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 22, 24, 24)
        title = QLabel("软件流畅度")
        title.setObjectName("pageTitle")
        sub = QLabel("这里判断运行此电脑软件是否流畅，重点看常用软件和多进程聚合压力。")
        sub.setObjectName("pageSub")
        self.software_table = self._make_table(["软件/分类", "状态", "占用/得分", "说明", "建议"])
        layout.addWidget(title)
        layout.addWidget(sub)
        layout.addWidget(self.software_table, 1)
        return page

    def _build_system_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 22, 24, 24)
        title = QLabel("系统详情")
        title.setObjectName("pageTitle")
        sub = QLabel("系统可用性关注 Windows、空间、缓存、后台、自启动和稳定性风险。")
        sub.setObjectName("pageSub")
        self.system_tabs = QTabWidget()
        self.system_tabs.setObjectName("tabs")
        self.system_tables = {
            "space": self._make_table(["分类", "名称", "大小/容量", "说明", "建议"]),
            "background": self._make_table(["类型", "名称", "占用/来源", "说明", "建议"]),
            "settings": self._make_table(["设置", "当前值", "影响", "建议"]),
            "risk": self._make_table(["项目", "状态", "风险", "建议"]),
        }
        for key, tab_title in [("space", "空间"), ("background", "后台与启动项"), ("settings", "Windows 设置"), ("risk", "稳定风险")]:
            self.system_tabs.addTab(self.system_tables[key], tab_title)
        layout.addWidget(title)
        layout.addWidget(sub)
        layout.addWidget(self.system_tabs, 1)
        return page

    def _build_ai_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 22, 24, 24)
        title = QLabel("优化引导")
        title.setObjectName("pageTitle")
        actions = QHBoxLayout()
        copy_btn = QPushButton("复制 AI 提示词")
        copy_btn.clicked.connect(self.on_copy_prompt)
        json_btn = QPushButton("导出 JSON 给 AI")
        json_btn.clicked.connect(self.on_export_json)
        txt_btn = QPushButton("导出 TXT 报告")
        txt_btn.clicked.connect(self.on_export_txt)
        actions.addWidget(copy_btn)
        actions.addWidget(json_btn)
        actions.addWidget(txt_btn)
        actions.addStretch(1)
        self.ai_text = QTextEdit()
        self.ai_text.setObjectName("panelTextLarge")
        self.ai_text.setReadOnly(True)
        self.ai_text.setText(AI_PROMPT_TEMPLATE)
        layout.addWidget(title)
        layout.addLayout(actions)
        layout.addWidget(self.ai_text, 1)
        return page

    def _build_brief_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 22, 24, 24)
        title = QLabel("简版报告")
        title.setObjectName("pageTitle")
        self.brief_text = QTextEdit()
        self.brief_text.setObjectName("panelTextLarge")
        self.brief_text.setReadOnly(True)
        self.brief_text.setText("扫描并完成 AI 分析后，这里会显示小白能看懂的简版报告。")
        layout.addWidget(title)
        layout.addWidget(self.brief_text, 1)
        return page

    def _build_history_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 22, 24, 24)
        title = QLabel("历史记录")
        title.setObjectName("pageTitle")
        self.history_text = QTextEdit()
        self.history_text.setObjectName("panelTextLarge")
        self.history_text.setReadOnly(True)
        layout.addWidget(title)
        layout.addWidget(self.history_text, 1)
        self._refresh_history()
        return page

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 22, 24, 24)
        title = QLabel("设置")
        title.setObjectName("pageTitle")
        info = QTextEdit()
        info.setObjectName("panelTextLarge")
        info.setReadOnly(True)
        info.setText(
            "当前版本定位：硬件是否还值得用 + 常用软件是否跑得动 + 系统环境是否拖后腿。\n\n"
            "原则：\n"
            "1. 软件只采集确定性数据，不做一键乱优化。\n"
            "2. 首页固定显示硬件状态、常用软件适配、系统可用性三张卡。\n"
            "3. 清理和禁用建议都区分安全、需确认、不要乱动。\n"
            "4. AI Key 只从 AIHUBMIX_API_KEY 环境变量读取，不写死在代码里。"
        )
        layout.addWidget(title)
        layout.addWidget(info, 1)
        return page

    def _panel(self, title: str) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 16)
        label = QLabel(title)
        label.setObjectName("panelTitle")
        layout.addWidget(label)
        return panel

    def _make_table(self, headers: list[str]) -> QTableWidget:
        table = QTableWidget()
        table.setObjectName("dataTable")
        table.setAlternatingRowColors(True)
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        return table

    def run_scan(self):
        if self.worker and self.worker.isRunning():
            return
        if hasattr(self, "stage_text"):
            self.stage_text.clear()
        self._set_stage("scan")
        self.menu.setCurrentRow(1)
        self.header_status.setText("扫描中")
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText("体检中...")
        self.worker = ScanWorker()
        self.worker.progress.connect(self.append_progress)
        self.worker.scan_finished.connect(self.on_scan_finished)
        self.worker.failed.connect(self.on_scan_failed)
        self.worker.start()

    def append_progress(self, text: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        if hasattr(self, "stage_text"):
            self.stage_text.append(f"[{timestamp}] {text}")

    def on_scan_finished(self, report: dict):
        self.current_report = report
        self._set_stage("thinking")
        self.header_status.setText("AI 分析中")
        self.append_progress("本地扫描完成，正在进入 AI 分析阶段。")
        self.ai_worker = AiWorker(report)
        self.ai_worker.progress.connect(self.append_progress)
        self.ai_worker.analysis_finished.connect(self.on_ai_finished)
        self.ai_worker.start()

    def on_ai_finished(self, report: dict):
        self.current_report = report
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText("重新体检")
        source = report.get("ai_result", {}).get("source", "")
        if source == "local_fallback":
            self.header_status.setText("本地规则报告")
            self.append_progress("AI 分析失败，已使用本地规则生成结果。")
        else:
            self.header_status.setText("分析完成")
            self.append_progress("AI 分析完成，正在回填首页。")
        self.current_ai_status = report.get("ai_status", {"success": source != "local_fallback", "source": source or "GPT", "message": "分析完成"})
        self._update_ai_status_indicator()
        self._refresh_views(report)
        self._refresh_history()
        self.menu.setCurrentRow(0)

    def on_scan_failed(self, message: str):
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText("重新体检")
        self.header_status.setText("扫描失败")
        self.append_progress(f"扫描失败：{message}")
        QMessageBox.critical(self, "扫描失败", message)

    def _update_ai_status_indicator(self):
        success = bool(self.current_ai_status.get("success"))
        if success:
            tooltip = f"{self.current_ai_status.get('source', 'GPT')} 分析成功，本页结果由 AI 生成"
        else:
            tooltip = "AI 分析未成功，本页结果为本地规则或未分析状态"
        self.ai_status_indicator.set_status(success, tooltip)

    def _refresh_views(self, report: dict):
        score = report.get("score", {})
        product = report.get("product", {})
        ai_result = report.get("ai_result") or build_local_ai_result(report)
        overall = ai_result.get("overall", {})
        scores = report.get("scores", {})
        total_score = int(overall.get("score", score.get("total_score", 0)) or 0)

        self.score_label.setText(str(total_score))
        self.score_bar.setValue(total_score)
        self.score_status.setText(f"综合参考：{overall.get('status', score.get('display_level', '已扫描'))}")
        self.score_hint.setText(overall.get("summary", "扫描完成。"))
        self.status_title.setText(f"当前状态：{overall.get('status', '已扫描')}")
        self.status_subtitle.setText(overall.get("summary", product.get("plain_summary", "扫描完成。")))
        self.last_scan_label.setText(f"最近扫描：{report.get('scan_time', '')}")
        self._set_emotion_image(self._emotion_image_from_key(overall.get("emotion") or emotion_key(total_score)))

        ai_card_map = {
            "hardware_market_score": ai_result.get("hardware_market_review", ai_result.get("hardware_review", {})),
            "software_smoothness_score": ai_result.get("software_smoothness_review", ai_result.get("software_fit_review", {})),
            "system_usability_score": ai_result.get("system_review", {}),
        }
        for key, card in self.dimension_cards.items():
            fallback = scores.get(key, {})
            data = ai_card_map.get(key, {}) or fallback
            card.set_data({"score": data.get("score", fallback.get("score", 0)), "status": data.get("status", fallback.get("status", "")), "summary": data.get("summary", fallback.get("summary", "")), "emotion": data.get("emotion")})

        self.hardware_chart.setText(self._build_hardware_chart(ai_result, report))
        self.pressure_chart.setText(self._build_pressure_chart(ai_result, report))

        self._fill_table(self.hardware_table, self._hardware_market_rows(ai_result, report))
        self._fill_table(self.software_table, self._software_rows(report))
        self._fill_table(self.system_tables["space"], self._space_rows(report))
        self._fill_table(self.system_tables["background"], self._background_rows(report))
        self._fill_table(self.system_tables["settings"], self._settings_rows(report))
        self._fill_table(self.system_tables["risk"], self._risk_rows(report))
        self.ai_text.setText(self._build_ai_preview(report))
        self.brief_text.setText(self._build_brief_text(report))

    def _space_rows(self, report: dict) -> list[list[object]]:
        rows = []
        for item in report.get("disk_partitions", []):
            rows.append(["磁盘分区", item.get("drive", ""), f"剩余 {item.get('free_gb', 0)}GB / 总 {item.get('total_gb', 0)}GB", f"占用 {item.get('usage_percent', 0)}%", "保持 C 盘至少 40GB 可用"])
        sections = report.get("product", {}).get("space_sections", {})
        for key, title in [("safe_clean", "安全清理"), ("confirm_clean", "确认后清理"), ("manual_review", "手动整理")]:
            for item in sections.get(key, []):
                rows.append([title, item.get("name", ""), f"{item.get('size_gb', 0)}GB", item.get("explain", ""), item.get("button", "")])
        return rows

    def _hardware_rows(self, report: dict) -> list[list[object]]:
        return [[i.get("name", ""), i.get("status", ""), i.get("impact", ""), i.get("suggestion", "")] for i in report.get("product", {}).get("hardware_bottlenecks", [])]

    def _hardware_market_rows(self, ai_result: dict, report: dict) -> list[list[object]]:
        review = ai_result.get("hardware_market_review", {})
        items = review.get("items") or report.get("scores", {}).get("hardware_market_score", {}).get("items", [])
        rows = []
        for item in items:
            rows.append([
                item.get("name", ""),
                f"{item.get('score', '--')}/{item.get('max_score', '--')}",
                item.get("level", ""),
                item.get("reason", item.get("detail", "")),
            ])
        return rows

    def _software_rows(self, report: dict) -> list[list[object]]:
        rows = [
            [i.get("name", ""), i.get("status", ""), f"{i.get('fit_score', '--')}分", i.get("bottleneck", ""), i.get("suggestion", "")]
            for i in report.get("product", {}).get("software_fit", [])
        ]
        for group in report.get("software", {}).get("process_groups", [])[:20]:
            rows.append([
                group.get("name", ""),
                group.get("pressure_level", ""),
                f"{group.get('memory_mb', 0)}MB / {group.get('process_count', 0)}进程",
                group.get("explain", ""),
                "压力源" if group.get("pressure_level") in {"中", "高"} else "正常观察",
            ])
        for item in report.get("software", {}).get("software_requirement_match", []):
            weak = "、".join(item.get("weak_hardware", [])) or "无明显短板"
            rows.append([item.get("category", ""), item.get("status", ""), "--", weak, f"建议基准：{item.get('required', {})}"])
        return rows

    def _background_rows(self, report: dict) -> list[list[object]]:
        rows = []
        process_summary = report.get("product", {}).get("process_summary", {})
        for group in report.get("software", {}).get("process_groups", [])[:20]:
            rows.append([
                f"进程聚合/{group.get('category', '')}",
                group.get("name", ""),
                f"{group.get('memory_mb', 0)}MB / {group.get('process_count', 0)} 个进程",
                group.get("explain", ""),
                "重点关注" if group.get("pressure_level") in {"中", "高"} else "正常观察",
            ])
        for item in process_summary.get("items", [])[:40]:
            rows.append([item.get("category", ""), item.get("name", ""), f"{item.get('cpu_percent', 0)}% / {item.get('memory_mb', 0)}MB", item.get("explain", ""), "可关闭观察" if item.get("can_close") else "建议保留"])
        for item in report.get("product", {}).get("startup_summary", {}).get("items", [])[:40]:
            rows.append([item.get("category", ""), item.get("name", ""), item.get("source", ""), item.get("impact", ""), " / ".join(item.get("buttons", []))])
        return rows

    def _settings_rows(self, report: dict) -> list[list[object]]:
        return [[i.get("name", ""), i.get("value", ""), i.get("impact", ""), i.get("suggestion", "")] for i in report.get("windows_settings", {}).get("items", [])]

    def _risk_rows(self, report: dict) -> list[list[object]]:
        return [[i.get("name", ""), i.get("status", ""), i.get("level", ""), i.get("suggestion", "")] for i in report.get("stability_risk", {}).get("risk_items", [])]

    def _fill_table(self, table: QTableWidget, rows: list[list[object]]):
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for col_index, value in enumerate(row):
                table.setItem(row_index, col_index, QTableWidgetItem(str(value)))

    def _build_ai_preview(self, report: dict) -> str:
        ai_result = report.get("ai_result") or build_local_ai_result(report)
        guide = ai_result.get("optimization_guide", {})
        steps = guide.get("steps", [])
        if steps:
            lines = [guide.get("title", "优化引导"), ""]
            for index, item in enumerate(steps, start=1):
                lines.extend([
                    f"{index}. {item.get('title', '')}",
                    f"原因：{item.get('reason', '')}",
                    f"收益：{item.get('benefit', '')}",
                    f"风险：{item.get('risk', '')}",
                    f"操作：{item.get('action', '')}",
                    f"自动支持：{'是' if item.get('auto_supported') else '否'}",
                    "",
                ])
            if ai_result.get("source") == "local_fallback":
                lines.append(f"提示：{ai_result.get('error', 'AI 分析失败，已使用本地规则生成。')}")
            return "\n".join(lines)

        scores = report.get("scores", {})
        lines = [
            build_ai_prompt(report),
            "",
            "====== 本次扫描摘要 ======",
            f"综合参考分：{scores.get('total_score', report.get('score', {}).get('total_score', 0))}/100",
            f"状态：{report.get('current_emotion', {}).get('status', '')}",
            f"一句话：{report.get('product', {}).get('plain_summary', '')}",
            "",
            "三大评分：",
        ]
        for key, title, _ in SCORE_CARD_META:
            item = scores.get(key, {})
            lines.append(f"- {title}：{item.get('score', '--')}分，{item.get('status', '')}，{item.get('summary', '')}")
        return "\n".join(lines)

    def _build_hardware_chart(self, ai_result: dict, report: dict) -> str:
        review = ai_result.get("hardware_market_review", {})
        items = review.get("items") or report.get("scores", {}).get("hardware_market_score", {}).get("items", [])
        if not items:
            return "暂无硬件市场分布。"
        rows = []
        for item in items:
            score = int(item.get("score", 0) or 0)
            max_score = int(item.get("max_score", 10) or 10)
            filled = int(round(score / max_score * 10)) if max_score else 0
            bar = "█" * filled + "░" * (10 - filled)
            rows.append(f"{item.get('name', ''):<4} {score:>2}/{max_score:<2}  {bar}")
        return "\n".join(rows)

    def _build_pressure_chart(self, ai_result: dict, report: dict) -> str:
        review = ai_result.get("software_smoothness_review", {})
        apps = review.get("pressure_apps") or report.get("software", {}).get("process_groups", [])[:5]
        if not apps:
            return "暂无明显软件压力。"
        rows = []
        for item in apps[:5]:
            name = item.get("name", "")
            level = item.get("level") or item.get("pressure_level", "")
            memory = float(item.get("memory_mb", 0) or 0)
            memory_text = f"{round(memory / 1024, 1)}GB" if memory >= 1024 else f"{round(memory)}MB"
            rows.append(f"{name:<10} {level:<2} {memory_text}")
        return "\n".join(rows)

    def _build_brief_text(self, report: dict) -> str:
        ai_result = report.get("ai_result") or build_local_ai_result(report)
        brief = ai_result.get("brief_report", {})
        content = brief.get("content") or brief.get("issues_by_impact", [])
        if not content:
            return "暂无简版报告。"
        lines = []
        for index, item in enumerate(content, start=1):
            if isinstance(item, dict):
                lines.append(f"{index}. {item.get('title', '')}\n原因：{item.get('reason', '')}\n建议：{item.get('action', '')}")
            else:
                lines.append(f"{index}. {item}")
        return "\n\n".join(lines)

    def _set_stage(self, stage: str):
        names = {
            "scan": ("伊迪斯扫描中", "assets/status/scan.png"),
            "loading": ("伊迪斯启动中", "assets/status/loading.png"),
            "thinking": ("伊迪斯分析中", "assets/status/thinking.png"),
        }
        title, image = names.get(stage, names["scan"])
        if hasattr(self, "stage_title") and self.stage_title:
            self.stage_title.setText(title)
        path = Path(__file__).resolve().parents[1] / image
        pixmap = QPixmap(str(path))
        if hasattr(self, "stage_image") and not pixmap.isNull():
            self.stage_image.setPixmap(pixmap.scaled(620, 620, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _set_emotion_image(self, image_path: str):
        path = Path(image_path)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[1] / image_path
        pixmap = QPixmap(str(path))
        if not pixmap.isNull():
            self.emotion_image.setPixmap(pixmap.scaled(128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.emotion_image.setText("🙂")
            self.emotion_image.setAlignment(Qt.AlignCenter)

    def _emotion_image(self, score: int) -> str:
        if score >= 90:
            return "assets/ip/90-100.png"
        if score >= 75:
            return "assets/ip/70-90.png"
        if score >= 60:
            return "assets/ip/60-70.png"
        if score >= 40:
            return "assets/ip/30-60.png"
        return "assets/ip/0-30.png"

    def _emotion_image_from_key(self, key: str) -> str:
        return f"assets/emotion/{key}.png"

    def _refresh_history(self):
        report_dir = Path(__file__).resolve().parents[1] / "data" / "reports"
        files = sorted(report_dir.glob("BenBen_PC_Report_*"), key=lambda p: p.stat().st_mtime, reverse=True)[:20]
        if not files:
            text = "暂无历史报告。"
        else:
            text = "\n".join(f"{datetime.fromtimestamp(p.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}  {p.name}" for p in files)
        self.history_text.setPlainText(text)

    def _require_report(self) -> bool:
        if not self.current_report:
            QMessageBox.warning(self, "提示", "请先执行一次扫描。")
            return False
        return True

    def on_export_json(self):
        if not self._require_report():
            return
        path = export_json(self.current_report)
        QMessageBox.information(self, "导出成功", f"JSON 已导出：\n{path}")
        self._refresh_history()

    def on_export_txt(self):
        if not self._require_report():
            return
        path = export_txt(self.current_report)
        QMessageBox.information(self, "导出成功", f"TXT 已导出：\n{path}")
        self._refresh_history()

    def on_copy_prompt(self):
        text = build_ai_prompt(self.current_report) if self.current_report else AI_PROMPT_TEMPLATE
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "已复制", "AI 诊断模板和本次摘要已复制到剪贴板。")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()


def run_app():
    app = QApplication([])
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    app.setWindowIcon(QIcon(str(Path(__file__).resolve().parents[1] / "assets" / "app_icon.ico")))
    win = MainWindow()
    win.show()
    app.exec_()


APP_QSS = """
QWidget#outer {
    background: transparent;
    font-family: "Microsoft YaHei UI", "Microsoft YaHei";
}
QFrame#shell {
    background: #f6f7f9;
    border: 1px solid #d9dde5;
    border-radius: 24px;
}
QFrame#topBar {
    background: #ffffff;
    border-top-left-radius: 24px;
    border-top-right-radius: 24px;
    border-bottom: 1px solid #e6e9ef;
    min-height: 56px;
    max-height: 56px;
}
QWidget#body, QStackedWidget, QWidget#page {
    background: #f6f7f9;
    color: #1f2937;
}
QPushButton#closeDot { background: #ff5f57; border: none; border-radius: 6px; }
QPushButton#minDot { background: #febc2e; border: none; border-radius: 6px; }
QLabel#logo {
    background: #2f7cf6;
    color: #ffffff;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 800;
    min-width: 34px;
    min-height: 30px;
    qproperty-alignment: AlignCenter;
}
QLabel#appName { color: #111827; font-size: 16px; font-weight: 800; }
QLabel#appCaption, QLabel#headerStatus, QLabel#muted, QLabel#pageSub {
    color: #6b7280;
    font-size: 13px;
}
QLabel#headerStatus {
    background: #eef4ff;
    color: #2f5fb8;
    border: 1px solid #d4e2ff;
    border-radius: 12px;
    padding: 7px 14px;
}
QListWidget#sidebar {
    background: #ffffff;
    border: none;
    border-right: 1px solid #e6e9ef;
    padding: 18px 12px;
    color: #667085;
    outline: none;
}
QListWidget#sidebar::item {
    height: 44px;
    padding-left: 16px;
    border-radius: 10px;
    margin: 2px 0;
}
QListWidget#sidebar::item:hover { background: #f1f5f9; color: #111827; }
QListWidget#sidebar::item:selected {
    background: #1f2937;
    color: #ffffff;
    font-weight: 700;
}
QFrame#hero, QFrame#dimensionCard, QFrame#panel, QFrame#scorePanel, QFrame#visualPanel, QTextEdit#panelTextLarge, QTableWidget#dataTable {
    background: #ffffff;
    border: 1px solid #e1e6ef;
    border-radius: 22px;
}
QFrame#hero { min-height: 190px; }
QLabel#heroTitle { color: #111827; font-size: 32px; font-weight: 900; }
QLabel#heroSub { color: #4b5563; font-size: 15px; }
QLabel#score { color: #111827; font-size: 56px; font-weight: 900; }
QLabel#scoreStatus { color: #2f5fb8; font-size: 14px; font-weight: 800; }
QLabel#emotionImage {
    background: #f8fafc;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    qproperty-alignment: AlignCenter;
    font-size: 54px;
}
QLabel#cardEmotion {
    background: #f8fafc;
    border: 1px solid #e5e7eb;
    border-radius: 14px;
    qproperty-alignment: AlignCenter;
}
QLabel#stageImage {
    background: #ffffff;
    border-radius: 22px;
}
QProgressBar#scoreBar {
    background: #e5e7eb;
    border: none;
    border-radius: 5px;
    height: 10px;
}
QProgressBar#scoreBar::chunk { background: #22c55e; border-radius: 5px; }
QLabel#cardTitle { color: #6b7280; font-size: 13px; font-weight: 700; }
QLabel#cardScore { color: #111827; font-size: 28px; font-weight: 900; }
QLabel#cardStatus { color: #2f5fb8; font-size: 13px; font-weight: 800; }
QLabel#cardSummary { color: #4b5563; font-size: 13px; }
QLabel#panelTitle { color: #111827; font-size: 16px; font-weight: 800; }
QLabel#pageTitle { color: #111827; font-size: 28px; font-weight: 900; }
QPushButton {
    background: #ffffff;
    color: #1f2937;
    border: 1px solid #d0d7e2;
    border-radius: 14px;
    padding: 10px 16px;
    font-weight: 700;
}
QPushButton:hover { background: #f1f5f9; }
QPushButton#primaryButton {
    background: #2563eb;
    color: #ffffff;
    border: none;
    padding: 12px 26px;
}
QPushButton#primaryButton:hover { background: #1d4ed8; }
QPushButton#secondaryAction { background: #f8fafc; }
QPushButton:disabled { background: #e5e7eb; color: #94a3b8; }
QTextEdit#panelText, QTextEdit#panelTextLarge {
    background: #ffffff;
    border: 1px solid #e1e6ef;
    border-radius: 16px;
    color: #1f2937;
    padding: 10px;
    selection-background-color: #bfdbfe;
}
QTextEdit#panelText { min-height: 130px; }
QTabWidget::pane {
    border: 1px solid #e1e6ef;
    border-radius: 18px;
    background: #ffffff;
}
QTabBar::tab {
    background: #edf2f7;
    color: #475569;
    border-radius: 14px;
    padding: 9px 14px;
    margin-right: 6px;
}
QTabBar::tab:selected {
    background: #1f2937;
    color: #ffffff;
}
QTableWidget#dataTable {
    color: #1f2937;
    alternate-background-color: #f8fafc;
    selection-background-color: #dbeafe;
    gridline-color: #edf2f7;
}
QHeaderView::section {
    background: #f1f5f9;
    color: #475569;
    border: none;
    padding: 10px;
    font-weight: 800;
}
"""


if __name__ == "__main__":
    run_app()
