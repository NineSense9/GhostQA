"""Compose original GhostQA footage and explicitly labeled same-run review."""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'artifacts'/'competition_video_ghostqa'
W,H=1920,1080
BG='#F2EFE8'; PANEL='#FBF9F4'; INK='#2D2B27'; TEAL='#0D6B66'; MUTED='#6F6C64'
FONT='C:/Windows/Fonts/msyh.ttc'

def probe(path):
    return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(path)],text=True))
def duration_seconds(path):
    metadata = probe(path)
    duration = metadata.get('format', {}).get('duration')
    if duration:
        return float(duration)
    stream = next((item for item in metadata.get('streams', []) if item.get('codec_type') == 'video'),
                  metadata.get('streams', [{}])[0])
    rate = stream.get('avg_frame_rate') or stream.get('r_frame_rate') or '0/1'
    numerator, denominator = (float(part) for part in rate.split('/', 1))
    if denominator == 0 or numerator == 0:
        raise ValueError(f'Cannot infer frame rate for {path}')
    frames = stream.get('nb_read_frames')
    if not frames:
        counted = json.loads(subprocess.check_output([
            'ffprobe', '-v', 'error', '-count_frames',
            '-show_entries', 'stream=nb_read_frames,avg_frame_rate,r_frame_rate',
            '-of', 'json', str(path)], text=True))
        counted_stream = next((item for item in counted.get('streams', [])
                               if item.get('codec_type') == 'video'), counted.get('streams', [{}])[0])
        frames = counted_stream.get('nb_read_frames')
        rate = counted_stream.get('avg_frame_rate') or counted_stream.get('r_frame_rate') or rate
        numerator, denominator = (float(part) for part in rate.split('/', 1))
    if not frames or denominator == 0 or numerator == 0:
        raise ValueError(f'Cannot infer duration for {path}')
    return float(frames) * denominator / numerator
def font(size): return ImageFont.truetype(FONT,size)
def text(draw, xy, message, size=34, fill=INK, width=None):
    x,y=xy; f=font(size)
    for line in message.split('\n'):
        chunks=[''];
        for c in line:
            if width and draw.textlength(chunks[-1]+c,font=f)>width: chunks.append(c)
            else: chunks[-1]+=c
        for chunk in chunks:
            draw.text((x,y),chunk,font=f,fill=fill); y+=int(size*1.55)
    return y
def panel(im,box,title,lines,line_size=32):
    d=ImageDraw.Draw(im); x,y,x2,y2=box
    d.rounded_rectangle(box,14,fill=PANEL,outline='#D4D0C7',width=2)
    yy=text(d,(x+28,y+22),title,36,TEAL,width=x2-x-56)
    d.line((x+28,yy+10,x2-28,yy+10),fill='#D4D0C7',width=2); yy+=35
    for line in lines: yy=text(d,(x+28,yy),line,line_size,width=x2-x-56)+max(10, int(line_size * 0.45))
    if yy>y2-12: raise ValueError('Panel overflows: '+title)
def header(im,title,rid,review=True):
    d=ImageDraw.Draw(im)
    d.rectangle((0,0,W,138),fill=PANEL)
    text(d,(42,18),title,44,TEAL)
    text(d,(44,88),('本次运行回看 · ' if review else '真实产品界面 · ')+rid+'  |  产品默认 Ghost',24,MUTED)
    d.line((40,137,W-40,137),fill='#D4D0C7',width=2)
