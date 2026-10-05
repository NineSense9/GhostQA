"""Build the multi-case narration timeline for the GhostQA demo video.

The narration is written once, with run metrics injected from a facts file so
the spoken numbers can only ever come from the recorded run. Scene bounds are
estimated here; run with --fit after Qwen TTS to replace them with exact audio
durations plus a fixed pause.

Usage:
  python tools/video_ghostqa/build_multicase_script.py            # write text
  python tools/video_ghostqa/build_multicase_script.py --fit      # fit to audio
"""
from __future__ import annotations

import argparse
import json
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'artifacts' / 'competition_video_ghostqa'
SCRIPT = OUT / 'script_multicase.json'
AUDIO = OUT / 'audio_qwen_multicase'
FACTS = OUT / 'multicase-facts.json'
PAUSE = 1.2
# Scenes whose picture is a continuous capture can be longer than their narration.
# The live scene must fully contain start_click -> replay handover.
MIN_SECONDS = {'live': 37.0}
MAX_TOTAL = 297.0


def narration(f: dict) -> list[dict]:
    """Scene table. Only metrics from the recorded run are interpolated."""
    a, st, ca, cf, llm = (f['action_count'], f['state_count'],
                          f['candidate_count'], f['confirmed_count'], f['llm_calls'])
    edges = f['edge_count']
    return [
        {
            'id': 'opening', 'title': '开场',
            'paragraphs': [
                {'display': '下面演示 GhostQA 的一次完整测试流程。它是一个自主探索式的 Web 测试系统。',
                 'tts': '下面演示 Ghost Q A 的一次完整测试流程。它是一个自主探索式的 Web 测试系统。'},
            ],
        },
        {
            'id': 'intro', 'title': '从页面开始',
            'paragraphs': [
                {'display': '传统自动化测试，需要人先写好点击路径。GhostQA 面对一个页面和业务规格，尝试自己选择操作，把值得复查的问题留下来。',
                 'tts': '传统自动化测试，需要人先写好点击路径。Ghost Q A 面对一个页面和业务规格，尝试自己选择操作，把值得复查的问题留下来。'},
            ],
        },
        {
            'id': 'cases', 'title': '内置案例目录：一套执行器，多条规则',
            'paragraphs': [
                {'display': '先看它到底在测什么。内置案例目录里放着注册、结算、库存和购物车几个页面，规格文件里对应四条可执行规则。',
                 'tts': '先看它到底在测什么。内置案例目录里放着注册、结算、库存和购物车几个页面，规格文件里对应四条可执行规则。'},
                {'display': '购物车总价必须等于商品金额之和；库存数不能为负；用户名为空不能提示注册成功；未登录不能展示个人中心内容。这一次，探索器从目录页自己起跑。',
                 'tts': '购物车总价必须等于商品金额之和；库存数不能为负；用户名为空不能提示注册成功；未登录不能展示个人中心内容。这一次，探索器从目录页自己起跑。'},
            ],
        },
        {
            'id': 'config', 'title': '配置一次真实任务',
            'paragraphs': [
                {'display': '面板里选择内置案例目录。目标页面是案例目录页，规格文件是内置案例规格，预算三十步，策略保持默认 Ghost，Mock 没有勾选。',
                 'tts': '面板里选择内置案例目录。目标页面是案例目录页，规格文件是内置案例规格，预算三十步，策略保持默认 Ghost，模拟模型 没有勾选。'},
                {'display': '我们只给出检查规则，接下来的点击路径没有提前写死。',
                 'tts': '我们只给出检查规则，接下来的点击路径没有提前写死。'},
            ],
        },
        {
            'id': 'live', 'title': '一次连续真实运行',
            'paragraphs': [
                {'display': '点击启动，让它自己跑完这次探索。左侧是执行器返回的页面截图，状态图和动作记录随着运行更新。',
                 'tts': '点击启动，让它自己跑完这次探索。左侧是执行器返回的页面截图，状态图和动作记录随着运行更新。'},
                {'display': '我们用 Edge 展示面板，真正执行测试的，是服务器侧的 Playwright Chromium。探索从案例目录页出发，自己决定先进入哪个页面。',
                 'tts': '我们用 Edge 展示面板，真正执行测试的，是服务器侧的 Playwright Chromium。探索从案例目录页出发，自己决定先进入哪个页面。'},
            ],
        },
        {
            'id': 'state_ai', 'title': '本次运行回看：状态与决策',
            'paragraphs': [
                {'display': f'回看这次运行，实际执行了 {a} 个动作，形成 {st} 个状态，跨过注册、结算和库存几个页面。每执行一步，都重新读取页面元素和业务观测，用结构簇和语义变体记录状态身份。',
                 'tts': f'回看这次运行，实际执行了 {a} 个动作，形成 {st} 个状态，跨过注册、结算和库存几个页面。每执行一步，都重新读取页面元素和业务观测，用结构簇和语义变体记录状态身份。'},
                {'display': f'动作选择上，程序先给候选动作打分，遇到新状态或规格相关页面，再打开模型门控。这次运行有 {llm} 次真实模型调用，其余选择命中缓存。',
                 'tts': f'动作选择上，程序先给候选动作打分，遇到新状态或规格相关页面，再打开模型门控。这次运行有 {llm} 次真实模型调用，其余选择命中缓存。'},
            ],
        },
        {
            'id': 'graph', 'title': '把状态图单独放大',
            'paragraphs': [
                {'display': f'把刚才缩小的状态图单独放大。这一次不是两个节点，而是 {st} 个节点、{edges} 条边，从案例目录页连到它自己走进去的几个页面。',
                 'tts': f'把刚才缩小的状态图单独放大。这一次不是两个节点，而是 {st} 个节点、{edges} 条边，从案例目录页连到它自己走进去的几个页面。'},
                {'display': '节点身份不只看网址：结构簇相同、业务观测变体不同就记为相似，回到已有变体的动作记录成回边。节点、动作和页面观测一起留在运行文件里。',
                 'tts': '节点身份不只看网址：结构簇相同、业务观测变体不同就记为相似，回到已有变体的动作记录成回边。节点、动作和页面观测一起留在运行文件里。'},
            ],
        },
        {
            'id': 'ai_oracle', 'title': '异常判定分三层',
            'paragraphs': [
                {'display': '异常判定分三层。L1 和 L2 先处理崩溃、白屏、无响应和导航循环这些硬信号。',
                 'tts': '异常判定分三层。L1 和 L2 先处理崩溃、白屏、无响应和导航循环这些硬信号。'},
                {'display': 'L3 执行规格断言。本例里库存数被页面显示为负数，与规格冲突；注册页用户名为空却提示注册成功，同样由断言判定，然后才产生语义候选。',
                 'tts': 'L3 执行规格断言。本例里库存数被页面显示为负数，与规格冲突；注册页用户名为空却提示注册成功，同样由断言判定，然后才产生语义候选。'},
            ],
        },
        {
            'id': 'candidate', 'title': '发现异常，不等于确认缺陷',
            'paragraphs': [
                {'display': f'这次运行留下 {ca} 个去重候选，分别落在注册、结算和库存三个页面上：空用户名仍然提示注册成功，价格计算脚本报错、支付按钮点击没有反应，库存数显示为负数。',
                 'tts': f'这次运行留下 {ca} 个去重候选，分别落在注册、结算和库存三个页面上：空用户名仍然提示注册成功，价格计算脚本报错、支付按钮点击没有反应，库存数显示为负数。'},
                {'display': '它们现在还只是候选，是检查发现的现象。能不能重新出现，要交给重放验证。',
                 'tts': '它们现在还只是候选，是检查发现的现象。能不能重新出现，要交给重放验证。'},
            ],
        },
        {
            'id': 'replay_min', 'title': '同指纹重放与路径最小化',
            'paragraphs': [
                {'display': '系统从干净起点重新执行发现所在回合的动作前缀，只有相同缺陷指纹再次出现，重放才通过。它验证现象可复现，不自动证明根因。',
                 'tts': '系统从干净起点重新执行发现所在回合的动作前缀，只有相同缺陷指纹再次出现，重放才通过。它验证现象可复现，不自动证明根因。'},
                {'display': f'{ca} 个候选里，{cf} 个通过重放确认，最短的复现路径只有两步：打开注册页，点击提交。路径最小化会尝试删除动作，保留仍能重现的序列，不保证全局最短。',
                 'tts': f'{ca} 个候选里，{cf} 个通过重放确认，最短的复现路径只有两步：打开注册页，点击提交。路径最小化会尝试删除动作，保留仍能重现的序列，不保证全局最短。'},
            ],
        },
        {
            'id': 'report', 'title': '打开同一次运行的报告',
            'paragraphs': [
                {'display': '点击打开报告。运行摘要、异常类型、现场观测、重放确认状态和可以重新执行的路径都在这里，每一项都来自刚才那次运行。',
                 'tts': '点击打开报告。运行摘要、异常类型、现场观测、重放确认状态和可以重新执行的路径都在这里，每一项都来自刚才那次运行。'},
                {'display': f'本次 {ca} 个候选，{cf} 个已确认缺陷。未通过重放和重放未完成，是不同的证据状态，不能混入确认数量。',
                 'tts': f'本次 {ca} 个候选，{cf} 个已确认缺陷。未通过重放和重放未完成，是不同的证据状态，不能混入确认数量。'},
            ],
        },
        {
            'id': 'research', 'title': '产品默认与研究候选分开',
            'paragraphs': [
                {'display': '研究证据页单独保留版本和失败结果：部分候选得到 Outcome A，仍没有晋升为产品默认。已发表主要实验使用无模型或 Mock，不能据此宣称真实大模型收益。',
                 'tts': '研究证据页单独保留版本和失败结果：部分候选得到 A 类结论，仍没有晋升为产品默认。已发表主要实验使用无模型或 模拟模型，不能据此宣称真实大模型收益。'},
            ],
        },
        {
            'id': 'ending', 'title': '留下能走回来的路径',
            'paragraphs': [
                {'display': 'GhostQA 把页面探索、异常检查、重放确认和复现路径放进一次测试流程。脚本测试验证已知流程，探索测试负责找出还没被写下来的问题。问题必须走得回来。',
                 'tts': 'Ghost Q A 把页面探索、异常检查、重放确认和复现路径放进一次测试流程。脚本测试验证已知流程，探索测试负责找出还没被写下来的问题。问题必须走得回来。'},
            ],
        },
    ]


