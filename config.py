from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
REPORT_DIR = DATA_DIR / "reports"
LOG_DIR = DATA_DIR / "logs"
CACHE_DIR = DATA_DIR / "cache"

APP_NAME = "BenBen PC Check"
APP_VERSION = "1.0.0"

AI_PROMPT_TEMPLATE = """你是一名 Windows 电脑诊断专家，请根据我上传的 BenBen 电脑体检报告 JSON 文件进行分析。

请严格按照以下结构回复，不要自由发挥太多：
1. 电脑整体评分
2. 当前最主要的 3 个问题
3. 硬件是否需要升级
4. C 盘和空间问题
5. 启动项和后台程序
6. 清理和优化步骤
7. 风险提醒
8. 最终结论
"""

for p in [DATA_DIR, REPORT_DIR, LOG_DIR, CACHE_DIR]:
    p.mkdir(parents=True, exist_ok=True)
