# -*- coding: utf-8 -*-
"""실험 1 집계·통계 분석.
입력: data/E1_*_v*.json (측정), data/cost.json (라운드별 비용), logs/trials.jsonl (회귀·메모)
출력: data/e1_summary.json, results/e1_tables.md, results/fig_*.png
"""
import json, os, glob, sys, statistics as st
from scipy import stats

ROOT = 'D:/claude/butterfly_mcp_paper'
STYLES = ['N', 'T', 'Q', 'M']
SNAME = {'N': '서술형', 'T': '기술형', 'Q': '수치형', 'M': '혼합형'}
SENSITIVE = {'B09_prelanding_calm', 'G02_gaze_lag'}
os.makedirs(ROOT + '/results', exist_ok=True)


def load(trial, v):
    p = '%s/data/%s_v%d.json' % (ROOT, trial, v)
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else None


def score(r, exclude=()):
    ach = [k for k, c in r['checks'].items() if c['type'] == 'achievement' and k not in exclude]
    con = [k for k, c in r['checks'].items() if c['type'] == 'constraint' and k not in exclude]
    return (sum(r['checks'][k]['pass'] for k in ach), len(ach),
            sum(r['checks'][k]['pass'] for k in con), len(con))


def fails(r):
    return {k for k, c in r['checks'].items() if not c['pass']}


cost = json.load(open(ROOT + '/data/cost.json', encoding='utf-8')) if os.path.exists(ROOT + '/data/cost.json') else {}

trials = {}
for s in STYLES:
    for n in (1, 2, 3):
        t = 'E1_%s_r%d' % (s, n)
        vs = [load(t, v) for v in (0, 1, 2)]
        vs = [x for x in vs if x]
        if not vs:
            continue
        rec = {'style': s, 'rounds': len(vs) - 1}
        rec['v'] = []
        prev = None
        for i, r in enumerate(vs):
            a, an, c, cn = score(r)
            a2, an2, c2, cn2 = score(r, SENSITIVE)
            f = fails(r)
            reg = sorted((f - prev)) if prev is not None else []
            rec['v'].append({'ach': a, 'con': c, 'total': a + c, 'ach_ex': a2, 'con_ex': c2, 'n_ex': an2 + cn2,
                             'fails': sorted(f), 'regressions': reg})
            prev = f
        rec['first_total'] = rec['v'][0]['total']
        rec['final_total'] = rec['v'][-1]['total']
        rec['all_pass_round'] = next((i for i, x in enumerate(rec['v']) if x['total'] == 30), None)
        rec['n_regressions'] = sum(len(x['regressions']) for x in rec['v'])
        segs = cost.get(t, [])
        rec['cost_rounds'] = [{'duration_s': s_['duration_s'], 'tool_uses': s_['tool_uses'], 'houdini_calls': s_['houdini_calls']} for s_ in segs]
        rec['duration_total_s'] = sum(x['duration_s'] for x in rec['cost_rounds'])
        rec['tool_uses_total'] = sum(x['tool_uses'] for x in rec['cost_rounds'])
        rec['duration_first_s'] = rec['cost_rounds'][0]['duration_s'] if segs else None
        rec['tool_uses_first'] = rec['cost_rounds'][0]['tool_uses'] if segs else None
        trials[t] = rec


