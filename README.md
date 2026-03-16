# 巴西经贸信息周报自动生成系统

自动抓取中巴双边经贸新闻，通过三层 AI 筛选，生成高质量结构化分析报告。

## 功能特性

- **多源爬虫**：覆盖 13 个中巴官方信息源，6 线程并发抓取
- **三层 AI 筛选**：
  1. Gemini Flash Lite 200 并发粗筛 → 过滤无关文章
  2. Gemini Flash 逐篇独立评分（0-100）→ 精选最重要的 6 篇
  3. Claude Sonnet 深度分析 → 生成专业情报简报
- **Web 界面**：浏览器操作，选择日期即可生成报告，支持进度追踪和下载

## 快速开始

### 环境变量配置

系统使用两套 API：Gemini（粗筛+深度评分）和 OpenAI 兼容（报告生成）。

**Gemini API（粗筛 + 深度评分）：**

| 变量 | 必填 | 说明 |
|------|------|------|
| `GEMINI_API_KEY` | **是** | Google Gemini API Key |
| `GEMINI_MODEL` | **是** | 粗筛模型（如 `gemini-3.1-flash-lite-preview`） |
| `GEMINI_DEEP_MODEL` | **是** | 深度评分模型（如 `gemini-3-flash-preview`） |
| `GEMINI_CONCURRENCY` | 否 | 粗筛并发数（默认 200） |

**OpenAI 兼容 API（报告生成）：**

| 变量 | 必填 | 说明 |
|------|------|------|
| `AI_API_KEY` | **是** | OpenAI 兼容 API Key |
| `AI_BASE_URL` | **是** | OpenAI 兼容 API 地址 |
| `AI_SONNET_MODEL` | **是** | 报告模型（如 `claude-sonnet-4-6`） |

### 本地运行

```bash
pip install -e .

# 设置环境变量
export GEMINI_API_KEY=your-gemini-key
export GEMINI_MODEL=gemini-3.1-flash-lite-preview
export GEMINI_DEEP_MODEL=gemini-3-flash-preview
export AI_API_KEY=your-openai-key
export AI_BASE_URL=https://your-api-endpoint/v1
export AI_SONNET_MODEL=claude-sonnet-4-6

# Web 模式
uvicorn brazil_daily_news.web.app:app --port 8000
```

### Docker 部署

```bash
docker build -t brazil-news .
docker run -p 8000:8000 \
  -e GEMINI_API_KEY=your-gemini-key \
  -e GEMINI_MODEL=gemini-3.1-flash-lite-preview \
  -e GEMINI_DEEP_MODEL=gemini-3-flash-preview \
  -e AI_API_KEY=your-openai-key \
  -e AI_BASE_URL=https://your-api-endpoint/v1 \
  -e AI_SONNET_MODEL=claude-sonnet-4-6 \
  brazil-news
```

### Render 一键部署

1. Fork 本仓库到你的 GitHub
2. 在 Render Dashboard 创建新的 Web Service，关联仓库
3. 在 Environment 中设置全部 6 个必填环境变量
4. 部署完成后即可访问

## 架构说明

```
新闻源 (13个)
    │
    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  爬虫层       │───▶│ 粗筛          │───▶│ 深度评分      │───▶│  报告生成     │
│ 6线程并发抓取 │    │ Gemini Lite  │    │ Gemini Flash │    │ Claude Sonnet│
│              │    │ 200并发       │    │ 逐篇打分0-100│    │ 最多6篇深度  │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
    │                    │                    │                    │
    ▼                    ▼                    ▼                    ▼
  ~90篇             ~15篇相关            前6篇精选           专业情报简报
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
brazil-news --start 2026-03-09 --end 2026-03-16
brazil-news --start 2026-03-09 --end 2026-03-16 --dry-run
brazil-news --start 2026-03-09 --end 2026-03-16 --force-scrape
brazil-news --start 2026-03-09 --end 2026-03-16 --steps filter,report
brazil-news --start 2026-03-09 --end 2026-03-16 -v
```
