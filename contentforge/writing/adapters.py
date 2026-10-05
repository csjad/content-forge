"""文案工坊·平台适配：一份脚本 → 八大平台发布包（标题/正文/标签）
每个平台标题给 3 个候选（选最优留余量，人工可改）
"""

from ..utils.llm import LLMClient
from ..utils.log import get_logger

log = get_logger("adapters")

_SYSTEM = (
    "你是熟悉国内外主流内容平台的新媒体运营专家。"
    "你负责把一条视频脚本，适配成各平台的标题、正文与话题标签，"
    "贴合每个平台的调性、字数限制与流量逻辑。"
)

_USER_TEMPLATE = """请根据视频脚本，为以下平台分别生成发布文案。

【内容方向约束】
{direction}

【视频脚本（分句）】
{script}

【平台与要求】
1. douyin（抖音）：标题≤28字，口语化有钩子；正文1-2句引导；话题标签3-5个。
2. xiaohongshu（小红书）：标题≤20字，情绪化；正文分段、带适当emoji、口语化种草风；标签5-8个。
3. bilibili（B站）：标题≤40字，信息明确有悬念；简介3-5句；标签3-5个。
4. video_account（视频号）：标题≤25字；简介1-2句。
5. weibo（微博）：正文80-150字，带话题标签2-3个（格式 #话题#）。
6. youtube：标题≤60字符（英文标题可选中文+英文双语）；description 5-8句含关键词；tags 5-8个英文标签。
7. tiktok：标题≤60字符；hashtags 5-8个英文标签。
8. x（推特）：推文≤260字符；hashtags 3-5个。
9. instagram：caption 3-6句；hashtags 8-10个英文标签。

每个平台的标题给出 3 个候选（titles_zh / titles_en 视平台），
tags 用数组，如 ["#AI", "#工具"]。

返回 JSON：
{{
  "douyin": {{"titles": ["标题1","标题2","标题3"], "body": "正文", "tags": ["#.."]}},
  "xiaohongshu": {{"titles": ["标题1","标题2","标题3"], "body": "正文", "tags": ["#.."]}},
  "bilibili": {{"titles": ["标题1","标题2","标题3"], "body": "简介", "tags": ["#.."]}},
  "video_account": {{"titles": ["标题1","标题2","标题3"], "body": "简介"}},
  "weibo": {{"body": "正文", "tags": ["#话题#"]}},
  "youtube": {{"titles_zh": ["中文标题1","中文标题2","中文标题3"], "titles_en": ["English title"], "description": "...", "tags": ["tag1","tag2"]}},
  "tiktok": {{"titles": ["标题1","标题2","标题3"], "body": "caption", "tags": ["#tag1","#tag2"]}},
  "x": {{"body": "推文", "tags": ["#tag1","#tag2"]}},
  "instagram": {{"caption": "...", "tags": ["#tag1","#tag2"]}}
}}
只输出 JSON 对象本身。所有正文文案必须是完整成品，不要留占位符。
"""


class PlatformAdapter:
    def __init__(self, cfg):
        self.cfg = cfg
        self.llm = LLMClient(cfg.llm)

    def adapt(self, script_lines: list[str], outline: list[str]) -> dict | None:
        script_text = "\n".join(f"{i+1}. {line}" for i, line in enumerate(script_lines))
        outline_text = " / ".join(outline or [])
        user = _USER_TEMPLATE.format(
            direction=self.cfg.direction.to_prompt(),
            script=script_text,
            outline=outline_text,
        )
        try:
            result = self.llm.chat_json([
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user},
            ], temperature=0.85, max_tokens=8000)
        except Exception as e:
            log.error(f"平台文案适配失败: {e}")
            return None
        if not isinstance(result, dict):
            log.error("平台适配返回结构异常")
            return None
        # 归一化：titles 数组至少1个，没有则用列表第一个
        for _key, item in result.items():
            if isinstance(item, dict):
                for tkey in ("titles", "titles_zh", "titles_en"):
                    t = item.get(tkey)
                    if isinstance(t, list) and t:
                        item[tkey] = [str(x).strip() for x in t if str(x).strip()]
                for tkey in ("tags",):
                    t = item.get(tkey)
                    if isinstance(t, list) and t:
                        item[tkey] = [str(x).strip() for x in t if str(x).strip()]
        return result
