"""Compose the multi-case GhostQA cut from one recorded run.

Reads artifacts/competition_video_ghostqa/multicase/ (recorded by
record_multicase.py) and script_multicase.json, draws the enlarged multi-node
state graph from the same run's graph.json, and muxes picture + Qwen voiceover.

Every number shown comes from the recorded run; nothing is taken from the
earlier cart-case video.
"""
from __future__ import annotations
import json, math, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'artifacts' / 'competition_video_ghostqa'
MC = OUT / 'multicase'
W, H = 1920, 1080
BG = '#F2EFE8'; PANEL = '#FBF9F4'; INK = '#2D2B27'; TEAL = '#0D6B66'; MUTED = '#6F6C64'
WARN = '#9A5B12'; RED = '#A33A2B'
FONT = 'C:/Windows/Fonts/msyh.ttc'
AUDIO = OUT / 'audio_qwen_multicase'
FINAL = OUT / 'ghostqa_final_multicase.mp4'
CLEAN = OUT / 'ghostqa_clean_capture_multicase.mp4'


def font(size):
    return ImageFont.truetype(FONT, size)


def text(draw, xy, message, size=34, fill=INK, width=None):
    x, y = xy; f = font(size)
    for line in message.split('\n'):
        chunks = ['']
        for c in line:
            if width and draw.textlength(chunks[-1] + c, font=f) > width:
                chunks.append(c)
            else:
                chunks[-1] += c
        for chunk in chunks:
            draw.text((x, y), chunk, font=f, fill=fill); y += int(size * 1.55)
    return y


def panel(im, box, title, lines, line_size=32, title_size=36):
    d = ImageDraw.Draw(im); x, y, x2, y2 = box
    d.rounded_rectangle(box, 14, fill=PANEL, outline='#D4D0C7', width=2)
    yy = text(d, (x + 28, y + 22), title, title_size, TEAL, width=x2 - x - 56)
    d.line((x + 28, yy + 10, x2 - 28, yy + 10), fill='#D4D0C7', width=2); yy += 35
    for line in lines:
        yy = text(d, (x + 28, yy), line, line_size, width=x2 - x - 56) + max(8, int(line_size * 0.40))
    if yy > y2 - 8:
        raise ValueError('Panel overflows: ' + title)
    return yy


def header(im, title, rid, review=True):
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 138), fill=PANEL)
    text(d, (42, 18), title, 44, TEAL)
    text(d, (44, 88), ('本次运行回看 · ' if review else '真实产品界面 · ') + rid + '  |  产品默认 Ghost', 24, MUTED)
    d.line((40, 137, W - 40, 137), fill='#D4D0C7', width=2)


def source(im, message):
    # Kept above the burned-in subtitle band: libass scales MarginV against a
    # 288-line script, so the subtitle sits roughly 100 px off the bottom.
    text(ImageDraw.Draw(im), (42, 928), message, 21, MUTED, width=1836)


def caption(im, message, y=900, size=26, fill=TEAL):
    text(ImageDraw.Draw(im), (42, y), message, size, fill, width=1836)


