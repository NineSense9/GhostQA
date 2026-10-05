"""Build the longer, explanation-first narration timeline."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "competition_video_ghostqa"


NEW = {
    "cases": {
        "title": "规格目录：同一套执行器可以换规则",
        "start": 24,
        "end": 56,
        "paragraphs": [
            {
                "display": "先看它到底在测什么。规格文件里是四条可执行规则：购物车总价必须等于商品金额之和，库存不能为负，空用户名不能提示注册成功，未登录不能展示个人中心内容。",
                "tts": "先看它到底在测什么。规格文件里是四条可执行规则：购物车总价必须等于商品金额之和，库存不能为负，空用户名不能提示注册成功，未登录不能展示个人中心内容。",
            },
            {
                "display": "本次正式运行选择第一条购物车规则。其它三条只作为内置案例目录，说明同一个执行器可以换页面和规格；它们没有被混入本次成绩。",
                "tts": "本次正式运行选择第一条购物车规则。其它三条只作为内置案例目录，说明同一个执行器可以换页面和规格；它们没有被混入本次成绩。",
            },
        ],
    },
    "graph": {
        "title": "把状态图单独放大",
        "start": 120,
        "end": 160,
        "paragraphs": [
            {
                "display": "把刚才缩小的状态图单独放大。图里只有两个节点，但节点身份不只看网址：同一购物车页面的结构簇相同，业务观测变体不同，所以关系记为 SIMILAR。",
                "tts": "把刚才缩小的状态图单独放大。图里只有两个节点，但节点身份不只看网址：同一购物车页面的结构簇相同，业务观测变体不同，所以关系记为相似。",
            },
            {
                "display": "第一条边是点击刷新合计。后续回到同一个变体的动作会被记录成回边。图节点、动作和页面观测一起留在运行文件里，评委可以按同一条边回看截图。",
                "tts": "第一条边是点击刷新合计。后续回到同一个变体的动作会被记录成回边。图节点、动作和页面观测一起留在运行文件里，评委可以按同一条边回看截图。",
            },
        ],
    },
    "ai_oracle": {
        "title": "动作选择和异常判定各有边界",
        "start": 160,
        "end": 200,
        "paragraphs": [
            {
                "display": "动作怎么选？程序先给当前候选动作打分。遇到新状态或规格相关页面，再打开模型门控。本次前两次真的调用了模型，后面命中缓存，直接沿程序路径继续。",
                "tts": "动作怎么选？程序先给当前候选动作打分。遇到新状态或规格相关页面，再打开模型门控。本次前两次真的调用了模型，后面命中缓存，直接沿程序路径继续。",
            },
            {
                "display": "异常判定分三层。L1 和 L2 先处理崩溃、白屏、无响应和导航循环等硬信号。L3 执行规格断言，本例用页面观测比较商品金额 5 和总价 12，最后才产生语义候选。",
                "tts": "异常判定分三层。L1 和 L2 先处理崩溃、白屏、无响应和导航循环等硬信号。L3 执行规格断言，本例用页面观测比较商品金额 5 和总价 12，最后才产生语义候选。",
            },
        ],
    },
}


def main() -> None:
    original = json.loads((OUT / "script.json").read_text(encoding="utf-8"))
    scenes_by_id = {scene["id"]: scene for scene in original["scenes"]}
    extended_order = ["intro", "cases", "config", "live", "state_ai", "graph", "ai_oracle",
                      "candidate", "replay_min", "report", "mechanism", "research", "ending"]
    durations = {
        "intro": (0, 24), "cases": (24, 56), "config": (56, 80), "live": (80, 120),
        "state_ai": (120, 145), "graph": (145, 185), "ai_oracle": (185, 225),
        "candidate": (225, 260), "replay_min": (260, 300), "report": (300, 345),
        "mechanism": (345, 375), "research": (375, 395), "ending": (395, 410),
    }
    scenes = []
    for scene_id in extended_order:
        scene = dict(NEW[scene_id]) if scene_id in NEW else dict(scenes_by_id[scene_id])
        start, end = durations[scene_id]
        scene["id"] = scene_id
        scene["start"], scene["end"] = start, end
        scenes.append(scene)
    output = {
        "speaker": original["speaker"],
        "duration": 410,
        "run_id": original["run_id"],
        "source_sha": original["source_sha"],
        "scenes": scenes,
        "notes": [
            "The cart case is the only formal run. The other builtin rules are shown as a specification catalog.",
            "All formal run metrics remain from run_id 66026146.",
        ],
    }
    (OUT / "script_extended.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", OUT / "script_extended.json")


if __name__ == "__main__":
    main()
