# BenBenPCCheck (V1.3 原型)

## 运行

```bash
pip install -r requirements.txt
python main.py
```

## 已实现

- 一键体检（系统、CPU、内存、磁盘、进程、启动项、可清理项）
- 本地诊断规则
- 本地评分 + 5 档 IP 表情状态
- 四维体检评分：空间、硬件、软件、系统
- 当前状态只显示一个 IP 表情，默认开心，体检后按总分切换
- Top3 体验问题永远生成 3 条
- 显卡读取：优先 NVIDIA SMI，兜底 PowerShell CIM
- 已安装软件扫描 + 常用软件画像记录
- 软件适配：根据常用软件画像和软件配置档案判断是否跑得动
- 空间、硬件、软件、系统、报告与建议 6 页产品结构
- JSON/TXT 报告导出
- AI 分析模板复制

## 报告输出目录

`data/reports/`