def probe(path):
    return json.loads(subprocess.check_output(
        ['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(path)], text=True))


def duration_seconds(path):
    meta = probe(path)
    if meta.get('format', {}).get('duration'):
        return float(meta['format']['duration'])
    raise ValueError('No duration for ' + str(path))


def short_name(url: str) -> str:
    tail = url.rstrip('/').split('/')[-1] or 'index.html'
    return tail


def capture_case_page(base: str) -> Path:
    """Screenshot the real builtin case catalog page for the catalog slide."""
    dst = OUT / 'edit_mc' / 'assets' / 'case_page.png'
    if dst.is_file():
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1280, 'height': 720}, device_scale_factor=1)
            page.goto(base + '/cases/index.html', wait_until='networkidle', timeout=30000)
            page.screenshot(path=str(dst))
            browser.close()
    except Exception as exc:  # keep the build moving; fall back to the dashboard shot
        print('CASE_PAGE_CAPTURE_SKIPPED', str(exc)[:200], flush=True)
        return MC / 'shots' / 'config.png'
    return dst


# ---------------------------------------------------------------- graph slide

BRANCH_ROWS = {'register': 280, 'script': 500, 'stock': 720}
INDEX_POS = (150, 500)
GRAPH_PANEL = (1420, 165, 1885, 830)


def _self_loop(d, c):
    """A loop that actually leaves and re-enters the node instead of floating."""
    cx, cy = c
    d.line((cx - 28, cy - 56, cx - 28, cy - 100), fill=TEAL, width=4)
    d.arc((cx - 28, cy - 128, cx + 28, cy - 72), 180, 360, fill=TEAL, width=4)
    d.line((cx + 28, cy - 100, cx + 28, cy - 64), fill=TEAL, width=4)
    d.polygon([(cx + 28, cy - 54), (cx + 19, cy - 72), (cx + 37, cy - 72)], fill=TEAL)


def _arrow(d, p1, p2, shrink=62):
    import math
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    dist = math.hypot(dx, dy) or 1
    ux, uy = dx / dist, dy / dist
    a = (p1[0] + ux * shrink, p1[1] + uy * shrink)
    b = (p2[0] - ux * shrink, p2[1] - uy * shrink)
    d.line((a[0], a[1], b[0], b[1]), fill=TEAL, width=4)
    tip = 16
    d.polygon([(b[0], b[1]), (b[0] - ux * tip - uy * tip * 0.6, b[1] - uy * tip + ux * tip * 0.6),
               (b[0] - ux * tip + uy * tip * 0.6, b[1] - uy * tip - ux * tip * 0.6)], fill=TEAL)
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def draw_graph(im, graph, rid):
    d = ImageDraw.Draw(im)
    node_list = graph['nodes']
    index_sig = node_list[0]['sig']
    pos = {index_sig: INDEX_POS}
    groups: dict[str, list] = {}
    for n in node_list[1:]:
        groups.setdefault(short_name(n['url']), []).append(n)
    for branch, row in BRANCH_ROWS.items():
        bucket = groups.get(branch + '.html', [])
        if len(bucket) == 1:
            xs = [(INDEX_POS[0] + GRAPH_PANEL[0]) / 2 + 120]
        elif bucket:
            lo, hi = 430, 1330
            step = (hi - lo) / (len(bucket) - 1)
            xs = [lo + step * i for i in range(len(bucket))]
        else:
            xs = []
        for node, x in zip(bucket, xs):
            pos[node['sig']] = (x, row)

    def centre(sig):
        return pos.get(sig, (960, 500))

    action_counts: dict[str, int] = {}
    for e in graph['edges']:
        action_counts[e['action_key']] = action_counts.get(e['action_key'], 0) + 1

    badges = []
    for e in graph['edges']:
        p1, p2 = centre(e['src']), centre(e['dst'])
        act = e.get('action') or {}
        if e['src'] == e['dst']:
            _self_loop(d, p1)
            continue
        _arrow(d, p1, p2)
        if action_counts[e['action_key']] == 1 and act.get('type') == 'click' and act.get('target_eid'):
            t = 0.45
            bx = p1[0] + (p2[0] - p1[0]) * t
            by = p1[1] + (p2[1] - p1[1]) * t
            dx, dy = p2[0] - p1[0], p2[1] - p1[1]
            length = math.hypot(dx, dy) or 1
            px, py = -dy / length, dx / length
            if py > 0:
                px, py = -px, -py
            badges.append((bx + px * 32, by + py * 32, act['target_eid'], e['count']))

    for n in node_list:
        cx, cy = centre(n['sig'])
        r = 62
        fill = '#E4F0EE' if n['relation'] != 'new' else PANEL
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fill, outline=TEAL, width=5)
        label = short_name(n['url']).replace('.html', '')
        text(d, (cx - r + 10, cy - 16), label, 24, TEAL, width=r * 2 - 20)
        text(d, (cx - r - 30, cy + r + 10),
             f"{n['relation']} · step {n.get('first_seen_step', '—')}", 19, MUTED, width=200)

    legend = []
    for index, (bx, by, name, count) in enumerate(badges, 1):
        d.ellipse((bx - 17, by - 17, bx + 17, by + 17), fill=TEAL)
        text(d, (bx - 10, by - 15), str(index), 20, PANEL)
        legend.append(f"{index}   {name}" + (f"   ×{count}" if count > 1 else ''))

    lines = [f"节点：{len(graph['nodes'])} 个",
             f"边：{len(graph['edges'])} 条",
             '起点：案例目录页 index',
             '分支：注册 · 结算 · 库存', '']
    if legend:
        lines += ['关键边：'] + legend + ['']
    lines += ['结构簇相同、业务观测变体',
              '不同 → 标记为 similar',
              '节点上的自环 = 回到已有变体']
    panel(im, GRAPH_PANEL, '这次不是两个节点', lines, line_size=22, title_size=31)


