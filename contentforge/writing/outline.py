"""文案工坊·脚本大纲：选题 → 口播脚本（分句字幕稿）+ 结构化大纲
输出统一进 contents 表，随后按平台适配
"""
from ..db import DB
from ..utils.llm import LLMClient
from ..utils.log import get_logger

log = get_logger("writing")

_SYSTEM = (
    "你是一位顶级短视频编剧和口播文案作者。你写的脚本要：3秒钩子、信息密度高、"
    "口语化自然、层层推进、结尾有行动引导。每句一个自然停顿，适合逐句配字幕。"
)

_USER_TEMPLATE = """请基于以下选题和内容方向，创作一条 {duration_sec} 秒左右的视频口播脚本。

【内容方向约束】
{direction}

【选题】
标题：{title}
概述：{summary}
切入角度：{angle}

要求：
1. 脚本按句拆分（script_lines），每句 8-25 字，便于逐句配字幕和配音。
2. 结构：hook（3秒钩子）→ 主体（干货/故事，2-4个要点）→ cta（引导关注/评论）。
3. 总句数约 {line_count} 句。
4. 语言口语化，符合内容方向风格，规避红线。
5. 返回 JSON：
{{
  "hook": "开头钩子（1句话）",
  "outline": ["要点1", "要点2", "要点3"],
  "script_lines": ["句1", "句2", "句3", ...],
  "cta": "结尾引导语",
  "duration_est": 60
}}
只输出 JSON 对象本身。
"""


class ScriptWriter:
    def __init__(self, cfg, db: DB):
        self.cfg = cfg
        self.db = db
        self.llm = LLMClient(cfg.llm)

    def write(self, topic: dict, format: str = "voice_slides") -> dict | None:
        duration = 60 if format == "voice_slides" else 90
        line_count = 14 if format == "voice_slides" else 20
        user = _USER_TEMPLATE.format(
            direction=self.cfg.direction.to_prompt(),
            title=topic["title"],
            summary=topic.get("summary", ""),
            angle=topic.get("angle", ""),
            duration_sec=duration,
            line_count=line_count,
        )
        try:
            result = self.llm.chat_json([
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user},
            ], temperature=0.85)
        except Exception as e:
            log.error(f"脚本生成失败: {e}")
            return None

        script_lines = result.get("script_lines") or []
        if len(script_lines) < 3:
            log.error("脚本句数异常，放弃")
            return None
        return {
            "hook": result.get("hook", script_lines[0]),
            "outline": result.get("outline", []),
            "script_lines": script_lines,
            "cta": result.get("cta", ""),
            "duration_est": result.get("duration_est", duration),
        }
