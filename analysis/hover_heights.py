# -*- coding: utf-8 -*-
"""정지 비행 높이 산출(Houdini 내부에서 exec). 실험 1에서 사용한 계산을 그대로 스크립트로 보존하고 실험 3에 확장.
- pre: F97–131 중 손 기준 속도 0.05 m/s 미만·높이 3cm 초과 프레임의 손 위 높이(hand_contact 월드 위치 기준 Y 차) 중앙값
- takeoff_lift: F217–250 중 수평 8cm 이내에서의 최대 높이
출력: data/hover_heights.json(전 버전), data/hover_final.json(최종 버전)
"""
import glob, os, math, json
import hou

D = 'D:/claude/butterfly_mcp_paper/'


def measure(p):
    hou.hipFile.load(p, suppress_save_prompt=True, ignore_load_warnings=True)
    b = hou.node('/obj/butterfly/CTRL_body'); h = hou.node('/obj/hand_contact')
    R = {}
    for f in range(90, 262):
        hou.setFrame(f)
        R[f] = hou.Vector3(b.worldTransform().extractTranslates()) - hou.Vector3(h.worldTransform().extractTranslates())

    def hover(a, c):
        hs = [R[f][1] for f in range(a, c) if (R[f + 1] - R[f]).length() * 24 < 0.05 and R[f][1] > 0.03]
        return (round(sorted(hs)[len(hs) // 2] * 100, 1), len(hs)) if hs else (None, 0)
    mx = max([R[f][1] for f in range(217, 251) if math.hypot(R[f][0], R[f][2]) <= 0.08] or [0])
    return {'pre': hover(97, 131), 'takeoff': hover(217, 250), 'takeoff_lift_cm': round(mx * 100, 1)}


def run(prefixes=('E1_', 'E3_')):
    allv = {}
    for p in sorted(glob.glob(D + 'houdini/trials/*_v*.hip')):
        n = os.path.basename(p)[:-4]
        if n.startswith(prefixes):
            allv[n] = measure(p)
    json.dump(allv, open(D + 'data/hover_heights_all.json', 'w'), indent=1)
    finals = {}
    for n in allv:
        t = n.rsplit('_v', 1)[0]
        if t not in finals or n > finals[t]:
            finals[t] = n
    out = {finals[t]: {'pre_hover_cm': allv[finals[t]]['pre'][0], 'takeoff_lift_cm': allv[finals[t]]['takeoff_lift_cm']} for t in sorted(finals)}
    json.dump(out, open(D + 'data/hover_final_all.json', 'w'), indent=1)
    return out