def make_assets(facts, events):
    dst = OUT / 'edit_mc' / 'assets'; dst.mkdir(parents=True, exist_ok=True)
    shots = MC / 'shots'; rid = facts['run_id']
    spec = json.loads((ROOT / 'apps' / 'builtin-cases' / 'spec.json').read_text(encoding='utf-8'))['assertions']
    graph = json.loads((MC / 'graph.json').read_text(encoding='utf-8'))
    bugs = facts['bugs']

    # --- opening title card ---------------------------------------------------
    im = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(im)
    d.rectangle((120, 400, 1800, 404), fill=TEAL)
    text(d, (120, 250), 'GhostQA', 150, TEAL)
    text(d, (126, 452), 'AI 驱动的自主探索式 Web 测试系统', 46, INK)
    text(d, (126, 528), '一次真实运行，从内置案例目录走进多个页面', 34, MUTED)
    text(d, (126, 600), f"正式运行 {rid} ｜ 产品默认 Ghost ｜ 30 步预算", 26, MUTED)
    source(im, '本片全部数字取自同一次真实运行；页面截图为该运行的界面回看。')
    im.save(dst / 'title_card.png')

    # --- builtin case catalog -------------------------------------------------
    im = Image.new('RGB', (W, H), BG); header(im, '内置案例目录：一套执行器，四条可执行规则', rid, review=False)
    page_img = Image.open(capture_case_page(facts['base_url'])).convert('RGB')
    crop = page_img.crop((0, 0, min(1000, page_img.width), min(700, page_img.height)))
    crop.thumbnail((900, 640)); im.paste(crop, (44, 200))
    caption(im, '真实案例目录页 · ' + facts['base_url'] + '/cases/index.html', y=860)
    spec_lines = []
    for a in spec:
        spec_lines.append(f"{a['id']}  ·  {a.get('severity', '')}")
        spec_lines.append('    ' + a.get('desc', ''))
    panel(im, (985, 178, 1878, 900), '规格文件 · apps/builtin-cases/spec.json',
          spec_lines + ['', '本次运行从该目录页出发，'], line_size=24, title_size=30)
    source(im, '来源：真实案例目录页截图与 spec.json；本次运行从该目录页出发。')
    im.save(dst / 'case_catalog.png')

    # --- run review: states and decisions -------------------------------------
    im = Image.new('RGB', (W, H), BG); header(im, '本次运行回看：状态与决策', rid)
    first = Image.open(shots / 'first_action.png').convert('RGB')
    crop = first.crop((16, 172, min(1172, first.width), min(827, first.height)))
    im.paste(crop.resize((1156, 655)), (36, 185))
    decision = next((e['decision'] for e in events if e.get('decision', {}).get('model_used')),
                    events[0].get('decision', {}))
    top = [f"{a['label']}   {a['score']:.2f}" for a in decision.get('top_k', [])][:3]
    panel(im, (1230, 185, 1878, 880), 'AI 观测 · 真实事件', [
        f"实际执行：{facts['action_count']} 动作 / {facts['state_count']} 状态",
        f"跨过页面：注册 · 结算 · 库存",
        f"真实模型调用：{facts['llm_calls']} 次",
        '候选动作评分：', *top,
        '程序评分先行，模型按需重排'], line_size=28)
    source(im, '来源：本次运行 multicase/events.json 与 graph.json；截图为同一运行的 UI 回看。')
    im.save(dst / 'state_ai.png')

    # --- enlarged state graph -------------------------------------------------
    im = Image.new('RGB', (W, H), BG); header(im, '把状态图单独放大', rid)
    draw_graph(im, graph, rid)
    source(im, '来源：本次运行 graph.json；节点、边与动作标签按真实记录绘制。')
    im.save(dst / 'graph_zoom.png')

    # --- oracle three layers --------------------------------------------------
    im = Image.new('RGB', (W, H), BG); header(im, '异常判定分三层', rid)
    panel(im, (45, 185, 930, 880), '硬信号层', [
        'L1 · 崩溃 / 脚本错误 / 白屏',
        'L2 · 无响应 / 导航循环 / 幂等过滤',
        '',
        '本层不依赖业务语义，',
        '先排掉一眼能看出的硬故障。'], line_size=29)
    panel(im, (985, 185, 1878, 880), '业务规格层 · L3', [
        '库存数 ≥ 0',
        '  页面显示 -1 → 断言不成立',
        '用户名为空 → 不能提示注册成功',
        '  页面提示“注册成功” → 断言不成立',
        '',
        '断言结果来自页面可观测字段，',
        '输出的是候选，不是结论。'], line_size=27)
    source(im, '来源：本次 multicase/events.json、spec.json、report.json；不展示模型内部思维过程。')
    im.save(dst / 'ai_oracle.png')

    # --- candidates are not confirmed defects ---------------------------------
    im = Image.new('RGB', (W, H), BG); header(im, '发现异常，不等于确认缺陷', rid)
    shot = Image.open(shots / 'confirmed_card.png').convert('RGB')
    crop = shot.crop((0, 120, min(1180, shot.width), min(900, shot.height)))
    crop.thumbnail((1120, 720)); im.paste(crop, (40, 190))
    lines = []
    for b in facts['candidates']:
        flag = {'semantic': '语义', 'js_error': '脚本', 'dead_action': '无响应'}.get(b['kind'], b['kind'])
        lines.append(f"{flag} · {b['severity']} · step {b['step_index']}")
        lines.append('  ' + b['description'].split('：')[-1][:22])
    panel(im, (1210, 178, 1878, 900), f"本次去重候选 {facts['candidate_count']} 条", lines, line_size=24)
    source(im, '来源：本次运行 multicase/candidates.json；候选是检查发现的现象，未通过重放前不计入确认。')
    im.save(dst / 'candidate.png')

    # --- replay + minimization ------------------------------------------------
    im = Image.new('RGB', (W, H), BG); header(im, '同指纹重放与路径最小化', rid)
    lines = ['重放起点：新的执行器，干净重置', '匹配条件：相同 BugFingerprint', '']
    for bug in bugs:
        f = bug['finding']
        lines.append(f"{f['kind']} · {f['description'].split('：')[-1][:16]}")
        lines.append(f"  原始 {bug['original_length']} 步 → 最小 {len(bug['reproduction'])} 步 · 已确认")
    panel(im, (45, 185, 1000, 900), '本次重放结果', lines, line_size=25)
    panel(im, (1055, 185, 1878, 900), '证据边界', [
        f"确认缺陷：{facts['confirmed_count']} 条",
        f"未通过重放：{facts['failed_count']} 条",
        f"重放未完成：{facts['unfinished_count']} 条",
        '',
        '重放证明现象可复现，',
        '不自动证明根因。',
        '路径最小化保留仍能重现的序列，',
        '不保证全局最短。'], line_size=28)
    source(im, '来源：本次运行 multicase/report.json 与 replay 事件；三类状态分开计数。')
    im.save(dst / 'replay_min.png')

    # --- research separation --------------------------------------------------
    res_shot = Image.open(shots / 'research.png').convert('RGB')
    panel(res_shot, (42, 218, 1010, 900), '产品默认与研究证据分开', [
        '产品默认：NoFrontier / sequence_mode=off',
        'v0.3.35：Outcome A；不晋升',
        'v0.3.36 / v0.3.37：Outcome C',
        'v0.3.38：Outcome A；不晋升',
        '主要已发表实验：NoLLM / Mock',
        '真实模型收益仍需独立评测'], line_size=27)
    source(res_shot, '来源：published 各版本 summary.md；历史实验不是本次运行的成绩。')
    res_shot.save(dst / 'research.png')

    # --- ending ---------------------------------------------------------------
    done = Image.open(shots / 'completed.png').convert('RGB')
    ending = Image.new('RGB', (W, H), BG)
    crop = done.crop((0, 0, min(done.width, 1280), min(done.height, 760)))
    crop.thumbnail((1080, 642)); ending.paste(crop, (42, 184))
    panel(ending, (1170, 184, 1878, 880), '这次运行的结论', [
        f"动作：{facts['action_count']}",
        f"状态：{facts['state_count']}（跨 4 个页面）",
        f"候选：{facts['candidate_count']}",
        f"确认：{facts['confirmed_count']}",
        'Explore → Replay → Minimize → Report',
        '问题必须走得回来。'], line_size=30)
    source(ending, '来源：本次 run_id ' + rid + ' 的 completed.png 与 report.json；仅作同一运行收尾回看。')
    ending.save(OUT / 'edit_mc' / 'assets' / 'ending.png')
    return dst


