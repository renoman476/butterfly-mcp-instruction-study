# -*- coding: utf-8 -*-
"""실험 2 집계: 수정 범위(R1~R3) × 보존 조항(P+/P-)."""
import json, os, glob, sys, statistics as st

ROOT = 'D:/claude/butterfly_mcp_paper'
RN = {'R1': 'R1 나비 국소(hover 연장)', 'R2': 'R2 소녀 국소(손가락)', 'R3': 'R3 모호한 범위(장난스럽게)'}
PN = {'Pp': '보존 조항 명시(P+)', 'Pm': '미명시(P−)'}
cost = json.load(open(ROOT + '/data/cost.json', encoding='utf-8'))

rows = []
for p in sorted(glob.glob(ROOT + '/data/E2_*_eval.json')):
    e = json.load(open(p, encoding='utf-8'))
    t = e['trial']; _, r, pc, rep = t.split('_')
    c = e['collateral']
    seg = cost.get(t, [{}])[0]
    rows.append({'trial': t, 'R': r, 'P': pc, 'target': e['target']['pass'], 'preserved': e['preserved'],
                 'path_rms_cm': c['butterfly_rms_cm'], 'path_max_cm': c['butterfly_max_cm'], 'flap_rms': c['flap_rms_deg'],
                 'landing_shift': (c['landing_rev'] or 0) - (c['landing_ref'] or 0), 'head_deg': c['head_mean_deg'],
                 'hands_cm': c['left_hand_rms_cm'] + c['right_hand_rms_cm'], 'cams': c['camera_parms_changed'],
                 'regressions': e['regressions'], 'n_reg': len(e['regressions']),
                 'duration_s': seg.get('duration_s'), 'tool_uses': seg.get('tool_uses'), 'tvals': e['target']})

L = ['# 실험 2 결과 표 (자동 생성)', '']
L.append('## 표 6. 시행별 결과')
L.append('')
L.append('| 시행 | 목표 달성 | 구간 밖 나비 경로 RMS / 최대 (cm) | 날갯짓 RMS (°) | 착지 판정 변화 | 소녀·카메라 변화 | 30항목 회귀 | 소요(초) / 도구 |')
L.append('|---|---|---|---|---|---|---|---|')
for r in rows:
    L.append('| %s | %s | %.2f / %.2f | %.1f | %+d | %s | %s | %s / %s |' % (
        r['trial'], 'O' if r['target'] else 'X', r['path_rms_cm'], r['path_max_cm'], r['flap_rms'], r['landing_shift'],
        '없음' if r['head_deg'] == 0 and r['hands_cm'] == 0 and r['cams'] == 0 else '있음',
        ', '.join(x.split('_')[0] for x in r['regressions']) or '-', r['duration_s'], r['tool_uses']))
L.append('')
L.append('## 표 7. 조건별 요약 (n=2)')
L.append('')
L.append('| 수정 범위 | 보존 조항 | 목표 달성 | 보존 기준 충족 | 구간 밖 경로 RMS (cm) | 회귀 수 | 소요(초) |')
L.append('|---|---|---|---|---|---|---|')
summary = {}
for R in ('R1', 'R2', 'R3'):
    for P in ('Pp', 'Pm'):
        g = [r for r in rows if r['R'] == R and r['P'] == P]
        if not g:
            continue
        s = {'target': sum(r['target'] for r in g), 'preserved': sum(r['preserved'] for r in g),
             'path': st.mean(r['path_rms_cm'] for r in g), 'reg': st.mean(r['n_reg'] for r in g),
             'dur': st.mean(r['duration_s'] for r in g if r['duration_s'] is not None), 'n': len(g)}
        summary[R + P] = s
        L.append('| %s | %s | %d/%d | %d/%d | %.2f | %.1f | %.0f |' % (RN[R], PN[P], s['target'], s['n'], s['preserved'], s['n'], s['path'], s['reg'], s['dur']))
L.append('')
pp = [r for r in rows if r['P'] == 'Pp']; pm = [r for r in rows if r['P'] == 'Pm']
L.append('## 표 8. 보존 조항 주효과')
L.append('')
L.append('| 조건 | 목표 달성 | 보존 기준 충족 | 구간 밖 경로 RMS 평균 (cm) | 회귀 시행 수 | 소요 평균(초) |')
L.append('|---|---|---|---|---|---|')
for name, g in (('P+', pp), ('P−', pm)):
    L.append('| %s | %d/%d | %d/%d | %.2f | %d/%d | %.0f |' % (name, sum(r['target'] for r in g), len(g), sum(r['preserved'] for r in g), len(g),
             st.mean(r['path_rms_cm'] for r in g), sum(1 for r in g if r['n_reg']), len(g), st.mean(r['duration_s'] for r in g)))
L.append('')
L.append('## 회귀 항목 유형')
L.append('')
from collections import Counter
cnt = Counter(x for r in rows for x in r['regressions'])
for k, v in cnt.most_common():
    L.append('- %s: %d건 (%s)' % (k, v, ', '.join(r['trial'] for r in rows if k in r['regressions'])))
open(ROOT + '/results/e2_tables.md', 'w', encoding='utf-8').write('\n'.join(L))
json.dump({'rows': rows, 'summary': summary}, open(ROOT + '/data/e2_summary.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
sys.stdout.reconfigure(encoding='utf-8')
print('\n'.join(L))
