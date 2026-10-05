"""Create narration and a source ledger only from the selected formal run."""
import json, sys, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'artifacts'/'competition_video_ghostqa'

def main():
    folder=OUT/'formal'
    identity=json.loads((folder/'run-identity.json').read_text(encoding='utf-8'))
    report=json.loads((folder/'report.json').read_text(encoding='utf-8'))
    events=json.loads((folder/'events.json').read_text(encoding='utf-8'))['events']
    first_step=next(e for e in events if e.get('type')=='step' and e.get('findings'))
    image_url=first_step['dst']['screenshot']
    urllib.request.urlretrieve(identity['base_url']+image_url,folder/'shots'/'tested_page.png')
    summary=report['summary']; rid=identity['run_id']
    n=summary['actions_executed']; states=summary['states_discovered']
    candidates=summary['candidate_findings']; confirmed=summary['confirmed_bugs']; calls=summary['llm_calls']
    if not report['bugs']: raise ValueError('Selected take has no confirmed report; cannot narrate a successful bug')
    bug=report['bugs'][0]; finding=bug['finding']; obs=finding['evidence']['obs']
    original=bug['original_length']; minimal=len(bug['reproduction'])
    from ghostqa.oracle.fingerprint import fingerprint_of
    fp=fingerprint_of(finding['kind'],finding['evidence'])
    real=any(e.get('decision',{}).get('model_used') is True and e.get('decision',{}).get('model_kind')=='real' for e in events)
    model_sentence=(f'这次运行有 {calls} 次真实模型调用，后续命中缓存的选择没有重复请求。'
      if real else '这次没有接入或触发真实模型慢路径，页面显示的程序评分仍然支撑完整流程。')
    path_sentence=(f'本次原始路径是 {original} 步，最小化后是 {minimal} 步。'
      + ('路径本身已经很短，这次没有进一步缩短。' if original==minimal else '每次接受删减，都必须再次通过同一指纹的重放。'))
    data=[
      ('intro',0,18,'从页面开始',[
       '传统自动化测试，需要人先写好点击路径。GhostQA 面对一个页面和业务规格，尝试自己选择操作，把值得复查的问题留下来。']),
      ('config',18,40,'配置一次真实任务',[
       '这里使用面板内置的购物车案例。目标页面、业务规格和六步预算已经填好，策略保持默认 Ghost，Mock 没有勾选。',
       '我们给出检查规则，接下来的点击路径没有提前写死。']),
      ('live',40,75,'一次连续真实运行',[
       '点击启动，让它自己跑完一次测试。左侧是执行器返回的页面截图，状态图和动作记录随着运行更新。',
       '我们用 Edge 展示面板；真正执行测试的，是服务器侧的 Playwright Chromium。探索结束后，还要继续完成重放和最小化。']),
      ('state_ai',75,105,'本次运行回看：状态与决策',[
       f'回看这次运行，实际执行了 {n} 个动作，形成 {states} 个状态。系统每执行一步，都重新读取页面元素和业务观测，用结构簇和语义变体记录状态身份。',
       '默认策略先按程序分数排序，满足门控条件才请模型重排少量候选。'+model_sentence]),
      ('candidate',105,130,'发现异常，不等于确认缺陷',[
       f'回到首次刷新合计的记录。页面商品金额是 {obs["cart_item_price"]}，总价却是 {obs["cart_total"]}。规格要求两者一致，因此 Oracle 记录了一条语义候选。',
       '但这里，还不能叫已确认缺陷。候选是检查发现的现象，是否能重新出现，要交给下一步验证。']),
      ('replay_min',130,160,'同指纹重放与路径最小化',[
       '系统从干净起点重新执行发现所在回合的动作前缀。只有相同缺陷指纹再次出现，重放才通过；它验证现象可复现，并不自动证明根因。',
       path_sentence+'更长路径会尝试删除动作，保留仍能重现的序列；ddmin 不保证全局最短。']),
      ('report',160,200,'打开同一次运行的报告',[
       '点击打开报告。这里保留了运行摘要、异常类型、现场观测、重放确认状态，以及可以重新执行的路径。每一项都来自刚才那次运行。',
       f'本次共有 {candidates} 个去重候选，{confirmed} 个已确认缺陷。未通过重放、重放未完成，是不同的证据状态，不能混入确认数量。',
       '报告里的总价和商品金额，来自页面可观测字段。业务判断依靠可执行规格，并不是让模型自由判断一切。']),
      ('mechanism',200,225,'探索与脚本测试的分工',[
       '脚本测试擅长验证已经知道的流程。这里的动作来自当前可执行元素，探索、异常检查和复现证据放在同一次测试中。',
       f'这个案例只有 {states} 个状态，能说明功能闭环，不能用来证明深层覆盖。没有业务规格时，也只能执行通用检查。']),
      ('research',225,245,'产品默认与研究候选分开',[
       '研究证据页单独保留版本和失败结果。部分候选得到 Outcome A，仍没有晋升为产品默认。',
       '已发表主要实验使用无模型或 Mock，不能据此宣称真实大模型收益。真实模型收益还需要独立评测。']),
      ('ending',245,260,'留下能走回来的路径',[
       'GhostQA 把页面探索、异常检查、重放确认和复现路径，放进一次测试流程。发现问题只是开始，问题必须走得回来。'])
    ]
    scenes=[]
    for sid,start,end,title,paragraphs in data:
        scenes.append({'id':sid,'start':start,'end':end,'title':title,'paragraphs':[
            {'display':p,'tts':p.replace('GhostQA','Ghost Q A').replace('Oracle','异常判定器').replace('ddmin','路径最小化').replace('Outcome A','A 类结论').replace('Mock','模拟模型')}
            for p in paragraphs]})
    script={'speaker':{'voice':'zh-CN-XiaoyiNeural','rate':'+4%','pitch':'+0Hz'},'duration':260,'run_id':rid,'source_sha':identity['source_sha'],'scenes':scenes}
    (OUT/'script.json').write_text(json.dumps(script,ensure_ascii=False,indent=2),encoding='utf-8')
    facts={'run_id':rid,'source_sha':identity['source_sha'],'base_url':identity['base_url'],'cfg':identity['cfg'],
        'action_count':n,'state_count':states,'candidate_count':candidates,'confirmed_count':confirmed,'llm_calls':calls,
        'real_model_evidence':real,'original_length':original,'minimal_length':minimal,'fingerprint':fp,'obs':obs,
        'notes':'All numbers are read from this formal run; no rehearsal numbers are imported.'}
    (OUT/'formal-facts.json').write_text(json.dumps(facts,ensure_ascii=False,indent=2),encoding='utf-8')
    md=['# GhostQA 最终口播','',f'目标提交：{identity["source_sha"]}',f'正式运行：{rid}',
        '录制浏览器为 Edge；测试执行器为服务器侧 Playwright Chromium。','']
    for s in scenes:
        md += [f'## {s["start"]:03d}–{s["end"]:03d} 秒　{s["title"]}','']+[p['display']+'\n' for p in s['paragraphs']]
    (OUT/'ghostqa_script_final.md').write_text('\n'.join(md),encoding='utf-8')
    shotlist=['# GhostQA 镜头清单','',f'正式 run_id：{rid}。启动到完成保留同一原始录屏；其后为同一记录的说明性回看。','',
        '|区间|画面|来源|','|---|---|---|']
    for s in scenes: shotlist.append(f'|{s["start"]}–{s["end"]} 秒|{s["title"]}|formal/{rid}；研究页仅为独立历史证据|')
    (OUT/'ghostqa_shotlist.md').write_text('\n'.join(shotlist),encoding='utf-8')
    print(json.dumps(facts,ensure_ascii=False))
    print('Narration characters',sum(len(p['display']) for s in scenes for p in s['paragraphs']))

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8'); main()