def audio_seconds(path: Path) -> float:
    with wave.open(str(path), 'rb') as w:
        return w.getnframes() / w.getframerate()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--fit', action='store_true', help='set scene bounds from TTS audio')
    args = ap.parse_args()
    facts = json.loads(FACTS.read_text(encoding='utf-8'))
    scenes = narration(facts)

    if args.fit:
        cursor = 0.0
        for index, scene in enumerate(scenes, 1):
            total = 0.0
            for pindex, _ in enumerate(scene['paragraphs'], 1):
                wav = AUDIO / 'paragraphs' / f'scene_{index:02d}_paragraph_{pindex:02d}.wav'
                total += audio_seconds(wav)
            audio_total = total
            total += PAUSE * len(scene['paragraphs'])
            total = max(total, MIN_SECONDS.get(scene['id'], 0.0))
            total = round(total, 2)
            start = round(cursor, 2)
            end = round(cursor + total, 2)
            scene['start'], scene['end'] = start, end
            scene['audio_seconds'] = round(audio_total, 2)
            cursor = end
        duration = int(round(cursor))
        if duration > MAX_TOTAL:
            raise SystemExit(
                f'Narration does not fit {MAX_TOTAL:.0f}s (would be {duration}s); '
                'shorten a paragraph before generating audio.')
        duration += 2
    else:
        for scene in scenes:
            scene['start'], scene['end'] = 0, 10
        duration = 300

    output = {
        'speaker': {'provider': 'Xiaomi MiMo TTS (OpenAI-compatible)',
                    'model': 'mimo-v2.5-tts-voicedesign',
                    'voice': '',
                    'language': 'Chinese / 中文',
                    'instruct': ('三十五岁左右的男性新闻播音员，普通话标准，声音沉稳干净，中低音区，'
                                 '吐字清晰，语速平稳，语调平直克制，无情绪起伏，适合电视新闻联播播报。'),
                    'rate': 'default', 'pitch': 'default'},
        'duration': duration,
        'run_id': facts['run_id'],
        'source_sha': facts['source_sha'],
        'scenes': scenes,
        'notes': [
            'A single run started from the builtin case catalog visits several cases.',
            'Every metric and defect in this narration is read from the recorded run.',
        ],
    }
    SCRIPT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('wrote', SCRIPT, 'duration', duration)
    if args.fit:
        for scene in scenes:
            print(f"  {scene['id']:11s} {scene['start']:>6} -> {scene['end']:>6}"
                  f"  audio {scene['audio_seconds']:>5}")


if __name__ == '__main__':
    main()
