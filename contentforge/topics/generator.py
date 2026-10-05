"""AI 选题生成：方向约束 + 热点参考 → 结构化候选选题（带评分和理由）
评分维度：与赛道契合度 / 受众兴趣 / 时效性 / 制作可行性 / 差异化
"""

from ..db import DB
from ..utils.llm import LLMClient
from ..utils.log import get_logger

log = get_logger("topics")

_SYSTEM = (
    "你是一位资深新媒体内容策划主编，擅长把热点转化为高传播的选题。"
    "你的任务是根据内容方向约束，结合热点参考列表，产出结构化的候选选题。"
)

_USER_TEMPLATE = """请围绕以下内容方向，结合提供的热点参考，产出 {n} 个候选选题。

【内容方向约束】
{direction}

【今日热点参考】（部分可用，不必都用，也可不受其限制）
{hot_topics}

要求：
1. 每个选题必须有明确的切入角度（angle），避免泛泛而谈。
2. 选题要适合视频内容，具备钩子潜力。
3. 按 0-100 打分，并给出简短的评分理由（reason）。
4. 返回 JSON 数组，格式：
[
  {{"title": "选题标题（口语化、有吸引力）", "summary": "一句话内容概述", "angle": "切入角度", "score": 88, "reason": "理由（<30字）"}}
]
只输出 JSON 数组本身。
"""


class TopicGenerator:
    def __init__(self, cfg, db: DB):
        self.cfg = cfg
        self.db = db
        self.llm = LLMClient(cfg.llm)

    def generate(self, hot_items: list[dict], n: int | None = None) -> list[dict]:
        n = n or self.cfg.topics.candidates_per_run
        direction = self.cfg.direction.to_prompt()
        hot_text = "\n".join(f"- {i.get('title')}" for i in hot_items[:30]) or "（今日无热点参考）"

        user = _USER_TEMPLATE.format(n=n, direction=direction, hot_topics=hot_text)
        try:
            result = self.llm.chat_json([
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user},
            ], temperature=0.9)
        except Exception as e:
            log.error(f"AI 选题生成失败: {e}")
            return []

        if isinstance(result, dict):
            result = result.get("topics") or result.get("candidates") or []
        if not isinstance(result, list):
            log.error(f"选题生成返回结构异常: {type(result)}")
            return []
        return result

    def produce_candidates(self, hot_items: list[dict]) -> list[dict]:
        """生成选题并写入候选池（自动去重 + 过滤低分）"""
        generated = self.generate(hot_items)
        min_score = self.cfg.topics.min_score
        dedup_days = self.cfg.topics.dedup_days
        snapshot = self.cfg.direction.to_prompt()

        saved = []
        for item in generated:
            title = (item.get("title") or "").strip()
            if not title:
                continue
            try:
                score = float(item.get("score", 0))
            except (TypeError, ValueError):
                score = 0
            if score < min_score:
                log.info(f"选题分低跳过: [{score}] {title}")
                continue
            if self.db.topic_exists(title, dedup_days):
                log.info(f"选题去重跳过: {title}")
                continue
            topic_id = self.db.add_topic(
                title=title,
                summary=item.get("summary", ""),
                angle=item.get("angle", ""),
                score=score,
                reason=item.get("reason", ""),
                source="ai",
                direction_snapshot=snapshot,
            )
            saved.append({"id": topic_id, **item})
        log.info(f"候选池新增 {len(saved)} 个选题（共生成 {len(generated)}，过滤 {len(generated)-len(saved)}）")
        return saved
