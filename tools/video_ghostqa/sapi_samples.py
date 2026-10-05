"""Create local Windows SAPI Chinese voice samples for comparison."""
from __future__ import annotations
import json, subprocess, wave
from pathlib import Path
import win32com.client

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'artifacts'/'competition_video_ghostqa'/'voice_samples'
TEXT=("这是 Ghost Q A。我们给它一个页面和业务规格，接下来的动作由系统按当前状态选择。"
      "这里出现的是候选异常，还不能算确认缺陷。它要先回到干净起点，完整重放这段操作，"
      "再留下能复现的路径。")
VOICES={
    'H_huihui_sapi':'Microsoft Huihui Desktop',
    'I_kangkang_sapi':'Microsoft Kangkang Desktop',
    'J_yaoyao_sapi':'Microsoft Yaoyao Desktop',
}

def probe(path):
    return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(path)],text=True))

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    voice=win32com.client.Dispatch('SAPI.SpVoice')
    stream=win32com.client.Dispatch('SAPI.SpFileStream')
    stream.Format.Type=22
    available=[]
    for token in voice.GetVoices():
        available.append(str(token.GetDescription()))
    rows=[]
    for stem,name in VOICES.items():
        match=next((t for t in voice.GetVoices() if name.lower() in str(t.GetDescription()).lower()),None)
        if match is None:
            continue
        voice.Voice=match
        path=OUT/(stem+'.wav')
        stream.Open(str(path),3,False)
        voice.AudioOutputStream=stream
        voice.Speak(TEXT)
        stream.Close()
        voice.AudioOutputStream=None
        info=probe(path)
        rows.append({'sample':stem,'voice':str(match.GetDescription()),'path':str(path),
                     'duration_seconds':float(info['format']['duration']),'ffprobe':info})
    (OUT/'sapi_manifest.json').write_text(json.dumps({'text':TEXT,'available':available,'samples':rows},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for r in rows: print(f"{r['sample']}: {r['voice']} {r['duration_seconds']:.3f}s",flush=True)
    if not rows: raise RuntimeError('No requested SAPI voice was available')

if __name__=='__main__': main()
