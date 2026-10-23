# -*- coding: utf-8 -*-
"""하위 에이전트 transcript(JSONL)에서 라운드별 비용을 산출한다.
라운드 경계 = 연구자가 보낸 텍스트 메시지(최초 지시문, 추가 수정 지시).
사용: python cost.py  → data/cost.json
"""
import json, os, sys
from datetime import datetime

TASKS = '<HOME>/.claude/projects/D--claude/df5309fc-0c6a-46cf-b68b-67c8f02294a0/subagents'
AGENTS = 'D:/claude/butterfly_mcp_paper/logs/agents.json'
OUT = 'D:/claude/butterfly_mcp_paper/data/cost.json'


def ts(s):
    return datetime.fromisoformat(s.replace('Z', '+00:00'))


def is_prompt(d):
    if d.get('type') != 'user':
        return False
    c = d.get('message', {}).get('content')
    if isinstance(c, str):
        head = c[:200]
        return c.startswith('당신은') or c.startswith('[추가 수정') or c.startswith('[수정 지시]') or             ('coordinator sent a message' in head and ('[추가 수정' in head or '[수정 지시]' in head))
    if isinstance(c, list):
        for b in c:
            if b.get('type') == 'text':
                t = b.get('text', '')
                if t.startswith('당신은') or t.startswith('[추가 수정') or t.startswith('[수정 지시]'):
                    return True
    return False


def rounds(path):
    segs = []
    cur = None
    for line in open(path, encoding='utf-8'):
        try:
            d = json.loads(line)
        except Exception:
            continue
        if is_prompt(d):
            cur = {'start': d['timestamp'], 'end': d['timestamp'], 'tool_uses': 0, 'houdini_calls': 0,
                   'output_tokens': 0, 'input_tokens': 0, 'cache_read': 0, 'cache_write': 0, 'turns': 0}
            segs.append(cur)
            continue
        if cur is None:
            continue
        if 'timestamp' in d:
            cur['end'] = d['timestamp']
        if d.get('type') == 'assistant':
            m = d['message']
            u = m.get('usage') or {}
            cur['turns'] += 1
            cur['output_tokens'] += u.get('output_tokens', 0) or 0
            cur['input_tokens'] += u.get('input_tokens', 0) or 0
            cur['cache_read'] += u.get('cache_read_input_tokens', 0) or 0
            cur['cache_write'] += u.get('cache_creation_input_tokens', 0) or 0
            for b in m.get('content', []):
                if b.get('type') == 'tool_use':
                    cur['tool_uses'] += 1
                    if b.get('name', '').startswith('mcp__houdini__'):
                        cur['houdini_calls'] += 1
    for s in segs:
        s['duration_s'] = round((ts(s['end']) - ts(s['start'])).total_seconds(), 1)
    return segs


if __name__ == '__main__':
    agents = json.load(open(AGENTS, encoding='utf-8'))
    res = {}
    for trial, aid in agents.items():
        p = os.path.join(TASKS, 'agent-' + aid + '.jsonl')
        if os.path.exists(p):
            res[trial] = rounds(p)
    json.dump(res, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    sys.stdout.reconfigure(encoding='utf-8')
    for t, segs in res.items():
        print(t, [(i, s['duration_s'], s['tool_uses'], s['output_tokens']) for i, s in enumerate(segs)])
