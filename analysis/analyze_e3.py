# -*- coding: utf-8 -*-
"""실험 3 집계: 시행별 라운드 점수·회귀·비용 → data/e3_summary.json, data/scores_by_trial.csv(실험 1·3 원점수)
비용: cost.rounds()로 라운드를 나누고, 외부 중단(30분 초과 무기록 구간)은 소요 시간에서 제외한다
(실험 1의 E1_T_r2 처리와 같은 원칙).
"""
import json, os, sys, csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cost as C

sys.stdout.reconfigure(encoding='utf-8')
R = 'D:/claude/butterfly_mcp_paper'
GAP = 1800


def active_rounds(path):
    segs = C.rounds(path)
    # 라운드별로 30분 초과 무기록 구간을 빼기 위해 다시 읽는다
    bounds = [C.ts(s['start']) for s in segs] + [None]
    idle = [0.0] * len(segs)
    prev = None
    for line in open(path, encoding='utf-8'):
        try:
            d = json.loads(line)
        except Exception:
            continue
        if 'timestamp' not in d:
            continue
        t = C.ts(d['timestamp'])
        if prev is not None:
            g = (t - prev).total_seconds()
            if g > GAP:
                k = max(i for i in range(len(segs)) if bounds[i] <= prev) if any(b <= prev for b in bounds[:-1]) else None
                if k is not None:
                    idle[k] += g
        prev = t
    for s, i in zip(segs, idle):
        s['idle_excluded_s'] = round(i, 1)
        s['duration_active_s'] = round(s['duration_s'] - i, 1)
    return segs


def score(t, v):
    m = json.load(open('%s/data/%s_v%d.json' % (R, t, v), encoding='utf-8'))
    fails = sorted(k for k, x in m['checks'].items() if not x['pass'])
    return m['achievement']['pass'] + m['constraint']['pass'], m['achievement']['pass'], m['constraint']['pass'], fails


if __name__ == '__main__':
    A = json.load(open(R + '/logs/agents.json'))
    trials = {}
    for t in sorted(k for k in A if k.startswith('E3_')):
        vs = [v for v in range(3) if os.path.exists('%s/data/%s_v%d.json' % (R, t, v))]
        if not vs:
            continue
        rows = [score(t, v) for v in vs]
        regs = 0
        for a, b in zip(rows, rows[1:]):
            regs += len(set(b[3]) - set(a[3]))
        segs = active_rounds('%s/agent-%s.jsonl' % (C.TASKS, A[t]))
        rec = {'cond': t.split('_')[1], 'v': [{'total': r[0], 'ach': r[1], 'con': r[2], 'fails': r[3]} for r in rows],
               'first_total': rows[0][0], 'final_total': rows[-1][0],
               'all_pass_round': next((i for i, r in enumerate(rows) if r[0] == 30), None), 'n_regressions': regs,
               'cost_rounds': [{'duration_s': s['duration_active_s'], 'idle_excluded_s': s['idle_excluded_s'], 'tool_uses': s['tool_uses']} for s in segs]}
        rec['duration_first_s'] = rec['cost_rounds'][0]['duration_s']
        rec['tool_uses_first'] = rec['cost_rounds'][0]['tool_uses']
        rec['duration_total_s'] = round(sum(c['duration_s'] for c in rec['cost_rounds']), 1)
        rec['tool_uses_total'] = sum(c['tool_uses'] for c in rec['cost_rounds'])
        trials[t] = rec
        print(t, [r[0] for r in rows], 'reg', regs, 'cost', [(c['duration_s'], c['tool_uses'], c['idle_excluded_s']) for c in rec['cost_rounds']])
    json.dump({'trials': trials}, open(R + '/data/e3_summary.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    # 시행별 원점수표(실험 1·3)
    E1 = json.load(open(R + '/data/e1_summary.json', encoding='utf-8'))['trials']
    with open(R + '/data/scores_by_trial.csv', 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.writer(fh)
        w.writerow(['experiment', 'trial', 'condition', 'round0_total', 'round1_total', 'round2_total', 'final_total',
                    'round0_achievement', 'round0_constraint', 'regressions', 'duration_total_s', 'tool_uses_total', 'round0_failed_items'])
        for t, r in sorted(E1.items()):
            tot = [x['ach'] + x['con'] for x in r['v']]
            w.writerow(['E1', t, r['style'], *(tot + [''] * (3 - len(tot))), r['final_total'], r['v'][0]['ach'], r['v'][0]['con'],
                        r['n_regressions'], round(r['duration_total_s'], 1), r['tool_uses_total'],
                        ' '.join(r['v'][0].get('fails', [])) if isinstance(r['v'][0].get('fails'), list) else ''])
        for t, r in sorted(trials.items()):
            tot = [x['total'] for x in r['v']]
            w.writerow(['E3', t, r['cond'], *(tot + [''] * (3 - len(tot))), r['final_total'], r['v'][0]['ach'], r['v'][0]['con'],
                        r['n_regressions'], r['duration_total_s'], r['tool_uses_total'], ' '.join(f.split('_')[0] for f in r['v'][0]['fails'])])
    print('saved')
