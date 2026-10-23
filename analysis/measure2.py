# -*- coding: utf-8 -*-
"""실험 2: 국소 수정 지시 전후 비교 (reference.hip 대비 수정본).
사용: exec(open(PATH).read(), ns); ns['compare'](ref_hip, rev_hip, rcode, out_json)
"""
import hou, json, math

FPS = 24.0
G = '/obj/girl'
BF = '/obj/butterfly'
FR = list(range(1, 265))

# 수정 지시별 목표 구간 (이 구간 밖의 변화 = 부작용)
TARGET = {
    'R1': {'butterfly': (85, 131), 'right_fingers': None},
    'R2': {'butterfly': None, 'right_fingers': (140, 210)},
    'R3': {'butterfly': (43, 102), 'right_fingers': None},
}
FINGERS = ['index', 'middle', 'ring', 'little']


def T(f):
    return (f - 1) / FPS


def W(path, f):
    # 재생·렌더와 같은 방식(현재 프레임 이동 후 평가) — measure.py 와 동일
    if hou.frame() != f:
        hou.setFrame(f)
    return hou.node(path).worldTransform()


def P(path, f):
    return hou.Vector3(W(path, f).extractTranslates())


def axis(m, i):
    return hou.Vector3(m.at(i, 0), m.at(i, 1), m.at(i, 2)).normalized()


def ang(a, b):
    return math.degrees(math.acos(max(-1.0, min(1.0, a.normalized().dot(b.normalized())))))


def flap(side, f):
    body = W(BF + '/CTRL_body', f); w = W(BF + '/CTRL_wing_' + side, f)
    x = axis(w, 0); bx, by = axis(body, 0), axis(body, 1)
    if side == 'R':
        x = -x; bx = -bx
    return math.degrees(math.atan2(x.dot(by), x.dot(bx)))


def curl(side, f):
    out = []
    for fn in FINGERS:
        d = [-axis(W('%s/rig_bone_%s_%d_%s' % (G, fn, k, side), f), 2) for k in (1, 2, 3)]
        out.append(ang(d[0], d[1]) + ang(d[1], d[2]))
    return out


def sample(hip):
    hou.hipFile.load(hip, suppress_save_prompt=True, ignore_load_warnings=True)
    S = {}
    S['bp'] = [P(BF + '/CTRL_body', f) for f in FR]
    S['flapL'] = [flap('L', f) for f in FR]
    S['head'] = [axis(W(G + '/rig_bone_head', f), 1) for f in FR]
    S['lh'] = [P(G + '/ctrl_rig_bone_hand_left', f) for f in FR]
    S['rh'] = [P(G + '/ctrl_rig_bone_hand_right', f) for f in FR]
    S['lc'] = {f: curl('left', f) for f in range(1, 265, 3)}
    S['rc'] = {f: curl('right', f) for f in range(1, 265, 3)}
    S['hc'] = [P('/obj/hand_contact', f) for f in FR]
    cams = {}
    for c in ('CAM_A_MASTER', 'CAM_B_HAND', 'CAM_C_TRANSITION'):
        n = hou.node('/obj/' + c)
        cams[c] = {p.name(): tuple(round(p.evalAtFrame(f), 6) for f in (1, 132, 264))
                   for p in n.parms() if isinstance(p.eval(), float)}
    S['cams'] = cams
    return S


def rms(xs):
    return math.sqrt(sum(x * x for x in xs) / len(xs)) if xs else 0.0


def outside(win):
    if win is None:
        return FR
    return [f for f in FR if not (win[0] <= f <= win[1])]


def hover_frames(S, a=85, b=131):
    n = 0
    for f in range(a, b + 1):
        d = S['bp'][f - 1] - S['hc'][f - 1]
        if 0.10 <= d[1] <= 0.15 and math.hypot(d[0], d[2]) <= 0.06:
            n += 1
    return n


def hf_noise(S, a, b):
    bp = S['bp']; res = []
    for i in range(a - 1, b):
        w = bp[max(0, i - 6):i + 7]
        m = hou.Vector3(sum(p[0] for p in w) / len(w), sum(p[1] for p in w) / len(w), sum(p[2] for p in w) / len(w))
        res.append((bp[i] - m).length())
    return rms(res)


def path_ratio(S, a, b):
    bp = S['bp']
    L = sum((bp[i + 1] - bp[i]).length() for i in range(a - 1, b - 1))
    d = (bp[b - 1] - bp[a - 1]).length()
    return L / d if d > 1e-6 else 99


