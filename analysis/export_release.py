# -*- coding: utf-8 -*-
"""공개 저장소용 재현 자료 패키지(release/) 생성.
- 원본 에이전트 작업 기록에는 실행 환경의 계정 정보가 포함되므로 공개하지 않고,
  지시문·도구 호출·도구 결과·보고문만 추린 정제본(transcripts/*.jsonl)을 만든다.
- 정제본에서 사용자 홈 경로는 <HOME>으로 바꾸고, 이메일 형태 문자열이 남아 있으면 중단한다.
"""
import json, os, re, shutil, glob, sys

sys.stdout.reconfigure(encoding='utf-8')
R = 'D:/claude/butterfly_mcp_paper'
OUT = R + '/release'
SUB = '<HOME>/.claude/projects/D--claude/df5309fc-0c6a-46cf-b68b-67c8f02294a0/subagents'
HOME_PAT = re.compile(r'C:[\\/]+Users[\\/]+Pro', re.I)
EMAIL_PAT = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
EMAIL_OK = {'noreply@anthropic.com'}


def clean(s):
    return HOME_PAT.sub('<HOME>', s)


def text_of(c):
    if isinstance(c, str):
        return c
    out = []
    for b in c or []:
        if isinstance(b, dict):
            if b.get('type') == 'text':
                out.append(b.get('text', ''))
            elif b.get('type') == 'tool_result':
                cc = b.get('content')
                out.append(cc if isinstance(cc, str) else ' '.join(x.get('text', '') for x in (cc or []) if isinstance(x, dict) and x.get('type') == 'text'))
    return '\n'.join(out)


def export_transcript(trial, aid):
    recs, prompts = [], []
    for line in open('%s/agent-%s.jsonl' % (SUB, aid), encoding='utf-8'):
        d = json.loads(line)
        if d.get('type') not in ('user', 'assistant'):
            continue
        m = d.get('message') or {}
        c = m.get('content')
        ts = d.get('timestamp')
        if d['type'] == 'user':
            if isinstance(c, list) and any(isinstance(b, dict) and b.get('type') == 'tool_result' for b in c):
                for b in c:
                    if isinstance(b, dict) and b.get('type') == 'tool_result':
                        t = text_of([b])
                        recs.append({'ts': ts, 'kind': 'tool_result', 'id': b.get('tool_use_id'), 'text': clean(t[:4000]) + (' …[truncated]' if len(t) > 4000 else '')})
            else:
                t = text_of(c)
                if t.startswith('<') and 'system-reminder' in t[:40]:
                    continue
                recs.append({'ts': ts, 'kind': 'instruction', 'text': clean(t)})
                prompts.append(clean(t))
        else:
            for b in c or []:
                if not isinstance(b, dict):
                    continue
                if b.get('type') == 'text' and b.get('text', '').strip():
                    recs.append({'ts': ts, 'kind': 'assistant_text', 'text': clean(b['text'])})
                elif b.get('type') == 'tool_use':
                    recs.append({'ts': ts, 'kind': 'tool_use', 'id': b.get('id'), 'name': b.get('name'), 'input': json.loads(clean(json.dumps(b.get('input'), ensure_ascii=False)))})
    return recs, prompts


if __name__ == '__main__':
    if os.path.exists(OUT):
        keep = OUT + '/README.md'
        readme = open(keep, encoding='utf-8').read() if os.path.exists(keep) else None
        shutil.rmtree(OUT)
        os.makedirs(OUT)
        if readme:
            open(keep, 'w', encoding='utf-8').write(readme)
    for d in ('prompts', 'transcripts', 'specs', 'data/measure', 'analysis', 'houdini/trials', 'mcp_server', 'logs'):
        os.makedirs(OUT + '/' + d, exist_ok=True)
    A = json.load(open(R + '/logs/agents.json'))
    for t, aid in sorted(A.items()):
        recs, prompts = export_transcript(t, aid)
        with open('%s/transcripts/%s.jsonl' % (OUT, t), 'w', encoding='utf-8') as fh:
            for r in recs:
                fh.write(json.dumps(r, ensure_ascii=False) + '\n')
        with open('%s/prompts/%s.txt' % (OUT, t), 'w', encoding='utf-8') as fh:
            for i, p in enumerate(prompts):
                fh.write('===== 입력 %d =====\n%s\n\n' % (i, p))
    for f in glob.glob(R + '/specs/*.txt'):
        shutil.copy(f, OUT + '/specs/')
    for f in ('specs.py', 'specs2.py', 'specs3.py'):
        shutil.copy(R + '/analysis/' + f, OUT + '/specs/')
    for f in glob.glob(R + '/data/E[123]_*.json') + glob.glob(R + '/data/reference_measure.json') + glob.glob(R + '/data/base_measure.json'):
        shutil.copy(f, OUT + '/data/measure/')
    for f in ('e1_summary.json', 'e2_summary.json', 'e3_summary.json', 'scores_by_trial.csv', 'stats_exact.json', 'selfcheck.json',
              'selfcheck_reports.json', 'hover_final.json', 'hover_final_all.json', 'hover_heights.json', 'cost.json'):
        if os.path.exists(R + '/data/' + f):
            shutil.copy(R + '/data/' + f, OUT + '/data/')
    for f in ('measure.py', 'measure2.py', 'e2_eval.py', 'cost.py', 'analyze_e1.py', 'analyze_e2.py', 'analyze_e3.py', 'stats_exact.py',
              'selfcheck.py', 'hover_heights.py', 'e3_run.py', 'build_reference.py', 'make_figs.py', 'make_figs_rev.py', 'export_release.py'):
        shutil.copy(R + '/analysis/' + f, OUT + '/analysis/')
    for f in ('base_scene.hip', 'reference.hip'):
        shutil.copy(R + '/houdini/' + f, OUT + '/houdini/')
    for f in glob.glob(R + '/houdini/trials/*.hip'):
        shutil.copy(f, OUT + '/houdini/trials/')
    shutil.copy('D:/claude/houdini_mcp/houdini_mcp_server.py', OUT + '/mcp_server/')
    shutil.copytree('D:/claude/houdini_mcp/houdini', OUT + '/mcp_server/houdini', ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree('D:/claude/houdini_mcp/tests', OUT + '/mcp_server/tests', ignore=shutil.ignore_patterns('__pycache__'))
    for f in ('trials.jsonl', 'decisions.md', 'run_conditions.json', 'E1_order.json', 'E2_order.json', 'E3_order.json'):
        if os.path.exists(R + '/logs/' + f):
            shutil.copy(R + '/logs/' + f, OUT + '/logs/')
    # 공개 전 점검: 이메일·사용자 경로
    bad = []
    for root, _, files in os.walk(OUT):
        for f in files:
            if f.endswith(('.hip',)):
                continue
            s = open(os.path.join(root, f), encoding='utf-8', errors='ignore').read()
            for e in set(EMAIL_PAT.findall(s)) - EMAIL_OK:
                bad.append((f, e))
            if HOME_PAT.search(s):
                bad.append((f, 'HOME path'))
    print('issues', bad[:20], len(bad))
