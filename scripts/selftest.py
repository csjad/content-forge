#!/usr/bin/env python
"""自测脚本：本地 Mock LLM 服务 + 全链路跑通（选题→文案→视频→入队）
用法：python scripts/selftest.py
验证点：
  1. 热点采集（真实网络，失败自动降级不影响）
  2. AI 选题/脚本/平台适配（Mock LLM，验证管道逻辑）
  3. 视频生产（真实 edge-tts + ffmpeg + PIL）
  4. 发布队列入队
  5. 产物检查（mp4 存在、时长合理、封面存在）
"""
import json
import os
import shutil
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TEST_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_selftest")
# 清理上次测试残留（独立测试库，不影响正式数据）
shutil.rmtree(TEST_ROOT, ignore_errors=True)
os.environ["FORGE_DB"] = os.path.join(TEST_ROOT, "selftest.db")

# ---------------- Mock LLM ----------------
TOPICS_JSON = json.dumps([
    {"title": "大学生为什么越努力越焦虑？", "summary": "解析努力的误区与正确节奏",
     "angle": "从'伪努力'切入，给出可执行的精力管理框架", "score": 92,
     "reason": "痛点共鸣强，角度新颖"},
    {"title": "大学里最该考的3个证书", "summary": "按就业价值排序推荐",
     "angle": "结合2026就业市场谈含金量", "score": 78,
     "reason": "干货型，搜索流量大"},
    {"title": "大一到大四，怎样规划不踩坑", "summary": "四年关键节点拆解",
     "angle": "学长视角时间线复盘", "score": 85,
     "reason": "长尾搜索强"},
], ensure_ascii=False)

SCRIPT_JSON = json.dumps({
    "hook": "你是不是也经常熬夜复习，成绩却上不去？",
    "outline": ["伪努力的表现", "精力管理的三个方法", "如何落地"],
    "script_lines": [
        "你是不是也经常熬夜复习，成绩却上不去？",
        "这大概率不是你不努力，而是陷入了伪努力。",
        "伪努力有三个表现：抄笔记不过脑、刷题不总结、熬夜感动自己。",
        "真正的努力，是精力管理。",
        "第一，把最难的任务放在早上大脑最清醒的时候。",
        "第二，每学习四十分钟，就起来活动五分钟。",
        "第三，睡前花十分钟，复盘今天真正完成了什么。",
        "坚持两周，你会明显感觉到效率的提升。",
        "如果这条视频对你有用，点个关注，下期继续讲学习方法。",
    ],
    "cta": "点个关注，下期继续讲学习方法。",
    "duration_est": 60,
}, ensure_ascii=False)

ADAPTER_JSON = json.dumps({
    "douyin": {"titles": ["伪努力正在毁掉你", "别再熬夜感动自己了", "三个方法告别伪努力"],
               "body": "你的努力可能方向错了，看完这条视频就知道怎么改。",
               "tags": ["#大学生", "#学习方法", "#自律"]},
    "xiaohongshu": {"titles": ["告别伪努力", "别再自我感动了", "高效学习法"],
                    "body": "曾经我也这样…直到我学会了精力管理。\n\n三个方法亲测有效：\n1️⃣ 难事放早上\n2️⃣ 四十分钟休息一次\n3️⃣ 睡前复盘",
                    "tags": ["#大学生活", "#学习方法", "#自律", "#效率", "#校园"]},
    "bilibili": {"titles": ["伪努力正在毁掉你的大学四年", "如何停止无效努力", "精力管理实操指南"],
                 "body": "本期视频拆解伪努力的三种表现，并给出可落地的精力管理方法。",
                 "tags": ["#大学生", "#学习方法", "#效率"]},
    "video_account": {"titles": ["告别伪努力", "大学高效学习法", "别再自我感动了"],
                      "body": "三个方法告别伪努力。"},
    "weibo": {"body": "伪努力的三表现，你中了几个？评论区聊聊。",
              "tags": ["#大学生", "#学习方法"]},
    "youtube": {"titles_zh": ["伪努力正在毁掉你的大学四年", "三个方法告别无效学习", "大学生高效学习指南"],
                "titles_en": ["Stop Fake Effort in College", "3 Ways to Study Smarter"],
                "description": "In this video, we break down fake effort and share practical energy management methods.",
                "tags": ["study", "college", "productivity"]},
    "tiktok": {"titles": ["Stop Fake Effort in College", "3 Study Hacks", "Study Smarter"],
               "body": "Are you studying hard but getting nowhere? Watch this.",
               "tags": ["#study", "#college", "#productivity"]},
    "x": {"body": "Fake effort is killing your progress. 3 methods to fix it.",
          "tags": ["#study", "#productivity"]},
    "instagram": {"caption": "Study smarter, not harder.\n\nSave this for your next study session.",
                  "tags": ["#studytips", "#college", "#productivity", "#selfimprovement"]},
}, ensure_ascii=False)


class MockHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        user_content = ""
        for m in body.get("messages", []):
            if m.get("role") == "user":
                user_content += m.get("content", "")

        if "候选选题" in user_content:
            reply = TOPICS_JSON
        elif "视频口播脚本" in user_content:
            reply = SCRIPT_JSON
        else:
            reply = ADAPTER_JSON

        resp = {"choices": [{"message": {"role": "assistant", "content": reply}}]}
        data = json.dumps(resp).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def start_mock_server() -> HTTPServer:
    server = HTTPServer(("127.0.0.1", 8765), MockHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server


# ---------------- 测试配置 ----------------
TEST_CONFIG = """forge:
  timezone: "Asia/Shanghai"
  cadence: "daily"
  daily_target: 1

direction:
  enabled: true
  niche: "大学生成长与校园干货"
  audience: "大学生"
  language: "zh-CN"
  style: "真诚、干货、口语化"
  must_avoid: "标题党"
  content_formats: "短视频口播"
  hooks: "痛点提问"
  custom_instructions: ""

llm:
  base_url: "http://127.0.0.1:8765/v1"
  api_key: "test"
  model: "mock"

tts:
  engine: "edge"
  voice: "zh-CN-XiaoxiaoNeural"
  rate: "+8%"
  pitch: "+0Hz"

image_source:
  engine: "local"
  local_dir: "E:/Desktop/doubao/可商用素材库"

video:
  default_format: "voice_slides"
  resolution: [1080, 1920]
  fps: 30
  bgm: false
  subtitle_style:
    font: "msyhbd"
    font_size_ratio: 0.052
    font_color: "#FFFFFF"
    stroke_color: "#000000"
    position: "bottom"
    margin_ratio: 0.08

platforms:
  douyin: {enabled: true, format: "voice_slides", channel: "rpa", publish_time: "19:00"}
  xiaohongshu: {enabled: true, format: "voice_slides", channel: "rpa", publish_time: "19:30"}
  bilibili: {enabled: true, format: "voice_slides", channel: "rpa", publish_time: "20:00"}
  video_account: {enabled: true, format: "voice_slides", channel: "manual", publish_time: "20:30"}
  weibo: {enabled: true, format: "voice_slides", channel: "rpa", publish_time: "12:00"}
  youtube: {enabled: true, format: "voice_slides", channel: "api", publish_time: "21:00"}
  tiktok: {enabled: true, format: "voice_slides", channel: "rpa", publish_time: "21:30"}
  x: {enabled: true, format: "voice_slides", channel: "api", publish_time: "22:00"}
  instagram: {enabled: true, format: "voice_slides", channel: "rpa", publish_time: "22:30"}

publish:
  confirm_before_publish: true
  max_retry: 2
  headless: true

topics:
  sources: ["baidu_hot", "weibo_hot"]
  candidates_per_run: 6
  min_score: 60
  dedup_days: 30
"""


def main():
    print("=" * 56)
    print("ContentForge 全链路自测")
    print("=" * 56)

    # 准备测试目录
    os.makedirs(TEST_ROOT, exist_ok=True)
    cfg_path = os.path.join(TEST_ROOT, "config.yaml")
    with open(cfg_path, "w", encoding="utf-8") as f:
        f.write(TEST_CONFIG)

    server = start_mock_server()
    print("[1/4] Mock LLM 服务已启动 (127.0.0.1:8765)")

    from contentforge.pipeline import Pipeline
    pipe = Pipeline(cfg_path)

    try:
        # ---- 阶段1: 热点 + 选题 ----
        print("[2/4] 热点采集 + AI 选题...")
        hot = []
        from contentforge.topics.collector import collect
        hot = collect(pipe.cfg.topics.sources)
        print(f"      热点: {len(hot)} 条")
        saved = pipe.generate_topics()
        assert saved, "选题生成失败"
        print(f"      候选选题: {len(saved)} 个, top: {saved[0]['title']}")

        # ---- 全自动 ----
        result = pipe.run(auto_pick=True)
        content = result["content"]
        video = result["video"]
        print(f"[3/4] 生产完成: 内容#{content['id']} | {len(content['scripts'])}个平台版本")
        print(f"      视频: {video['video_path']}")
        print(f"      时长: {video['duration']:.1f}s")

        # ---- 验证产物 ----
        print("[4/4] 产物验证...")
        ok = True
        vp = video["video_path"]
        if not os.path.exists(vp):
            print("  ❌ 视频文件不存在")
            ok = False
        else:
            size_mb = os.path.getsize(vp) / 1024 / 1024
            print(f"  ✅ 视频文件存在 ({size_mb:.1f} MB)")
            if video["duration"] < 20:
                print("  ⚠️ 视频偏短（脚本句数少）")
        cp = video["cover_path"]
        if os.path.exists(cp):
            print(f"  ✅ 封面存在: {cp}")
        else:
            print("  ❌ 封面缺失")
            ok = False
        qids = result["queue_ids"]
        print(f"  ✅ 发布队列: {len(qids)} 个平台")
        for qid in qids:
            item = pipe.db.get_queue_item(qid)
            print(f"     - [{item['platform']}] {item['scheduled_at']}")

        if not ok:
            print("\n自测失败")
            sys.exit(1)

        # 展示脚本预览
        print("\n===== 脚本预览（抖音版） =====")
        dy = content["scripts"].get("douyin", {})
        print("标题候选:", dy.get("titles"))
        print("正文:", dy.get("body", "")[:80])
        print("标签:", dy.get("tags"))
        print("\n✅ 全链路自测通过")
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