def landing_frame(S):
    for f in range(97, 217):
        if (S['bp'][f - 1] - S['hc'][f - 1]).length() <= 0.01:
            return f
    return None


def compare(ref_hip, rev_hip, rcode, out_json=None):
    R = sample(ref_hip)
    V = sample(rev_hip)
    tg = TARGET[rcode]
    out = {'rcode': rcode, 'ref': ref_hip, 'rev': rev_hip}

    # ---- 목표 달성
    if rcode == 'R1':
        hr, hv = hover_frames(R), hover_frames(V)
        out['target'] = {'hover_ref': hr, 'hover_rev': hv, 'pass': hv >= 20 and hv - hr >= 6}
    elif rcode == 'R2':
        def span(S):
            vals = [sum(S['rc'][f]) / 4 for f in S['rc'] if 150 <= f <= 200]
            return max(vals) - min(vals)
        sr, sv = span(R), span(V)
        out['target'] = {'curl_span_ref': round(sr, 2), 'curl_span_rev': round(sv, 2), 'pass': sv - sr >= 3}
    else:
        nr, nv = hf_noise(R, 49, 96), hf_noise(V, 49, 96)
        tr, tv = path_ratio(R, 49, 96), path_ratio(V, 49, 96)
        out['target'] = {'noise_ref_mm': round(nr * 1000, 2), 'noise_rev_mm': round(nv * 1000, 2),
                         'tort_ref': round(tr, 3), 'tort_rev': round(tv, 3),
                         'pass': nv >= 1.2 * nr or tv >= 1.2 * tr}

    # ---- 부작용 (목표 구간 밖)
    ob = outside(tg['butterfly'])
    col = {}
    col['butterfly_rms_cm'] = round(rms([(V['bp'][f - 1] - R['bp'][f - 1]).length() for f in ob]) * 100, 3)
    col['butterfly_max_cm'] = round(max((V['bp'][f - 1] - R['bp'][f - 1]).length() for f in ob) * 100, 3)
    col['flap_rms_deg'] = round(rms([V['flapL'][f - 1] - R['flapL'][f - 1] for f in ob]), 3)
    col['landing_ref'] = landing_frame(R); col['landing_rev'] = landing_frame(V)
    # 머리: R3는 목표 구간(+6프레임 지연 여유)의 시선 변화를 정당한 결과로 보고 제외
    oh = outside((tg['butterfly'][0], tg['butterfly'][1] + 6)) if rcode == 'R3' else (ob if rcode == 'R1' else FR)
    if rcode == 'R1':
        oh = outside((85, 137))
    col['head_mean_deg'] = round(sum(ang(V['head'][f - 1], R['head'][f - 1]) for f in oh) / len(oh), 3)
    col['left_hand_rms_cm'] = round(rms([(V['lh'][f - 1] - R['lh'][f - 1]).length() for f in FR]) * 100, 3)
    col['right_hand_rms_cm'] = round(rms([(V['rh'][f - 1] - R['rh'][f - 1]).length() for f in FR]) * 100, 3)
    col['left_fingers_mean_deg'] = round(sum(sum(abs(a - b) for a, b in zip(V['lc'][f], R['lc'][f])) / 4 for f in R['lc']) / len(R['lc']), 3)
    rf_win = tg['right_fingers']
    rfs = [f for f in R['rc'] if rf_win is None or not (rf_win[0] <= f <= rf_win[1])]
    col['right_fingers_mean_deg'] = round(sum(sum(abs(a - b) for a, b in zip(V['rc'][f], R['rc'][f])) / 4 for f in rfs) / len(rfs), 3)
    cam_changed = 0
    for c in R['cams']:
        for k, v in R['cams'][c].items():
            if V['cams'][c].get(k) != v:
                cam_changed += 1
    col['camera_parms_changed'] = cam_changed
    out['collateral'] = col
    # 허용 기준 (H5)
    out['preserved'] = (col['butterfly_rms_cm'] < 0.5 and cam_changed == 0 and col['landing_rev'] == col['landing_ref']
                        and col['right_hand_rms_cm'] < 0.5 and col['left_hand_rms_cm'] < 0.5)
    if out_json:
        with open(out_json, 'w', encoding='utf-8') as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1, default=str)
    return out
