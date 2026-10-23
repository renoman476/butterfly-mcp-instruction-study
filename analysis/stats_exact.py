# -*- coding: utf-8 -*-
"""심사 의견 ④ 대응: 소표본·동점을 고려한 정확(순열) 검정과 효과 크기.

- Kruskal–Wallis: 12개 점수를 4집단(각 3)에 배정하는 모든 경우(12!/(3!)^4 = 369,600)를 열거한 정확 순열 p.
  동점 보정 H 사용. 효과 크기 η²(H) = (H − k + 1)/(n − k)  (Tomczak & Tomczak, 2014).
- Mann–Whitney: 수치 기준 포함(6) vs 미포함(6). 모든 C(12,6)=924 분할 열거 정확 p(단측·양측).
  효과 크기: 순위이연상관 r_rb = 2U/(n1·n2) − 1 (= Cliff's δ).
- 2×2(표현 방식 × 수치 기준) 주효과: 각 요인 수준 간 Mann–Whitney 정확 검정.
- 실험 2: 기술통계(조건별 원자료)만 보고.
"""
import itertools, json, math, sys
import numpy as np
from scipy import stats

sys.stdout.reconfigure(encoding='utf-8')
ROOT = 'D:/claude/butterfly_mcp_paper'


def kw_H(groups):
    return stats.kruskal(*groups).statistic if len(set(np.concatenate(groups))) > 1 else 0.0


def kw_exact(groups):
    vals = np.concatenate(groups)
    sizes = [len(g) for g in groups]
    H0 = kw_H(groups)
    n = len(vals)
    # 정확 열거: 동일 값이 많으므로 값 다중집합 단위로 집계해도 되지만 단순 열거(369,600)로 충분
    idx = list(range(n))
    cnt = tot = 0
    def rec(remaining, gs):
        nonlocal cnt, tot
        if len(gs) == len(sizes) - 1:
            gs2 = gs + [remaining]
            H = kw_H([vals[list(g)] for g in gs2])
            tot += 1
            cnt += H >= H0 - 1e-12
            return
        k = sizes[len(gs)]
        first = remaining[0]
        rest = remaining[1:]
        for comb in itertools.combinations(rest, k - 1):
            g = (first,) + comb
            rem = tuple(i for i in remaining if i not in g)
            rec(rem, gs + [g])
    # 집단 크기가 같으므로 집단 순서 교환은 H에 영향 없음 → 첫 원소 고정으로 중복 제거
    rec(tuple(idx), [])
    k = len(groups)
    return H0, cnt / tot, tot, (H0 - k + 1) / (n - k)


