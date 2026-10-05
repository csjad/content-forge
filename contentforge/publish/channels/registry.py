"""通道注册表：platform → channel 实例"""
from ...utils.log import get_logger

log = get_logger("registry")


class ChannelRegistry:
    def __init__(self, cfg, db):
        self.cfg = cfg
        self.db = db
        self._channels = {}

    def register(self, channel):
        self._channels[channel.name] = channel
        return channel

    def get(self, name: str):
        return self._channels.get(name)

    def channels(self):
        return dict(self._channels)
