"""通道工厂：按 config 中每平台的 channel 类型，实例化发布通道并注册"""
from ...utils.log import get_logger
from .api_x import XChannel
from .api_youtube import YoutubeChannel
from .registry import ChannelRegistry
from .rpa_bilibili import BilibiliChannel
from .rpa_douyin import DouyinChannel
from .rpa_instagram import InstagramChannel
from .rpa_tiktok import TiktokChannel
from .rpa_video_account import VideoAccountChannel
from .rpa_weibo import WeiboChannel
from .rpa_xhs import XiaohongshuChannel

log = get_logger("factory")

# platform_key -> {rpa: 类, api: 类, manual: 类}
_PLATFORM_CHANNELS = {
    "douyin": {"rpa": DouyinChannel, "api": None, "manual": None},
    "xiaohongshu": {"rpa": XiaohongshuChannel, "api": None, "manual": None},
    "bilibili": {"rpa": BilibiliChannel, "api": None, "manual": None},
    "video_account": {"rpa": None, "api": None, "manual": VideoAccountChannel},
    "weibo": {"rpa": WeiboChannel, "api": None, "manual": None},
    "youtube": {"rpa": None, "api": YoutubeChannel, "manual": None},
    "tiktok": {"rpa": TiktokChannel, "api": None, "manual": None},
    "x": {"rpa": None, "api": XChannel, "manual": None},
    "instagram": {"rpa": InstagramChannel, "api": None, "manual": None},
}

MANUAL_PLATFORMS = {"video_account"}  # 默认强制人工


def build_registry(cfg, db) -> ChannelRegistry:
    registry = ChannelRegistry(cfg, db)
    for platform, pcfg in cfg.platforms.items():
        if not pcfg.enabled:
            continue
        channel_type = pcfg.channel
        if platform in MANUAL_PLATFORMS:
            channel_type = "manual"
        mapping = _PLATFORM_CHANNELS.get(platform, {})
        cls = mapping.get(channel_type)
        if cls is None:
            log.warning(f"平台 {platform} 的通道类型 {channel_type} 暂未实现，将跳过发布")
            continue
        registry.register(cls(cfg, db))
        log.info(f"平台 {platform} → 通道 {cls.name}")
    return registry
