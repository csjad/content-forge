"""发布通道基类：所有通道实现 publish() 接口
返回 (success: bool, url: str|None, error: str|None)
"""
from abc import ABC, abstractmethod


class PublishChannel(ABC):
    name = "base"

    def __init__(self, cfg, db):
        self.cfg = cfg
        self.db = db

    @abstractmethod
    def publish(self, platform: str, content: dict, assets: dict,
                scripts: dict, scheduled_at: str) -> tuple[bool, str | None, str | None]:
        """assets: {"video": path, "cover": path, ...}（平台=base 的素材）
        scripts: 平台适配后的 {titles, body, tags, ...}
        """
        raise NotImplementedError
