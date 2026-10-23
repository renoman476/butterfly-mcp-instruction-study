# -*- coding: utf-8 -*-
"""실험 2 시행 1건 평가: 국소 비교(measure2) + 30개 항목 재측정(measure) + 회귀 산출.
Houdini 안에서: exec(open(PATH).read(), ns); ns['evaluate']('E2_R1_Pm_r1')
"""
import json

D = 'D:/claude/butterfly_mcp_paper/'


def evaluate(trial):
    rcode = trial.split('_')[1]
    ns, ms = {}, {}
    exec(open(D + 'analysis/measure2.py', encoding='utf-8').read(), ns)
    exec(open(D + 'analysis/measure.py', encoding='utf-8').read(), ms)
    hip = D + 'houdini/trials/%s.hip' % trial
    c = ns['compare'](D + 'houdini/reference.hip', hip, rcode, D + 'data/%s_cmp.json' % trial)
    r = ms['run'](hip, D + 'data/%s.json' % trial, D + 'houdini/base_scene.hip')
    regressions = [k for k, v in r['checks'].items() if not v['pass']]  # 기준 해는 30/30
    out = {'trial': trial, 'target': c['target'], 'collateral': c['collateral'], 'preserved': c['preserved'],
           'checks_pass': r['n_pass'], 'regressions': regressions}
    json.dump(out, open(D + 'data/%s_eval.json' % trial, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return out
