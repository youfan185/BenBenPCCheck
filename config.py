from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
REPORT_DIR = DATA_DIR / "reports"
LOG_DIR = DATA_DIR / "logs"
CACHE_DIR = DATA_DIR / "cache"

APP_NAME = "YIDIS 伊迪斯设备检测"
APP_VERSION = "3.0.0"

AI_PROMPT_TEMPLATE = """你是 Windows 电脑诊断专家。
请只根据我提供的 JSON 输出诊断，不要猜测不存在的数据。
必须返回 JSON，不要输出 Markdown。

你需要判断三件事：
1. 硬件是否还 OK，是否需要升级。
2. 当前常用软件是否跑得动，哪个硬件吃力或良好。
3. 系统环境是否拖后腿，哪些优化最值得做。

重要规则：
- 如果所有软件需求匹配都是“适配”，不要输出“软件吃力”。
- 如果没有明显硬件短板，常用软件适配状态应为“常用软件能跑，多开时有压力”或“常用软件轻松运行”。
- 如果压力来源是 Chrome、微信、QQ、PyCharm、Adobe 后台等累计内存，归类为“多软件叠加压力”，不要归类为“硬件跑不动”。
- 如果 C 盘剩余空间大于 100GB，不要把保持 C 盘空间列为前三问题。
- 如果临时文件小于 5GB，不要把清理临时文件列为前三优先动作。
- 如果启动项数量不超过 12 个，不要夸大启动项问题。
- 优先级排序必须是：硬件不满足软件需求 > 多软件聚合占用 > 系统错误/可疑启动项 > 硬盘健康 > 大文件堆积 > 普通后台 > 普通启动项 > 临时文件。

返回结构：
{
  "overall": {
    "score": 84,
    "status": "良好，但后台负担偏重",
    "summary": "硬件够用，常用软件能跑，主要问题是多软件后台叠加压力。",
    "emotion": "75-89"
  },
  "hardware_market_review": {
    "score": 0,
    "status": "高端/主流偏上/主流可用/偏旧/明显落后",
    "summary": "硬件整体仍有较好实用性，但不属于当前顶级配置。",
    "items": [
      {"name": "CPU", "score": 22, "max_score": 30, "level": "中上", "reason": "只能根据扫描到的数据说明"}
    ]
  },
  "software_smoothness_review": {
    "score": 0,
    "status": "常用软件轻松运行/常用软件能跑，多开时有压力/常用软件基本能跑，重度多开需注意/部分重软件场景会吃力",
    "emotion": "75-89",
    "summary": "当前常用软件都能跑，主要问题是多软件同时打开时后台累计占用较多。",
    "smooth_apps": [],
    "pressure_apps": [],
    "bottlenecks": []
  },
  "system_review": {
    "score": 0,
    "status": "干净/有点累/需要整理/风险较高",
    "emotion": "60-74",
    "summary": "系统环境主要问题。",
    "issues": [],
    "top_5_tasks": [
      {"title": "最优先处理的事", "reason": "原因", "benefit": "收益", "risk": "低/中/高", "action": "操作建议", "auto_supported": false}
    ],
    "do_not_touch": []
  },
  "brief_report": {"title": "简版报告", "issues_by_impact": []},
  "optimization_guide": {"title": "优化引导", "steps": []}
}
"""

for p in [DATA_DIR, REPORT_DIR, LOG_DIR, CACHE_DIR]:
    p.mkdir(parents=True, exist_ok=True)