def desc(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return '-'
    m = st.mean(xs)
    sd = st.stdev(xs) if len(xs) > 1 else 0.0
    return '%.1f ± %.1f' % (m, sd)


by = {s: [r for r in trials.values() if r['style'] == s] for s in STYLES}

lines = ['# 실험 1 결과 표 (자동 생성)', '']
lines.append('## 표 1. 문체별 요구사항 충족 (30개 항목: 달성 23 + 제약 7, 평균 ± 표준편차, n=3)')
lines.append('')
lines.append('| 문체 | 1차 충족 | 1차 달성(/23) | 1차 제약(/7) | 최종 충족 | 1차 전 항목 통과 | 재작업 라운드 | 회귀 수 |')
lines.append('|---|---|---|---|---|---|---|---|')
for s in STYLES:
    R = by[s]
    lines.append('| %s | %s | %s | %s | %s | %d/%d | %s | %s |' % (
        SNAME[s], desc([r['first_total'] for r in R]), desc([r['v'][0]['ach'] for r in R]), desc([r['v'][0]['con'] for r in R]),
        desc([r['final_total'] for r in R]), sum(1 for r in R if r['all_pass_round'] == 0), len(R),
        desc([r['rounds'] for r in R]), desc([r['n_regressions'] for r in R])))
lines.append('')

lines.append('## 표 2. 문체별 비용 (1차 / 전체)')
lines.append('')
lines.append('| 문체 | 1차 소요(초) | 1차 도구 호출 | 전체 소요(초) | 전체 도구 호출 |')
lines.append('|---|---|---|---|---|')
for s in STYLES:
    R = by[s]
    lines.append('| %s | %s | %s | %s | %s |' % (SNAME[s], desc([r['duration_first_s'] for r in R]), desc([r['tool_uses_first'] for r in R]),
                                              desc([r['duration_total_s'] for r in R]), desc([r['tool_uses_total'] for r in R])))
lines.append('')

# 통계: 1차 충족 Kruskal-Wallis, N vs Q/M Mann-Whitney (참고)
groups = [[r['first_total'] for r in by[s]] for s in STYLES]
try:
    H, p = stats.kruskal(*groups)
except ValueError:
    H, p = float('nan'), float('nan')
n_all = sum(len(g) for g in groups)
eps2 = (H - len(groups) + 1) / (n_all - len(groups)) if n_all > len(groups) else float('nan')
groups_ex = [[r['v'][0]['ach_ex'] + r['v'][0]['con_ex'] for r in by[s]] for s in STYLES]
try:
    H2, p2 = stats.kruskal(*groups_ex)
except ValueError:
    H2, p2 = float('nan'), float('nan')
nq = [r['first_total'] for s in ('Q', 'M') for r in by[s]]
nt = [r['first_total'] for s in ('N', 'T') for r in by[s]]
U, pu = stats.mannwhitneyu(nq, nt, alternative='greater')
lines.append('## 표 3. 통계 검정 (1차 충족 점수)')
lines.append('')
lines.append('| 검정 | 통계량 | p | 비고 |')
lines.append('|---|---|---|---|')
lines.append('| Kruskal–Wallis (4문체) | H = %.2f | %.3f | ε² = %.2f |' % (H, p, eps2))
lines.append('| Kruskal–Wallis (B09·G02 제외 28항목) | H = %.2f | %.3f | 민감도 분석 |' % (H2, p2))
lines.append('| Mann–Whitney (수치 포함 Q+M > 미포함 N+T) | U = %.1f | %.4f | 단측, n=6 vs 6 |' % (U, pu))
lines.append('')

# 항목별 1차 실패 빈도
items = sorted({k for r in trials.values() for k in load(list(trials)[0], 0)['checks']})
lines.append('## 표 4. 항목별 1차 실패 빈도 (문체당 3시행 중)')
lines.append('')
lines.append('| 항목 | ' + ' | '.join(SNAME[s] for s in STYLES) + ' |')
lines.append('|---|' + '---|' * len(STYLES))
item_fail = {}
for k in items:
    row = [sum(1 for r in by[s] if k in r['v'][0]['fails']) for s in STYLES]
    item_fail[k] = row
    if sum(row):
        lines.append('| %s | %s |' % (k, ' | '.join(str(x) for x in row)))
lines.append('')

# 최종 미해결 항목
lines.append('## 표 5. 최종(재작업 후) 미해결 항목')
lines.append('')
lines.append('| 시행 | 최종 충족 | 미해결 항목 | 회귀 |')
lines.append('|---|---|---|---|')
for t, r in sorted(trials.items()):
    regs = [x for v in r['v'] for x in v['regressions']]
    lines.append('| %s | %d/30 | %s | %s |' % (t, r['final_total'], ', '.join(x.split('_')[0] for x in r['v'][-1]['fails']) or '-', ', '.join(x.split('_')[0] for x in regs) or '-'))
lines.append('')

open(ROOT + '/results/e1_tables.md', 'w', encoding='utf-8').write('\n'.join(lines))
json.dump({'trials': trials, 'kruskal': [H, p, eps2], 'kruskal_ex': [H2, p2], 'mwu': [U, pu], 'item_fail': item_fail},
          open(ROOT + '/data/e1_summary.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
sys.stdout.reconfigure(encoding='utf-8')
print('\n'.join(lines))
