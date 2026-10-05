"""主流水线：选题 → 文案 → 视频 → 入队（一次 run 完成当日生产）
"""

from .config import Config
from .db import DB, TOPIC_APPROVED, TOPIC_DONE
from .publish.channels.factory import build_registry
from .publish.queue import PublishQueue
from .topics.collector import collect
from .topics.generator import TopicGenerator
from .utils.llm import LLMClient, LLMError
from .utils.log import get_logger
from .video.producer import VideoProducer
from .writing.adapters import PlatformAdapter
from .writing.outline import ScriptWriter

log = get_logger("pipeline")


class Pipeline:
    def __init__(self, config_path: str | None = None):
        self.cfg = Config(config_path) if config_path else Config()
        self.db = DB()
        self.llm = LLMClient(self.cfg.llm)

    # ---------- 阶段1：选题 ----------
    def generate_topics(self) -> list[dict]:
        if not self.llm.ready():
            raise LLMError(
                "LLM 未配置：请在 config.yaml 的 llm 段填写 base_url / api_key / model，"
                "或复制 .env.example 为 .env 并填入 LLM_API_KEY。"
            )
        log.info("阶段1/5 采集热点...")
        hot = collect(self.cfg.topics.sources)
        log.info(f"共采集到 {len(hot)} 条热点")
        gen = TopicGenerator(self.cfg, self.db)
        saved = gen.produce_candidates(hot)
        return saved

    def pick_topic(self, topic_id: int) -> dict:
        topic = self.db.get_topic(topic_id)
        if not topic:
            raise ValueError(f"选题不存在: {topic_id}")
        if topic["status"] != "candidate":
            raise ValueError(f"选题 {topic_id} 状态为 {topic['status']}，不能重复选用")
        self.db.set_topic_status(topic_id, TOPIC_APPROVED)
        log.info(f"已选用选题 #{topic_id}: {topic['title']}")
        return topic

    def auto_pick(self) -> dict:
        candidates = self.db.list_topics(status="candidate", limit=50)
        if not candidates:
            self.generate_topics()
            candidates = self.db.list_topics(status="candidate", limit=50)
        if not candidates:
            raise RuntimeError("候选池为空（AI 选题生成失败，请检查 LLM 配置）")
        top = max(candidates, key=lambda t: t["score"])
        return self.pick_topic(top["id"])

    # ---------- 阶段2：文案 ----------
    def write_scripts(self, topic: dict) -> dict | None:
        log.info(f"阶段2/5 创作脚本: {topic['title']}")
        writer = ScriptWriter(self.cfg, self.db)
        script = writer.write(topic)
        if not script:
            return None
        log.info(f"阶段3/5 平台适配（{len(self.cfg.enabled_platforms())} 个平台）...")
        adapter = PlatformAdapter(self.cfg)
        adapted = adapter.adapt(script["script_lines"], script["outline"])
        if not adapted:
            return None
        content_id = self.db.add_content(
            topic_id=topic["id"],
            format=self.cfg.video.default_format,
            hook=script["hook"],
            outline=script,
            scripts=adapted,
            direction_snapshot=self.cfg.direction.to_prompt(),
        )
        self.db.set_topic_status(topic["id"], TOPIC_DONE)
        log.info(f"内容 #{content_id} 脚本完成（{len(adapted)} 平台版本）")
        return self.db.get_content(content_id)

    # ---------- 阶段4：视频 ----------
    def produce_video(self, content: dict) -> dict:
        log.info("阶段4/5 生产视频（配音+字幕+合成）...")
        producer = VideoProducer(self.cfg, self.db)
        script_lines = content["outline"].get("script_lines", [])
        if not script_lines:
            raise RuntimeError("脚本缺少 script_lines，无法生产视频")
        result = producer.produce(content["id"], content["outline"].get("hook", ""), script_lines)
        self.db.set_content_status(content["id"], "ready")
        return result

    # ---------- 阶段5：入队 ----------
    def enqueue(self, content_id: int) -> list[int]:
        log.info("阶段5/5 生成发布队列...")
        content = self.db.get_content(content_id)
        registry = build_registry(self.cfg, self.db)
        queue = PublishQueue(self.cfg, self.db, registry)
        qids = queue.enqueue_for_content(content_id, content["scripts"])
        return qids

    # ---------- 一键流程 ----------
    def run(self, topic_id: int | None = None, auto_pick: bool = False) -> dict:
        if topic_id:
            topic = self.pick_topic(topic_id)
        elif auto_pick:
            topic = self.auto_pick()
        else:
            # CLI 交互模式：先保证候选池有货，由 CLI 展示并让用户选择
            candidates = self.db.list_topics(status="candidate", limit=50)
            if not candidates:
                self.generate_topics()
            topic = None
            return {"need_pick": True, "message": "候选池已就绪，等待选择选题"}

        content = self.write_scripts(topic)
        if not content:
            raise RuntimeError("文案生成失败，请检查 LLM 配置或重试")
        video = self.produce_video(content)
        qids = self.enqueue(content["id"])
        return {
            "topic": topic,
            "content": content,
            "video": video,
            "queue_ids": qids,
            "platform_count": len(qids),
        }
