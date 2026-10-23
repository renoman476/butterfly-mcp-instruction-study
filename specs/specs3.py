# -*- coding: utf-8 -*-
"""실험 3(심사 대응 추가 실험) 지시문 생성기.

실험 1과 같은 기준 씬·공통 머리말·30개 요구사항(specs.py의 REQS)을 그대로 사용한다.
- C  (기술형+수치 기준): 기술형 문장 뒤에 수치형 문장을 '(수치 기준: …)'으로 덧붙임.
      실험 1의 서술형(N)·기술형(T)·혼합형(M=N+수치)과 함께
      '표현 방식(서술/기술) × 수치 기준(무/유)' 2×2 설계를 이룬다.
- NV (서술형+검증 절차), TV (기술형+검증 절차): 실험 1의 N·T 지시문에
      모든 조건 공통의 '검증 절차' 조항만 추가. 수치 기준은 주지 않는다.
      실험 1에서 수치형·혼합형 에이전트가 자발적으로 수행한 자기 검증을
      절차로 강제했을 때 수치 기준 없이도 충족률이 오르는지 본다.
재작업 지시는 실험 1과 같이 미충족 항목의 같은 유형 문장만 재전달한다(측정값 비공개, 최대 2회).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import specs as S

PREAMBLE = '당신은 Houdini MCP(mcp__houdini__* 도구)로 연결된 Houdini를 조작하는 애니메이션 에이전트다. 아래 지시를 수행하라.\n\n'

VERIFY = """■ 검증 절차
- 저장하기 전에, 아래 각 요구사항이 충족되었는지 씬 데이터(노드의 월드 위치·회전, 파라미터 값 등)를 프레임별로 조회·계산하는 검사 스크립트를 직접 작성해 실행한다.
- 충족되지 않은 항목이 있으면 수정한 뒤 다시 검사하고, 모든 항목이 충족된 것을 확인한 다음 저장한다.
- 보고에 항목별 검사 방법과 결과를 함께 적는다.

"""

STYLE_NAME = {'C': '기술형+수치기준', 'NV': '서술형+검증절차', 'TV': '기술형+검증절차'}
BASE_STYLE = {'C': 'T', 'NV': 'N', 'TV': 'T'}


def req_text(r, cond):
    rid, cut, n, t, q = r
    if cond == 'C':
        return '%s (수치 기준: %s)' % (t, q)
    return S.req_text(r, BASE_STYLE[cond])


def build_prompt(cond, out_path):
    head = S.HEADER.format(base=S.BASE, out=out_path)
    if cond in ('NV', 'TV'):
        head = head.replace('■ 요구사항\n', VERIFY + '■ 요구사항\n')
    lines = [head]
    for cut in (1, 2, 3, 4, 5, 0):
        rs = [r for r in S.REQS if r[1] == cut]
        if not rs:
            continue
        lines.append('[%s]' % S.CUT_NAME[cut])
        for r in rs:
            lines.append('- %s' % req_text(r, cond))
        lines.append('')
    return '\n'.join(lines)


def build_rework(cond, failed_ids, out_path):
    rs = [r for r in S.REQS if r[0] in failed_ids]
    lines = ['[추가 수정 지시] 방금 저장한 씬을 검토한 결과, 아래 요구사항이 아직 충족되지 않았다. '
             '나머지는 유지하면서 아래 항목을 수정하고 {} 로 저장한 뒤 보고해줘.'.format(out_path), '']
    for r in rs:
        lines.append('- %s' % req_text(r, cond))
    return '\n'.join(lines)


# 측정 항목 키 → 요구사항 ID (P01·P02는 공통 조건이므로 재지시 대상이 아님)
def ids_from_failed_checks(failed_keys):
    return sorted({k.split('_')[0] for k in failed_keys if k.split('_')[0] in {r[0] for r in S.REQS}})


if __name__ == '__main__':
    import random, json
    d = 'D:/claude/butterfly_mcp_paper/specs'
    for c in ('C', 'NV', 'TV'):
        with open('%s/E3_%s_%s.txt' % (d, c, STYLE_NAME[c]), 'w', encoding='utf-8') as fh:
            fh.write(build_prompt(c, 'D:/claude/butterfly_mcp_paper/houdini/trials/E3_%s_rX.hip' % c))
        print(c, len(build_prompt(c, 'X')), 'chars')
    trials = ['E3_%s_r%d' % (c, i) for c in ('C', 'NV', 'TV') for i in (1, 2, 3)]
    random.Random(2026).shuffle(trials)
    json.dump(trials, open('D:/claude/butterfly_mcp_paper/logs/E3_order.json', 'w'), ensure_ascii=False)
    print(trials)