def mwu_exact(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    U0 = stats.mannwhitneyu(a, b, alternative='greater').statistic
    vals = np.concatenate([a, b]); n1 = len(a)
    ge = le = tot = 0
    for comb in itertools.combinations(range(len(vals)), n1):
        m = np.zeros(len(vals), bool); m[list(comb)] = True
        U = stats.mannwhitneyu(vals[m], vals[~m], alternative='greater').statistic
        tot += 1; ge += U >= U0 - 1e-12; le += U <= U0 + 1e-12
    p1 = ge / tot
    p2 = min(1.0, 2 * min(ge, le) / tot)
    rrb = 2 * U0 / (len(a) * len(b)) - 1
    return U0, p1, p2, rrb, tot


if __name__ == '__main__':
    E1 = json.load(open(ROOT + '/data/e1_summary.json', encoding='utf-8'))['trials']
    first = {s: [r['first_total'] for k, r in sorted(E1.items()) if r['style'] == s] for s in 'NTQM'}
    out = {'raw_first': first}
    try:
        E3 = json.load(open(ROOT + '/data/e3_summary.json', encoding='utf-8'))['trials']
        for c in ('C', 'NV', 'TV'):
            first[c] = [r['first_total'] for k, r in sorted(E3.items()) if r['cond'] == c]
    except FileNotFoundError:
        pass
    print('1차 원점수', first)

    H, p, tot, eta = kw_exact([np.array(first[s], float) for s in 'NTQM'])
    pa = stats.kruskal(*[first[s] for s in 'NTQM']).pvalue
    out['kw_NTQM'] = {'H': H, 'p_asym': pa, 'p_exact': p, 'n_perm': tot, 'eta2_H': eta}
    print('KW N/T/Q/M  H=%.3f  점근 p=%.4f  정확 p=%.4f (%d 배정)  η²(H)=%.3f' % (H, pa, p, tot, eta))

    num = first['Q'] + first['M']; non = first['N'] + first['T']
    U, p1, p2, rrb, tot = mwu_exact(num, non)
    out['mwu_num_vs_non'] = {'U': U, 'p1_exact': p1, 'p2_exact': p2, 'r_rb': rrb, 'n_perm': tot}
    print('MWU 수치(Q,M) vs 비수치(N,T)  U=%.0f  정확 단측 p=%.4f  양측 p=%.4f  r_rb=%.2f' % (U, p1, p2, rrb))

    if 'C' in first:
        # 2×2: 표현(서술 N·M / 기술 T·C) × 수치 기준(무 N·T / 유 M·C)
        withN = first['M'] + first['C']; without = first['N'] + first['T']
        U, p1, p2, rrb, tot = mwu_exact(withN, without)
        out['2x2_numeric'] = {'U': U, 'p1_exact': p1, 'p2_exact': p2, 'r_rb': rrb}
        print('2×2 수치 기준 주효과(M,C vs N,T)  U=%.0f  단측 p=%.4f  양측 p=%.4f  r_rb=%.2f' % (U, p1, p2, rrb))
        nar = first['N'] + first['M']; tec = first['T'] + first['C']
        U, p1, p2, rrb, tot = mwu_exact(nar, tec)
        out['2x2_expression'] = {'U': U, 'p2_exact': p2, 'r_rb': rrb}
        print('2×2 표현 방식 주효과(서술 N,M vs 기술 T,C)  U=%.0f  양측 p=%.4f  r_rb=%.2f' % (U, p2, rrb))
        # 검증 절차 효과: NV vs N, TV vs T, (NV,TV) vs (N,T)
        U, p1, p2, rrb, tot = mwu_exact(first['NV'] + first['TV'], first['N'] + first['T'])
        out['verify_vs_base'] = {'U': U, 'p1_exact': p1, 'p2_exact': p2, 'r_rb': rrb}
        print('검증 절차(NV,TV) vs 기본(N,T)  U=%.0f  단측 p=%.4f  양측 p=%.4f  r_rb=%.2f' % (U, p1, p2, rrb))
        U, p1, p2, rrb, tot = mwu_exact(first['M'] + first['C'], first['NV'] + first['TV'])
        out['numeric_vs_verify'] = {'U': U, 'p1_exact': p1, 'p2_exact': p2, 'r_rb': rrb}
        print('수치 기준(M,C) vs 검증 절차(NV,TV)  U=%.0f  단측 p=%.4f  양측 p=%.4f  r_rb=%.2f' % (U, p1, p2, rrb))
    json.dump(out, open(ROOT + '/data/stats_exact.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- 민감도 분석: 측정 민감 항목(B09·G02) 제외 28개 항목
if __name__ == '__main__':
    ex = {s: [r['v'][0]['ach_ex'] + r['v'][0]['con_ex'] for k, r in sorted(E1.items()) if r['style'] == s] for s in 'NTQM'}
    try:
        for c in ('C', 'NV', 'TV'):
            ex[c] = [28 - len([x for x in r['v'][0]['fails'] if not x.startswith(('B09', 'G02'))]) for k, r in sorted(E3.items()) if r['cond'] == c]
    except NameError:
        pass
    print('28항목 1차 점수', ex)
    H, p, tot, eta = kw_exact([np.array(ex[s], float) for s in 'NTQM'])
    out['ex28_kw_NTQM'] = {'H': H, 'p_exact': p, 'eta2_H': eta}
    print('28항목 KW  H=%.3f 정확 p=%.4f η²(H)=%.3f' % (H, p, eta))
    if 'C' in ex:
        for name, a, b in (('ex28_numeric', ex['M'] + ex['C'], ex['N'] + ex['T']), ('ex28_verify', ex['NV'] + ex['TV'], ex['N'] + ex['T'])):
            U, p1, p2, rrb, tot = mwu_exact(a, b)
            out[name] = {'U': U, 'p1_exact': p1, 'p2_exact': p2, 'r_rb': rrb}
            print(name, 'U=%.0f 단측 p=%.4f 양측 p=%.4f r_rb=%.2f' % (U, p1, p2, rrb))
    json.dump(out, open(ROOT + '/data/stats_exact.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- 쉬운 버전 비교: 수치 기준 있음(Q·M·C, 9회) 대 없음(N·T·NV·TV, 12회)
if __name__ == '__main__':
    if 'C' in first:
        a = first['Q'] + first['M'] + first['C']; b = first['N'] + first['T'] + first['NV'] + first['TV']
        U, p1, p2, rrb, tot = mwu_exact(a, b)
        out['pooled_9v12'] = {'U': U, 'p1_exact': p1, 'p2_exact': p2, 'r_rb': rrb, 'n_perm': tot, 'n1': len(a), 'n2': len(b)}
        print('수치 기준 있음 9회 vs 없음 12회  U=%.0f  정확 양측 p=%.2e (%d 분할)  r_rb=%.2f' % (U, p2, tot, rrb))
        json.dump(out, open(ROOT + '/data/stats_exact.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