def source(im,message): text(ImageDraw.Draw(im),(42,910),message,22,MUTED,width=1836)
def make_assets(facts,events):
    dst=OUT/'edit'/'assets'; dst.mkdir(parents=True,exist_ok=True)
    shots=OUT/'formal'/'shots'; rid=facts['run_id']; s=Image.open(shots/'first_action.png').convert('RGB')
    im=Image.new('RGB',(W,H),BG); header(im,'页面观测 → 状态身份 → 下一动作',rid)
    cropped=s.crop((16,172,1172,827)); im.paste(cropped.resize((1156,655)),(36,185))
    decision=next((e['decision'] for e in events if e.get('decision',{}).get('model_used')),events[0].get('decision',{}))
    top=[f"{a['label']}   {a['score']:.2f}" for a in decision.get('top_k',[])][:3]
    panel(im,(1230,185,1878,840),'AI 观测 · 真实事件',[
        f"本次实际：{facts['action_count']} 动作 / {facts['state_count']} 状态",
        f"真实模型参与：{'是' if facts['real_model_evidence'] else '否'}",
        f"模型评分调用：{facts['llm_calls']} 次",'候选语义分数：',*top,'程序评分先行，模型按需重排'])
    source(im,'来源：正式运行 events.json / graph.json；截图为同一运行的 UI 回看。')
    im.save(dst/'state_ai.png')
    im=Image.new('RGB',(W,H),BG); header(im,'发现异常，不等于确认缺陷',rid)
    shot=Image.open(shots/'tested_page.png').convert('RGB')
    crop=shot.crop((0,0,min(720,shot.width),min(440,shot.height)))
    crop.thumbnail((1120,690)); im.paste(crop,(55,220))
    d=ImageDraw.Draw(im); text(d,(58,690),'Candidate ≠ Confirmed',56,TEAL)
    obs=facts['obs']
    panel(im,(1200,190,1878,860),'首次异常步骤 · 页面值',[
        '期望：商品金额之和 = 总价',f"商品金额：{obs['cart_item_price']}",f"页面总价：{obs['cart_total']}",
        'L3：可执行规格断言不成立','输出：语义候选','这一刻的发现尚未通过重放'])
    source(im,'来源：首次候选 step 的页面截图、页面观测与 spec.json；这是发现时刻的证据回看。')
    im.save(dst/'candidate.png')
    im=Image.new('RGB',(W,H),BG); header(im,'干净重置 → 同指纹重放 → ddmin',rid)
    panel(im,(42,190,948,860),'已记录的验证结果',[
        '重放起点：新的执行器，干净重置','匹配条件：相同 BugFingerprint',f"本例缺陷指纹：{facts['fingerprint']}",
        '确认依据：报告 confirmed = true','重放证明现象，不自动证明根因'])
    minima=[e for e in events if e.get('type')=='minimize']
    panel(im,(976,190,1878,860),'路径与真实测试记录',[
        f"原始路径：{facts['original_length']} 步",f"最小路径：{facts['minimal_length']} 步",
        f"本次最小化测试：{len(minima)} 次",'记录结果：'+' / '.join(e['result'] for e in minima),
        '接受删减：目标指纹重放 PASS','边界：非空路径；不保证全局最短'])
    source(im,'来源：本次 report.json、phase / minimize 事件；指纹由目标提交的统一函数计算。')
    im.save(dst/'replay_min.png')
    im=Image.open(shots/'research.png').convert('RGB');
    panel(im,(42,175,982,875),'产品默认与研究证据分开',[
        '产品默认：NoFrontier / sequence_mode=off','v0.3.35：Outcome A；不晋升',
        'v0.3.36 / v0.3.37：Outcome C','v0.3.38：Outcome A；不晋升',
        '主要已发表实验：NoLLM / Mock','真实模型收益仍需独立评测'])
    source(im,'来源：published 各版本 summary.md；历史实验不是本次运行的成绩。')
    im.save(dst/'research.png')
    # The final frame is derived from the completed same-run UI capture and
    # keeps the close explicit without introducing synthetic product evidence.
    im=Image.open(shots/'completed.png').convert('RGB')
    ending=Image.new('RGB',(W,H),BG)
    crop=im.crop((0,0,min(im.width,1280),min(im.height,760)))
    crop.thumbnail((1080,642))
    ending.paste(crop,(42,184))
    panel(ending,(1170,184,1878,820),'这次运行的结论',[ 
        '候选：1 条',
        '确认：1 条',
        f"原始路径：{facts['original_length']} 步",
        f"最小路径：{facts['minimal_length']} 步",
        'Explore → Replay → Minimize → Report',
        '问题必须走得回来。'])
    source(ending,'来源：正式 run_id '+rid+' 的 completed.png、report.json；仅作同一运行收尾回看。')
    ending.save(OUT/'formal'/'shots'/'ending.png')
    # Extended cut: show the real builtin specification catalog and enlarge
    # the two-node graph that is difficult to read in the live dashboard.
    spec=json.loads((ROOT/'apps'/'builtin-cases'/'spec.json').read_text(encoding='utf-8'))
    im=Image.new('RGB',(W,H),BG); header(im,'规格目录：页面规则可以执行',rid)
    config=Image.open(shots/'config.png').convert('RGB')
    crop=config.crop((1110,160,1910,860)); crop.thumbnail((760,660)); im.paste(crop,(42,190))
    panel(im,(850,185,1878,875),'内置规格 · apps/builtin-cases/spec.json',[
        '本次正式运行：购物车总价不一致',
        'case_cart_total_consistent  ·  high',
        '总价 = 商品金额之和',
        'case_stock_non_negative  ·  medium',
        '库存数 ≥ 0',
        'case_register_requires_username  ·  high',
        '用户名为空 → 不能提示注册成功',
        'case_login_gate  ·  high',
        '未登录 → 不展示个人中心内容',
        '本页展示规则目录，其它三条未计入本次 run_id 成绩'], line_size=27)
    source(im,'来源：真实 spec.json 与正式运行配置截图；目录案例不是本次运行结果。')
    im.save(dst/'case_catalog.png')

    graph=json.loads((OUT/'formal'/'graph.json').read_text(encoding='utf-8'))
    im=Image.new('RGB',(W,H),BG); header(im,'把状态图单独放大',rid)
    d=ImageDraw.Draw(im)
    left=(350,430); right=(1440,430)
    d.line((left[0]+95,left[1],right[0]-95,right[1]),fill=TEAL,width=7)
    d.polygon([(right[0]-115,right[1]-18),(right[0]-80,right[1]),(right[0]-115,right[1]+18)],fill=TEAL)
    for center,label,relation,variant in [(left,'S0 · NEW','起点','6fa334108cc7'),(right,'S1 · SIMILAR','刷新后','94e045e9375c')]:
        d.ellipse((center[0]-95,center[1]-95,center[0]+95,center[1]+95),fill=PANEL,outline=TEAL,width=7)
        text(d,(center[0]-55,center[1]-28),label,32,TEAL,width=220)
        text(d,(center[0]-120,center[1]+120),relation,28,MUTED,width=260)
        text(d,(center[0]-210,center[1]+140),'cluster 7e1d07ef407a5c97',22,MUTED,width=420)
        text(d,(center[0]-210,center[1]+175),'variant '+variant,22,MUTED,width=420)
    text(d,(700,350),'click:btn_refresh',36,TEAL,width=480)
    panel(im,(55,650,1865,880),'图的含义',[
        '同一 URL，结构簇相同，业务观测变体不同 → SIMILAR。',
        'graph.json：2 个节点、3 条边；刷新与 back 形成回边。',
        '节点、动作和页面观测可以按边回看。'], line_size=16)
    source(im,'来源：正式 run_id '+rid+' 的 graph.json / events.json；节点和边按真实记录绘制。')
    im.save(dst/'graph_zoom.png')

    im=Image.new('RGB',(W,H),BG); header(im,'动作选择和异常判定各有边界',rid)
    panel(im,(45,185,930,860),'动作选择 · 真实事件',[ 
        '程序先计算候选动作分数',
        '刷新合计：0.90',
        'back：0.10',
        '模型门控：前 2 次触发',
        '缓存命中：后续 4 次',
        '最终动作由当前页面和策略决定'])
    d=ImageDraw.Draw(im)
    panel(im,(985,185,1878,860),'Oracle 三层判定',[ 
        'L1 · 硬异常',
        '崩溃、脚本错误、白屏',
        'L2 · 结构异常',
        '无响应、导航循环、幂等过滤',
        'L3 · 业务规格',
        '商品金额 5 ≠ 页面总价 12',
        '输出：semantic candidate',
        'Candidate 仍需 Replay 才能 Confirm'])
    d.line((120,905,1800,905),fill='#D4D0C7',width=2)
    source(im,'来源：正式 events.json、spec.json 和 report.json；不展示模型内部思维过程。')
    im.save(dst/'ai_oracle.png')
    return dst

