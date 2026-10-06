# ContentForge：一条命令，产出全平台内容

> 开源内容自动化流水线 —— 从选题、写文案、做视频，到多平台发布，全部一条命令完成。
> GitHub: https://github.com/csjad/content-forge · MIT License · Python 3.11+

---

## 做内容的人，都懂这种累

每天打开电脑，你要做四件事：**选题、写文案、做视频、发布**。

光选题就要翻热搜、看同行、猜用户想看什么；文案要一稿一稿改，改完还要给每个平台分别适配标题和标签；视频要配音、加字幕、调比例；发布更痛苦——抖音发一遍、小红书发一遍、B站发一遍，每个平台单独登录、单独上传。

一个人，硬扛四个人的活。

**ContentForge 把这条流水线全部自动化了。**

---

## 它是什么

ContentForge 是一个**自托管的一键内容工厂**：你输入一条命令，它完成从热点调研 → AI 选题打分 → 分平台文案 → edge-tts 配音 → PIL 字幕帧 → ffmpeg 合成视频 → 定时发布队列 → 数据看板的完整闭环。

| 阶段 | 做了什么 |
| --- | --- |
| **选题引擎** | 采集百度 / 微博 / 抖音热搜（断网优雅降级）；AI 打分进入 SQLite 候选池；标题去重 |
| **文案工坊** | 痛点钩子 + 结构化大纲 + 多行脚本；9 个平台适配器分别产出标题、正文、标签、描述 |
| **视频工厂** | 逐句 edge-tts 配音（按句界打时间戳）；PIL 渲染字幕帧 + 渐变封面；ffmpeg 合成平台原生竖版视频（1080×1920），可选 BGM |
| **分发编排** | 内容进入队列，按各平台黄金时段调度；官方 API（YouTube / X）+ Playwright 浏览器自动化（抖音/小红书/B站/微博/TikTok/Instagram）双通道派发；视频号提供半自动兜底 |
| **数据看板** | `contentforge status` 一屏看清今日候选、已选选题、已产内容与队列健康度 |

### 流水线一览

```
  config.yaml + .env (direction / LLM / platforms)
        │
        ▼
┌─────────────┐   ┌──────────────┐   ┌─────────────┐   ┌─────────────────┐
│ topic engine │→ │ writing shop │→ │ video plant │→ │ publish queue   │
│ collector +  │   │ outline +    │   │ tts + frame │   │ scheduler +     │
│ AI scoring   │   │ 9 adapters   │   │ + compose   │   │ API / RPA /    │
└──────┬──────┘   └──────┬───────┘   └──────┬──────┘   │ manual channels │
       │                 │                  │          └────────┬────────┘
       ▼                 ▼                  ▼                   ▼
   topics table      contents table      assets table     publish_queue
                      SQLite state (state/forge.db)  +  data/ outputs
```

---

## 快速开始（三步）

**1. 安装**（Python 3.11+，需要 PATH 上的 ffmpeg）

```bash
git clone https://github.com/csjad/content-forge.git
cd content-forge
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
```

**2. 配置**（`config.yaml`）

```yaml
direction:
  niche: University student growth   # 你的内容人设，随时可换
  language: zh-CN
  must_avoid: clickbait

llm:                                  # OpenAI 兼容端点（DeepSeek/豆包/Agnes…）
  base_url: "https://api.deepseek.com/v1"
  api_key: "sk-..."
  model: "deepseek-chat"
```

**3. 生产**

```bash
contentforge run --auto      # 选题 → 文案 → 视频 → 入队，全自动
contentforge status          # 今日看板
contentforge publish         # 派发到期队列
contentforge publish --force # 立即派发全部待发布项
```

Windows 用户还附带了 `scripts/install_scheduler.ps1`，一条命令注册计划任务，实现完全无人值守的日更。

---

## 平台通道矩阵

| 平台 | 通道 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| YouTube | `api_youtube` | OAuth 2.0 device flow | 断点续传上传，默认 `private`，token 自动刷新 |
| X / Twitter | `api_x` | OAuth 1.0a（app-level） | HMAC-SHA1 签名，媒体分块上传，`POST /2/tweets` |
| 抖音 | `rpa_douyin` | 会话（登录一次） | Playwright + 系统 Edge，默认无头，`--show` 可见 |
| 小红书 | `rpa_xiaohongshu` | 会话 | — |
| B站 | `rpa_bilibili` | 会话 | — |
| 微博 | `rpa_weibo` | 会话 | — |
| TikTok | `rpa_tiktok` | 会话 | — |
| Instagram | `rpa_instagram` | 会话 | — |
| 视频号 | `manual_video_account` | — | 备好一切，你确认最终发布 |

每个平台的详细配置见 [docs/platform-channels.md](platform-channels.md)。

---

## 为什么不是玩具

开源内容工具很多，但多数是"半成品 demo"。ContentForge 的定位是**可长期服役的自托管生产线**：

- **类型化配置**：不可变 dataclass + 启动校验，配错直接报错，不静默带病运行
- **单一状态源**：选题、内容、资产、发布队列全部落在 `state/forge.db` 一个 SQLite 里，随时可查可改
- **可验证产物**：每一件产物（文案/字幕帧/视频/队列项）都有明确落盘路径与校验
- **37 个 pytest 测试 + CI 四平台全绿**：不是跑一次就行的脚本，是可以放心交给计划任务的系统
- **合规意识内置**：YouTube 默认 `private` 上传、自动化发布免责声明独立成 `NOTICE.md`、平台矩阵文档明示各通道的鉴权与兜底方式

---

## 合规与免责

ContentForge 默认遵守平台规范：自动化发布存在平台风控风险，`NOTICE.md` 列出了四条使用须知（账号安全、平台规则、内容责任、频率控制）。发布前请自行确认你所在平台对自动化发布的态度。项目对任何自动化操作导致的账号风险不承担责任。

---

## 路线图与贡献

- [ ] PyPI 发布（`pip install contentforge`）
- [ ] 更多语言与平台适配器
- [ ] 数据看板 Web 界面
- [ ] 多账号轮换与频率控制

欢迎提 Issue、PR，或到 Discussions 交流你的内容自动化玩法。项目采用 MIT 协议，随便拿去改、拿去用。

**GitHub: https://github.com/csjad/content-forge —— 觉得有用就点个 Star ⭐**

---

*本文由 ContentForge 团队撰写，欢迎转载并注明出处。*