SOURCES = {
    'intro': ('still', MC / 'shots' / 'config.png'),
    'cases': ('still', None),
    'config': ('clip', None),
    'live': ('unit', None),
    'state_ai': ('still', None),
    'graph': ('still', None),
    'ai_oracle': ('still', None),
    'candidate': ('still', None),
    'replay_min': ('still', None),
    'report': ('report', None),
    'research': ('still', None),
    'ending': ('still', None),
}
ASSET_NAME = {'opening': 'title_card.png',
              'cases': 'case_catalog.png', 'state_ai': 'state_ai.png', 'graph': 'graph_zoom.png',
              'ai_oracle': 'ai_oracle.png', 'candidate': 'candidate.png',
              'replay_min': 'replay_min.png', 'research': 'research.png', 'ending': 'ending.png'}


def main():
    facts = json.loads((OUT / 'multicase-facts.json').read_text(encoding='utf-8'))
    events = json.loads((MC / 'events.json').read_text(encoding='utf-8'))
    if isinstance(events, dict):
        events = events.get('events', events)
    script = json.loads((OUT / 'script_multicase.json').read_text(encoding='utf-8'))
    duration_total = int(script['duration'])
    rv = json.loads((MC / 'report-video.json').read_text(encoding='utf-8'))
    video_file = MC / 'video.json'
    if video_file.is_file():
        v = json.loads(video_file.read_text(encoding='utf-8'))
    else:
        raise FileNotFoundError('multicase/video.json missing; recording did not flush')
    marks = {m['name']: m['seconds'] for m in v['marks']}
    raw = Path(v['path']); raw_duration = duration_seconds(raw)
    marks.setdefault('recording_end', raw_duration)
    offset = raw_duration - marks['recording_end']
    assets = make_assets(facts, events)
    edit = OUT / 'edit_mc'; edit.mkdir(exist_ok=True)

    overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(overlay)
    d.rounded_rectangle((56, 242, 1180, 500), 18, fill=(251, 249, 244, 242))
    text(d, (88, 263), 'GhostQA', 72, TEAL)
    text(d, (90, 370), 'AI 驱动的自主探索式 Web 测试系统', 34)
    text(d, (90, 424), '一次运行，从案例目录走进多个页面', 28, MUTED)
    overlay.save(edit / 'intro_overlay.png')

    paths = {sid: (kind, p) for sid, (kind, p) in SOURCES.items()}
    for sid, name in ASSET_NAME.items():
        paths[sid] = ('still', assets / name)
    paths['config'] = ('clip', raw)
    paths['live'] = ('unit', raw)
    paths['report'] = ('report', Path(rv['path']))

    timeline = []
    for scene in script['scenes']:
        sid = scene['id']; duration = scene['end'] - scene['start']
        kind, path = paths[sid]
        output = edit / (sid + '.mp4')
        cmd = ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error']
        start = 0.0; unit = None
        if kind == 'still':
            cmd += ['-loop', '1', '-framerate', '30', '-i', str(path)]
        elif kind == 'clip':
            start = marks['config'] + offset + 3
            cmd += ['-ss', str(max(0, start)), '-i', str(path)]
        elif kind == 'unit':
            start = marks['start_click'] + offset
            unit = marks['authentic_unit_end'] - marks['start_click']
            cmd += ['-ss', str(max(0, start)), '-i', str(path)]
        else:
            cmd += ['-i', str(path)]
        filters = ['scale=1920:1080']
        if kind == 'unit':
            if unit > duration + 1e-6:
                raise ValueError(f'Authenticity unit {unit:.1f}s exceeds scene {sid} {duration:.1f}s')
            filters += ['trim=duration=' + f'{unit:.3f}', 'setpts=PTS-STARTPTS',
                        'tpad=stop_mode=clone:stop_duration=' + f'{duration - unit:.3f}']
        elif kind != 'still':
            filters += ['tpad=stop_mode=clone:stop_duration=' + f'{duration:.3f}']
        filters += ['fps=30', 'setsar=1', 'format=yuv420p']
        if sid == 'intro':
            cmd += ['-i', str(edit / 'intro_overlay.png')]
            cmd += ['-filter_complex', '[0:v]' + ','.join(filters) + '[base];[base][1:v]overlay=0:0[v]', '-map', '[v]']
        else:
            cmd += ['-vf', ','.join(filters)]
        cmd += ['-t', f'{duration:.3f}', '-an', '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
                '-maxrate', '8M', '-bufsize', '16M', '-threads', '4', '-map_metadata', '-1', str(output)]
        subprocess.run(cmd, check=True)
        timeline.append({'scene': sid, 'start': scene['start'], 'end': scene['end'], 'kind': kind,
                         'source': str(path.relative_to(OUT)), 'source_start_seconds': start,
                         'run_id': None if sid == 'research' else facts['run_id'],
                         'authenticity_unit_seconds': unit})
        print('RENDERED', sid, flush=True)
    (OUT / 'edit_timeline_multicase.json').write_text(
        json.dumps({'offset_seconds': offset, 'scenes': timeline}, ensure_ascii=False, indent=2), encoding='utf-8')

    concat = edit / 'concat.txt'
    concat.write_text('\n'.join("file '" + s['id'] + ".mp4'" for s in script['scenes']), encoding='utf-8')
    subprocess.run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-f', 'concat', '-safe', '0',
                    '-i', str(concat), '-c', 'copy', '-map_metadata', '-1', str(edit / 'picture.mp4')], check=True)

    voiceover = AUDIO / 'voiceover.wav'
    subtitles = AUDIO / 'subtitles.srt'
    sub_rel = subtitles.relative_to(OUT).as_posix()
    sub_filter = ("subtitles=" + sub_rel + ":force_style='Fontname=Microsoft YaHei,Fontsize=10,"
                  "PrimaryColour=&H00272B2D,OutlineColour=&H00F4F9FB,BorderStyle=1,Outline=1,"
                  "Shadow=0,MarginV=8'")
    subprocess.run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-i', str(edit / 'picture.mp4'),
                    '-i', str(voiceover), '-vf', sub_filter, '-af', 'loudnorm=I=-16:TP=-1.5:LRA=7',
                    '-c:v', 'libx264', '-preset', 'fast', '-b:v', '6M', '-maxrate', '8M', '-bufsize', '16M',
                    '-threads', '4', '-c:a', 'aac', '-b:a', '160k', '-ar', '48000', '-pix_fmt', 'yuv420p',
                    '-r', '30', '-t', str(duration_total), '-map_metadata', '-1', '-map_chapters', '-1',
                    '-movflags', '+faststart', str(FINAL)], cwd=OUT, check=True)
    subprocess.run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-i', str(raw), '-an',
                    '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-r', '30', '-pix_fmt', 'yuv420p',
                    '-map_metadata', '-1', '-movflags', '+faststart', str(CLEAN)], check=True)
    print('EXPORT_COMPLETE', FINAL, flush=True)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
