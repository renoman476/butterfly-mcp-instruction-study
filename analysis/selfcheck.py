# -*- coding: utf-8 -*-
"""하위 에이전트 작업 기록(JSONL)에서 자기 검증 행동을 정량화한다(심사 의견 ③ 대응).

분류 규칙(사전 정의, 모든 시행에 동일 적용)
- 쓰기 호출: Houdini 씬을 변경하는 execute_python (키·파라미터·표현식 설정, 노드 생성/삭제, 파일 로드/저장).
- 검사 호출: 씬을 변경하지 않고, 프레임을 옮기거나 시간 지정 평가로 결과값을 계산하는 execute_python.
  exec(open(파일)) 형태는 그 시점까지 Write/Edit로 작성된 파일 내용을 펼쳐서 판정한다.
- 검사 스크립트: 검사 호출에서 재사용된 파일(같은 파일을 2회 이상 실행했거나, 파일 이름에 check/verify/test/measure 포함).
- 사후 검사: 마지막 쓰기 호출 이후, 저장 전에 수행된 검사 호출(최종 상태를 확인했는지).
라운드는 '[추가 수정 지시]'로 시작하는 사용자 메시지로 나눈다. 기본 집계는 1차(라운드 0)이다.
"""
import json, re, os, sys

SUB = '<HOME>/.claude/projects/D--claude/df5309fc-0c6a-46cf-b68b-67c8f02294a0/subagents'
WRITE_PAT = re.compile(r'setKeyframe|\.set\(|setExpression|createNode|destroy\(|deleteAllKeyframes|hipFile\.(load|save)|'
                       r'setKeyframes|\.setInput|insertParmTemplate|addSpareParmTuple|setParms|lock\(|setFirstInput')
EVAL_PAT = re.compile(r'setFrame|AtTime|AtFrame|evalAtFrame|worldTransform')
EXEC_PAT = re.compile(r"exec\(open\(r?['\"]([^'\"]+)['\"]")
NAME_PAT = re.compile(r'check|verify|test|measure|valid|검사', re.I)


def classify(code, files):
    """code 안의 exec(open(f)) 를 펼친 전체 텍스트와 사용 파일 목록을 돌려준다."""
    used = EXEC_PAT.findall(code)
    full = code
    for f in used:
        full += '\n' + files.get(os.path.basename(f.replace('\\', '/')), '')
    return full, [os.path.basename(u.replace('\\', '/')) for u in used]


def analyse(agent_id):
    path = '%s/agent-%s.jsonl' % (SUB, agent_id)
    files, rounds, r = {}, {}, 0
    for line in open(path, encoding='utf-8'):
        o = json.loads(line)
        m = o.get('message') or {}
        c = m.get('content')
        if m.get('role') == 'user':
            txt = c if isinstance(c, str) else ' '.join(x.get('text', '') for x in c if isinstance(x, dict) and x.get('type') == 'text')
            if '[추가 수정 지시]' in txt:
                r += 1
        if not isinstance(c, list):
            continue
        for x in c:
            if x.get('type') != 'tool_use':
                continue
            nm, inp = x['name'], x.get('input', {})
            R = rounds.setdefault(r, {'events': [], 'tool_uses': 0})
            R['tool_uses'] += 1
            if nm in ('Write',):
                files[os.path.basename(inp.get('file_path', '').replace('\\', '/'))] = inp.get('content', '')
            elif nm == 'Edit':
                b = os.path.basename(inp.get('file_path', '').replace('\\', '/'))
                if b in files:
                    files[b] = files[b].replace(inp.get('old_string', ''), inp.get('new_string', ''), 1)
            elif nm == 'mcp__houdini__execute_python':
                full, used = classify(inp.get('code', ''), files)
                is_write = bool(WRITE_PAT.search(full))
                kind = 'write' if is_write else ('check' if EVAL_PAT.search(full) else 'query')
                R['events'].append((kind, used))
            elif nm == 'mcp__houdini__save_hip':
                R['events'].append(('save', []))
            elif nm in ('mcp__houdini__set_parms', 'mcp__houdini__create_node', 'mcp__houdini__delete_node', 'mcp__houdini__connect_nodes'):
                R['events'].append(('write', []))
    out = {}
    for k, R in rounds.items():
        ev = R['events']
        checks = [e for e in ev if e[0] == 'check']
        file_runs = {}
        for e in checks:
            for u in e[1]:
                file_runs[u] = file_runs.get(u, 0) + 1
        scripts = sorted(f for f, n in file_runs.items() if n >= 2 or NAME_PAT.search(f))
        last_w = max([i for i, e in enumerate(ev) if e[0] == 'write'], default=-1)
        saves = [i for i, e in enumerate(ev) if e[0] == 'save']
        last_s = saves[-1] if saves else len(ev)
        post = sum(1 for i, e in enumerate(ev) if e[0] == 'check' and last_w < i < last_s)
        out[k] = {'tool_uses': R['tool_uses'], 'writes': sum(e[0] == 'write' for e in ev), 'checks': len(checks),
                  'check_scripts': scripts, 'post_write_checks': post}
    return out


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    A = json.load(open('D:/claude/butterfly_mcp_paper/logs/agents.json'))
    res = {}
    for t, aid in sorted(A.items()):
        if not (t.startswith('E1_') or t.startswith('E3_')):
            continue
        if not os.path.exists('%s/agent-%s.jsonl' % (SUB, aid)):
            continue
        res[t] = analyse(aid)
        r0 = res[t].get(0, {})
        print(t, r0)
    json.dump(res, open('D:/claude/butterfly_mcp_paper/data/selfcheck.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
