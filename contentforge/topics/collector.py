"""热点采集器：多源抓取当日热点标题，失败自动降级
源：百度热搜 / 微博热搜 / 抖音热点（尽力而为）
"""
import time

import requests

from ..utils.log import get_logger

log = get_logger("collector")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

TIMEOUT = 10


def _get(url: str, headers: dict | None = None) -> requests.Response:
    return requests.get(url, headers=headers or {"User-Agent": UA}, timeout=TIMEOUT)


# ---------------- 百度热搜 ----------------
def baidu_hot(limit: int = 20) -> list[dict]:
    try:
        resp = _get("https://top.baidu.com/api/board?platform=wise&tab=realtime")
        data = resp.json()
        items = data.get("data", {}).get("cards", [])
        out = []
        for card in items:
            for item in card.get("content", [])[:limit]:
                title = item.get("word") or item.get("query")
                if title:
                    out.append({"title": title, "source": "baidu_hot",
                                "hot": item.get("hotScore", 0)})
        return out
    except Exception as e:
        log.warning(f"百度热搜抓取失败: {e}")
        return []


# ---------------- 微博热搜 ----------------
def weibo_hot(limit: int = 20) -> list[dict]:
    try:
        resp = _get("https://weibo.com/ajax/side/hotSearch")
        data = resp.json()
        items = data.get("data", {}).get("realtime", [])
        out = []
        for item in items[:limit]:
            title = item.get("word")
            if title:
                out.append({"title": title, "source": "weibo_hot",
                            "hot": item.get("raw_hot", 0)})
        return out
    except Exception as e:
        log.warning(f"微博热搜抓取失败: {e}")
        return []


# ---------------- 抖音热点（尽力而为） ----------------
def douyin_hot(limit: int = 20) -> list[dict]:
    try:
        url = ("https://www.douyin.com/aweme/v1/web/hot/search/list/?device_platform=webapp"
               "&aid=6383&channel=channel_pc_web&detail_list=1")
        resp = _get(url, headers={"User-Agent": UA, "Referer": "https://www.douyin.com/"})
        data = resp.json()
        items = (data.get("data") or {}).get("word_list", [])
        out = []
        for item in items[:limit]:
            title = item.get("word") or item.get("sentence")
            if title:
                out.append({"title": title, "source": "douyin_hot",
                            "hot": item.get("hot_value", 0)})
        return out
    except Exception as e:
        log.warning(f"抖音热点抓取失败: {e}")
        return []


def collect(sources: list[str] | None = None) -> list[dict]:
    """汇总所有热点，返回 [{title, source, hot}]，去重"""
    sources = sources or ["baidu_hot", "weibo_hot", "douyin_hot"]
    handlers = {
        "baidu_hot": baidu_hot,
        "weibo_hot": weibo_hot,
        "douyin_hot": douyin_hot,
    }
    all_items: list[dict] = []
    for name in sources:
        handler = handlers.get(name)
        if not handler:
            log.warning(f"未知热点源: {name}")
            continue
        try:
            items = handler()
            log.info(f"热点源 {name}: 抓到 {len(items)} 条")
            all_items.extend(items)
            time.sleep(0.5)  # 礼貌间隔
        except Exception as e:
            log.warning(f"热点源 {name} 异常: {e}")
    # 去重（按标题）
    seen = set()
    deduped = []
    for item in all_items:
        t = item["title"].strip()
        if t and t not in seen:
            seen.add(t)
            deduped.append(item)
    return deduped