def main():
    facts=json.loads((OUT/'formal-facts.json').read_text(encoding='utf-8'))
    events=json.loads((OUT/'formal'/'events.json').read_text(encoding='utf-8'))['events']
    script_path = OUT/'script_extended.json'
    if not script_path.is_file():
        script_path = OUT/'script.json'
    script=json.loads(script_path.read_text(encoding='utf-8'))
    duration_seconds_total = int(script.get('duration', 260))
    rv=json.loads((OUT/'formal'/'report-video.json').read_text(encoding='utf-8'))
    video_file=OUT/'formal'/'video.json'
    if video_file.is_file():
        v=json.loads(video_file.read_text(encoding='utf-8'))
    else:
        # The headed recorder was interrupted while closing the browser, so
        # its sidecar did not flush. Recover the same-run marks and select the
        # larger WebM, excluding the separate report review capture.
        marks_file=OUT/'formal'/'capture-marks.json'
        marks_data=json.loads(marks_file.read_text(encoding='utf-8'))
        report_raw=Path(rv['path']).resolve()
        raw_candidates=[path for path in (OUT/'formal'/'raw').glob('*.webm')
                        if path.resolve() != report_raw]
        if not raw_candidates:
            raise FileNotFoundError('No formal raw WebM capture found')
        raw_path=max(raw_candidates,key=lambda path:path.stat().st_size)
        v={'path':str(raw_path),'marks':marks_data}
    marks={m['name']:m['seconds'] for m in v['marks']}
    raw=Path(v['path']); raw_duration=duration_seconds(raw)
    marks.setdefault('recording_end',raw_duration)
    offset=raw_duration-marks['recording_end']
    assets=make_assets(facts,events)
    edit=OUT/'edit'; edit.mkdir(exist_ok=True)
    overlay=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(overlay)
    d.rounded_rectangle((56,242,1080,475),18,fill=(251,249,244,242))
    text(d,(88,263),'GhostQA',72,TEAL); text(d,(90,370),'AI 驱动的自主探索式 Web 测试系统',34)
    overlay.save(edit/'intro_overlay.png')
    sources={
        'intro':('still',OUT/'formal'/'shots'/'config.png',0,None),
        'cases':('still',assets/'case_catalog.png',0,None),
        'config':('clip',raw,marks['config']+offset+3,None),
        'live':('unit',raw,marks['start_click']+offset,marks['authentic_unit_end']-marks['start_click']),
        'state_ai':('still',assets/'state_ai.png',0,None),
        'graph':('still',assets/'graph_zoom.png',0,None),
        'ai_oracle':('still',assets/'ai_oracle.png',0,None),
        'candidate':('still',assets/'candidate.png',0,None),
        'replay_min':('still',assets/'replay_min.png',0,None),
        'report':('report',Path(rv['path']),0,None),
        'mechanism':('clip',raw,marks['restored_same_run']+offset,None),
        'research':('still',assets/'research.png',0,None),
        'ending':('still',OUT/'formal'/'shots'/'ending.png',0,None)}
    timeline=[]
    for scene in script['scenes']:
        sid=scene['id']; duration=scene['end']-scene['start']; kind,path,start,unit=sources[sid]
        output=edit/(sid+'.mp4')
        cmd=['ffmpeg','-y','-hide_banner','-loglevel','error']
        if kind=='still': cmd+=['-loop','1','-framerate','30','-i',str(path)]
        else: cmd+=['-ss',str(max(0,start)),'-i',str(path)]
        filters=[]
        if kind=='report': filters+=['scale=1920:1080']
        else: filters+=['scale=1920:1080']
        if kind=='unit':
            if unit>duration: raise ValueError('Authenticity unit exceeds scene; enlarge timeline instead of truncating')
            filters+=['trim=duration='+str(unit),'setpts=PTS-STARTPTS','tpad=stop_mode=clone:stop_duration='+str(duration-unit)]
        elif kind not in ['still']: filters+=['tpad=stop_mode=clone:stop_duration='+str(duration)]
        filters+=['fps=30','setsar=1','format=yuv420p']
        if sid=='intro':
            cmd+=['-i',str(edit/'intro_overlay.png')]
            cmd+=['-filter_complex','[0:v]'+','.join(filters)+'[base];[base][1:v]overlay=0:0[v]','-map','[v]']
        else: cmd+=['-vf',','.join(filters)]
        cmd+=['-t',str(duration),'-an','-c:v','libx264','-preset','fast','-crf','18','-maxrate','8M','-bufsize','16M','-threads','4','-map_metadata','-1',str(output)]
        subprocess.run(cmd,check=True)
        timeline.append({'scene':sid,'start':scene['start'],'end':scene['end'],'kind':kind,
                         'source':str(path.relative_to(OUT)),'source_start_seconds':start,'run_id':facts['run_id'] if sid!='research' else None,
                         'authenticity_unit_seconds':unit})
        print('RENDERED',sid,flush=True)
    (OUT/'edit_timeline.json').write_text(json.dumps({'offset_seconds':offset,'scenes':timeline},ensure_ascii=False,indent=2),encoding='utf-8')
    concat=edit/'concat.txt'; concat.write_text('\n'.join("file '"+s['id']+".mp4'" for s in script['scenes']),encoding='utf-8')
    subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error','-f','concat','-safe','0','-i',str(concat),'-c','copy','-map_metadata','-1',str(edit/'picture.mp4')],check=True)
    # Relative paths avoid Windows drive-letter escaping in the subtitle filter.
    voiceover = OUT/'audio_qwen_extended'/'voiceover.wav' if (OUT/'audio_qwen_extended'/'voiceover.wav').is_file() else OUT/'ghostqa_voiceover.wav'
    subtitles_file = OUT/'audio_qwen_extended'/'subtitles.srt' if (OUT/'audio_qwen_extended'/'subtitles.srt').is_file() else OUT/'ghostqa_subtitles.srt'
    subtitle_path = subtitles_file.relative_to(OUT).as_posix()
    subtitle=f"subtitles={subtitle_path}:force_style='Fontname=Microsoft YaHei,Fontsize=10,PrimaryColour=&H00272B2D,OutlineColour=&H00F4F9FB,BorderStyle=1,Outline=1,Shadow=0,MarginV=28'"
    subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error','-i',str(edit/'picture.mp4'),'-i',str(voiceover),
        '-vf',subtitle,'-af','loudnorm=I=-16:TP=-1.5:LRA=7','-c:v','libx264','-preset','fast','-b:v','6M','-maxrate','8M','-bufsize','16M',
        '-threads','4','-c:a','aac','-b:a','160k','-ar','48000','-pix_fmt','yuv420p','-r','30','-t',str(duration_seconds_total),'-map_metadata','-1','-map_chapters','-1','-movflags','+faststart',str(OUT/'ghostqa_final_extended.mp4')],cwd=OUT,check=True)
    # The entire formal capture remains available separately, without captions or narration.
    subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error','-i',str(raw),'-an','-c:v','libx264','-preset','fast','-crf','18','-r','30','-pix_fmt','yuv420p','-map_metadata','-1','-movflags','+faststart',str(OUT/'ghostqa_clean_capture_extended.mp4')],check=True)
    import shutil
    shutil.copy2(voiceover, OUT/'ghostqa_voiceover_extended.wav')
    shutil.copy2(subtitles_file, OUT/'ghostqa_subtitles_extended.srt')
    print('EXPORT_COMPLETE',flush=True)

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8'); main()
