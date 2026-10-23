# -*- coding: utf-8 -*-
"""실험 3 진행 도우미: 측정 결과 기록과 재작업 지시문 생성.
사용: python e3_run.py next   TRIAL ROUND TOKENS TOOLS DURATION_S "notes"
  → data/TRIAL_v{ROUND}.json 을 읽어 trials.jsonl 에 기록, 회귀 계산, 미충족이 있고 ROUND<2 이면 재작업 지시문 출력·저장
"""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import specs3 as S3
sys.stdout.reconfigure(encoding='utf-8')
R = 'D:/claude/butterfly_mcp_paper'


def failed_ids(t, v):
    m = json.load(open('%s/data/%s_v%d.json' % (R, t, v), encoding='utf-8'))
    ch = m['checks']
    fails = sorted({k.split('_')[0] for k, x in ch.items() if not x['pass']})
    return fails, m


if __name__ == '__main__':
    _, cmd, t, rnd, tok, tools, dur = sys.argv[:7]
    notes = sys.argv[7] if len(sys.argv) > 7 else ''
    rnd = int(rnd)
    cond = t.split('_')[1]
    fails, m = failed_ids(t, rnd)
    ach = m['achievement']['pass']; con = m['constraint']['pass']
    reg = []
    if rnd > 0:
        prev, _ = failed_ids(t, rnd - 1)
        reg = [f for f in fails if f not in prev]
    rec = {'trial': t, 'round': rnd, 'style': cond, 'tokens_cum' if rnd else 'tokens': int(tok),
           'tool_uses_cum' if rnd else 'tool_uses': int(tools), 'duration_s_cum' if rnd else 'duration_s': float(dur),
           'ach_pass': ach, 'con_pass': con, 'failed': fails, 'notes': notes}
    if rnd:
        rec['regressions'] = reg
    open(R + '/logs/trials.jsonl', 'a', encoding='utf-8').write(json.dumps(rec, ensure_ascii=False) + '\n')
    print('score', ach + con, '/30  failed', fails, 'regressions', reg)
    ids = S3.ids_from_failed_checks(['%s_x' % f for f in fails])
    if ids and rnd < 2:
        out = '%s/houdini/trials/%s_v%d.hip' % (R, t, rnd + 1)
        txt = S3.build_rework(cond, ids, out)
        open('%s/logs/%s_prompt_v%d.txt' % (R, t, rnd + 1), 'w', encoding='utf-8').write(txt)
        print('----REWORK----'); print(txt)
    else:
        print('----DONE----')
