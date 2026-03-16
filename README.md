# 巴西经贸信息周报自动生成系统

自动抓取中巴双边经贸新闻，通过 AI 过滤筛选相关内容，生成结构化分析报告。

## 功能特性

- **多源爬虫**：覆盖 13 个中巴官方信息源，自动抓取指定日期范围内的新闻
- **AI 智能过滤**：Claude Haiku 逐篇判断经贸相关性，精准筛选有价值文章
- **AI 报告生成**：Claude Sonnet 生成结构化周报，含数据解读和趋势分析
- **Web 界面**：浏览器操作，选择日期即可生成报告，支持进度追踪和历史查看

## 快速开始

### API 配置

两种方式提供 AI API 凭据（二选一）：

- **前端填写**（推荐）：打开网页后在 "API 配置" 区域填入 Key 和地址，自动保存到浏览器本地
- **环境变量**：设置 `AI_API_KEY` 和 `AI_BASE_URL`，作为默认值

| 变量 | 必填 | 说明 |
|------|------|------|
| `AI_API_KEY` | 否* | OpenAI 兼容 API 的 Key |
| `AI_BASE_URL` | 否* | OpenAI 兼容 API 地址 |
| `AI_HAIKU_MODEL` | 否 | 过滤模型（默认 claude-haiku-4-5-20251001） |
| `AI_SONNET_MODEL` | 否 | 报告模型（默认 claude-sonnet-4-6） |

*Web 模式下用户可在前端填写，CLI 模式下必须通过环境变量设置

### 本地运行

```bash
pip install -e .

# CLI 模式
brazil-news --start 2026-03-09 --end 2026-03-16

# Web 模式
uvicorn brazil_daily_news.web.app:app --port 8000
# 浏览器打开 http://localhost:8000
```

### Docker 部署

```bash
docker build -t brazil-news .
docker run -p 8000:8000 \
  -e AI_API_KEY=your-key \
  -e AI_BASE_URL=https://your-api-endpoint/v1 \
  brazil-news
```

### Render 一键部署

1. Fork 本仓库到你的 GitHub
2. 在 Render Dashboard 创建新的 Web Service，关联仓库
3. 在 Environment 中设置 `AI_API_KEY` 和 `AI_BASE_URL`
4. 部署完成后即可访问

## 架构说明

```
新闻源 (13个)
    │
    ▼
┌──────────┐    ┌──────────────┐    ┌──────────────┐
│  爬虫层   │───▶│  AI 过滤层    │───▶│  AI 报告生成  │
│ Scraper  │    │ Claude Haiku │    │ Claude Sonnet│
└──────────┘    └──────────────┘    └──────────────┘
    │                  │                    │
    ▼                  ▼                    ▼
  data/raw/      data/filtered/       reports/
```

## 项目结构

```
Brazil_Daily_News_Report/
├── pyproject.toml          # 项目配置与依赖
├── Dockerfile              # Docker 镜像
├── render.yaml             # Render 部署配置
├── .env.example            # 环境变量模板
├── config/
│   └── sources.yaml        # 新闻源配置
├── docs/
│   └── SOURCE_REGISTRY.md  # 来源说明文档
└── src/brazil_daily_news/
    ├── cli.py              # 命令行入口
    ├── pipeline.py         # 编排层
    ├── config.py           # 配置与数据模型
    ├── storage.py          # JSON 持久化
    ├── scraper/            # 爬虫模块
    ├── ai/                 # AI 模块（过滤 + 报告）
    └── web/                # Web 界面（FastAPI）
```

## 新闻源列表

| 来源 | 类别 | 国家 |
|------|------|------|
| 商务部驻巴西经商处 | 中方官方 | 中国 |
| 商务部 | 中方官方 | 中国 |
| 中国政府网 | 中方官方 | 中国 |
| 人民网国际频道 | 中方官方 | 中国 |
| 新华网 | 中方官方 | 中国 |
| 海关总署 | 中方官方 | 中国 |
| 港澳事务办公室 | 中方官方 | 中国 |
| MDIC 新闻 | 巴西官方 | 巴西 |
| Siscomex 新闻 | 巴西官方 | 巴西 |
| Fazenda 新闻 | 巴西官方 | 巴西 |
| IBGE 新闻 | 巴西官方 | 巴西 |
| Planalto | 巴西官方 | 巴西 |
| BCB Focus | 巴西官方 | 巴西 |

## CLI 用法

```bash
# 完整运行（爬虫 + AI 过滤 + 报告生成）
brazil-news --start 2026-03-09 --end 2026-03-16

# 只爬虫，不调 AI
brazil-news --start 2026-03-09 --end 2026-03-16 --dry-run

# 强制重新抓取
brazil-news --start 2026-03-09 --end 2026-03-16 --force-scrape

# 只运行特定步骤
brazil-news --start 2026-03-09 --end 2026-03-16 --steps filter,report

# 详细日志
brazil-news --start 2026-03-09 --end 2026-03-16 -v
```
