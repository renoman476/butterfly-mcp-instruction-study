# -*- coding: utf-8 -*-
"""Butterfly Encounter 실험 자동 측정 스크립트 (Houdini 내부에서 실행).

사용: exec(open(PATH).read(), ns); ns['run'](hip_path, out_json, base_hip)
모든 판정은 씬 데이터(월드 변환, 지오메트리)에서만 계산하며, 에이전트가 어떤 방식
(키프레임/CHOP/expression/constraint)으로 애니메이션을 만들었는지와 무관하다.
"""
import hou, json, math, hashlib

FPS = 24.0
F0, F1 = 1, 264
LAND = 132
SUB = 4  # 날갯짓 측정용 서브프레임 수

G = '/obj/girl'
BF = '/obj/butterfly'
CAMS = ['/obj/CAM_A_MASTER', '/obj/CAM_B_HAND', '/obj/CAM_C_TRANSITION']


# ---------------------------------------------------------------- 기초 함수
def T(f):
    return (f - 1) / FPS


def wxf(path, f):
    # 재생·렌더와 동일하게 현재 프레임을 이동해 평가한다.
    # (worldTransformAtTime 은 hou.frame() 기반 Python expression 을 반영하지 못함 — 2026-10-14 보정)
    if hou.frame() != f:
        hou.setFrame(f)
    return hou.node(path).worldTransform()


def pos(path, f):
    return hou.Vector3(wxf(path, f).extractTranslates())


def axis(m, i):
    return hou.Vector3(m.at(i, 0), m.at(i, 1), m.at(i, 2)).normalized()


def ang(a, b):
    d = max(-1.0, min(1.0, a.normalized().dot(b.normalized())))
    return math.degrees(math.acos(d))


def mean(x):
    return sum(x) / len(x) if x else float('nan')


def std(x):
    m = mean(x)
    return math.sqrt(sum((v - m) ** 2 for v in x) / len(x)) if x else float('nan')


def rng(a, b):
    return range(a, b + 1)


def deriv(series, dt):
    return [(series[i + 1] - series[i]) / dt for i in range(len(series) - 1)]


def vnorm(vs):
    return [v.length() for v in vs]


# ---------------------------------------------------------------- 날갯짓 각도
def flap_angle(side, t_frame):
    """날개 컨트롤 X축이 나비 몸통 수평면에서 들린 각도(+ 위). 구현 방식과 무관."""
    body = wxf(BF + '/CTRL_body', t_frame)
    w = wxf(BF + '/CTRL_wing_' + side, t_frame)
    x = axis(w, 0)
    bx, by = axis(body, 0), axis(body, 1)
    if side == 'R':
        x = -x  # 미러 날개의 바깥 방향
        bx = -bx
    return math.degrees(math.atan2(x.dot(by), x.dot(bx)))


def cycles(sig, ts, prom=15.0):
    """국소 최대(열림) 중 prominence 이상인 것의 시각 목록"""
    peaks = []
    for i in range(1, len(sig) - 1):
        if sig[i] >= sig[i - 1] and sig[i] > sig[i + 1]:
            lo_l = min(sig[max(0, i - 4 * SUB * 6):i + 1])
            lo_r = min(sig[i:i + 4 * SUB * 6])
            if sig[i] - max(lo_l, lo_r) >= prom:
                peaks.append(ts[i])
    return peaks


def flap_stats(a, b, pad=12):
    # 구간 양끝 봉우리의 prominence 가 잘리지 않도록 앞뒤 pad 프레임을 문맥으로 포함하고,
    # 봉우리 개수·진폭은 [a, b] 안에서만 센다. (2026-10-14 경계 효과 보정)
    a0, b0 = max(1, a - pad), min(264, b + pad)
    tsx = [a0 + k / SUB for k in range(int((b0 - a0) * SUB) + 1)]
    sigx = [0.5 * (flap_angle('L', t) + flap_angle('R', t)) for t in tsx]
    pk = [t for t in cycles(sigx, tsx, prom=15.0) if a <= t <= b]
    sig = [s for t, s in zip(tsx, sigx) if a <= t <= b]
    dur = (b - a) / FPS
    freq = len(pk) / dur if dur > 0 else 0
    amp = max(sig) - min(sig)
    return dict(freq_hz=freq, amp_deg=amp, n_cycles=len(pk), min_deg=min(sig), max_deg=max(sig))


# ---------------------------------------------------------------- 카메라 투영
def ndc(cam_path, p, f):
    cam = hou.node(cam_path)
    m = wxf(cam_path, f).inverted()
    q = p * m
    if q[2] >= -1e-4:
        return None
    foc = cam.parm('focal').evalAtTime(T(f))
    ap = cam.parm('aperture').evalAtTime(T(f))
    asp = cam.parm('resy').eval() / float(cam.parm('resx').eval())
    x = (foc * q[0] / -q[2]) / ap + 0.5
    y = (foc * q[1] / -q[2]) / (ap * asp) + 0.5
    return (x, y)


def in_frame(cam, p, f, margin=0.05):
    u = ndc(cam, p, f)
    return u is not None and margin <= u[0] <= 1 - margin and margin <= u[1] <= 1 - margin


# ---------------------------------------------------------------- 손가락
FINGERS = ['index', 'middle', 'ring', 'little']


def finger_curl(side, f):
    out = {}
    for fn in FINGERS:
        dirs = [-axis(wxf('%s/rig_bone_%s_%d_%s' % (G, fn, k, side), f), 2) for k in (1, 2, 3)]
        out[fn] = ang(dirs[0], dirs[1]) + ang(dirs[1], dirs[2])
    return out


# ---------------------------------------------------------------- 지오메트리
def skin_geo(f):
    return hou.node(G + '/geo_skin').displayNode().geometryAtFrame(f)


def geo_hash(sop_path):
    geo = hou.node(sop_path).geometry()
    h = hashlib.md5()
    for p in geo.points():
        h.update(('%.5f,%.5f,%.5f;' % tuple(p.position())).encode())
    return h.hexdigest()[:12]


def parm_snapshot(node_path):
    n = hou.node(node_path)
    snap = {}
    for p in n.parms():
        try:
            snap[p.name()] = [round(p.evalAtFrame(f), 6) if isinstance(p.eval(), float) else str(p.eval()) for f in (1, 132, 264)]
        except Exception:
            pass
    return snap


# ---------------------------------------------------------------- 메인 측정
def collect():
    D = {}
    fr = list(rng(F0, F1))
    D['bp'] = [pos(BF + '/CTRL_body', f) for f in fr]
    D['hc_m'] = [wxf('/obj/hand_contact', f) for f in fr]
    D['hc'] = [hou.Vector3(m.extractTranslates()) for m in D['hc_m']]
    D['head_m'] = [wxf(G + '/rig_bone_head', f) for f in fr]
    D['rhand'] = [pos(G + '/ctrl_rig_bone_hand_right', f) for f in fr]
    return D


def idx(f):
    return f - F0


def run(hip, out_json=None, base_hip=None):
    res = {'hip': hip, 'checks': {}, 'metrics': {}}
    base = {}
    if base_hip:
        hou.hipFile.load(base_hip, suppress_save_prompt=True, ignore_load_warnings=True)
        base['cams'] = {c: parm_snapshot(c) for c in CAMS}
        base['geo'] = {n: geo_hash(BF + '/' + n + '/OUT') for n in ('body', 'wing_fore_L', 'wing_hind_L', 'wing_fore_R', 'wing_hind_R')}
        base['rhand'] = pos(G + '/ctrl_rig_bone_hand_right', 1)
    hou.hipFile.load(hip, suppress_save_prompt=True, ignore_load_warnings=True)
    C, M = res['checks'], res['metrics']

    def chk(key, val, ok, note=''):
        C[key] = {'value': val, 'pass': bool(ok), 'note': note}

    D = collect()
    bp, hc, hcm = D['bp'], D['hc'], D['hc_m']
    dt = 1 / FPS
    vel = deriv(bp, dt)                      # len N-1, vel[i] ~ between frame i,i+1
    spd = vnorm(vel)
    acc = deriv(vel, dt)
    accn = vnorm(acc)
    jerk = vnorm(deriv(acc, dt))
    M['butterfly_speed_mean'] = mean(spd)

    # ---- B1 등장: F1 화면 밖, F30 이전 화면 안
    first_in = next((f for f in rng(1, 264) if in_frame('/obj/CAM_A_MASTER', bp[idx(f)], f, 0.0)), None)
    out1 = not in_frame('/obj/CAM_A_MASTER', bp[0], 1, 0.0)
    chk('B01_entry', {'out_at_F1': out1, 'first_in_frame': first_in}, out1 and first_in is not None and first_in <= 30)

    # ---- B2 첫 등장 급가속 금지 (F1-48 최대 가속도 <= 4 m/s^2)
    a148 = max(accn[0:47])
    chk('B02_entry_accel', round(a148, 3), a148 <= 4.0)

    # ---- B3 경로 굴곡도 F1-120 (1.15~3.0)
    L = sum(spd[0:119]) * dt
    straight = (bp[idx(120)] - bp[0]).length()
    tort = L / straight if straight > 1e-6 else 99
    chk('B03_tortuosity', round(tort, 3), 1.15 <= tort <= 3.0)

    # ---- B4 상하 bobbing F1-96: 12프레임 이동평균 제거 후 y 표준편차 3~30mm
    ys = [p[1] for p in bp[0:96]]
    w = 6
    det = [ys[i] - mean(ys[max(0, i - w):i + w + 1]) for i in range(len(ys))]
    bob = std(det)
    chk('B04_bobbing', round(bob * 1000, 2), 0.003 <= bob <= 0.03, 'mm')

    # ---- B5 얼굴 앞 통과 F49-96: 머리 중심과 최소거리 0.12~0.35m, 얼굴 앞쪽
    best = None
    for f in rng(49, 96):
        hm = D['head_m'][idx(f)]
        hpos = hou.Vector3(hm.extractTranslates())
        d = (bp[idx(f)] - hpos)
        front = d.normalized().dot(axis(hm, 1)) > 0.3
        if best is None or d.length() < best[0]:
            best = (d.length(), front, f)
    chk('B05_face_pass', {'min_dist': round(best[0], 3), 'front': best[1], 'frame': best[2]}, 0.12 <= best[0] <= 0.35 and best[1])

    # ---- B6 hover: F97-131 동안 접점 위 10~15cm, 수평 6cm 이내 >= 12프레임
    hov = 0
    for f in rng(97, 131):
        d = bp[idx(f)] - hc[idx(f)]
        if 0.10 <= d[1] <= 0.15 and math.hypot(d[0], d[2]) <= 0.06:
            hov += 1
    chk('B06_hover', hov, hov >= 12, 'frames')

    # ---- B7 착지 위치/유지: F132 <=1cm, F132-216 내내 <=1cm
    dl = [(bp[idx(f)] - hc[idx(f)]).length() for f in rng(132, 216)]
    chk('B07_landing_contact', {'d_F132_cm': round(dl[0] * 100, 2), 'max_cm': round(max(dl) * 100, 2)}, dl[0] <= 0.01 and max(dl) <= 0.01)
    land_first = next((f for f in rng(97, 216) if (bp[idx(f)] - hc[idx(f)]).length() <= 0.01), None)
    M['landing_frame_actual'] = land_first

    # ---- B8 착지 속도 F128-132 상대속도 평균 <= 0.08 m/s
    rel = [((bp[idx(f + 1)] - hc[idx(f + 1)]) - (bp[idx(f)] - hc[idx(f)])).length() / dt for f in rng(128, 131)]
    chk('B08_soft_landing', round(mean(rel), 3), mean(rel) <= 0.08, 'm/s')

    # ---- B9 착지 전 노이즈 감소: 고주파 잔차(13프레임 이동평균 제거) 표준편차 비율
    #      noise(F108-128) / noise(F1-96) <= 0.5  (파일럿 단계에서 jerk 기준을 대체, 로그 참조)
    def hf_noise(a, b):
        seg = [bp[idx(f)] for f in rng(max(1, a - 6), min(264, b + 6))]
        res = []
        for i in range(6, len(seg) - 6):
            w = seg[i - 6:i + 7]
            m = hou.Vector3(mean([p[0] for p in w]), mean([p[1] for p in w]), mean([p[2] for p in w]))
            res.append((seg[i] - m).length())
        return math.sqrt(mean([r * r for r in res])) if res else 0.0
    n1 = hf_noise(7, 96); n2 = hf_noise(108, 128)
    ratio = n2 / n1 if n1 > 1e-9 else 99
    M['jerk_mean_F1_96'] = mean(jerk[0:93]); M['jerk_mean_F108_128'] = mean(jerk[107:126])
    chk('B09_prelanding_calm', {'ratio': round(ratio, 3), 'noise_flight_mm': round(n1 * 1000, 2), 'noise_pre_mm': round(n2 * 1000, 2)}, ratio <= 0.5)

    # ---- 날갯짓
    fs_fly = flap_stats(1, 96)
    fs_pre = flap_stats(110, 131)
    fs_hand = flap_stats(145, 216)
    fs_take = flap_stats(217, 245)
    M.update({'flap_flight': fs_fly, 'flap_prelanding': fs_pre, 'flap_onhand': fs_hand, 'flap_takeoff': fs_take})
    chk('B10_flight_flap', {'hz': round(fs_fly['freq_hz'], 2), 'amp': round(fs_fly['amp_deg'], 1)},
        4 <= fs_fly['freq_hz'] <= 8 and 60 <= fs_fly['amp_deg'] <= 140)
    ok11 = fs_pre['freq_hz'] >= 1.1 * fs_fly['freq_hz'] and fs_pre['amp_deg'] <= 0.9 * fs_fly['amp_deg']
    chk('B11_prelanding_flap', {'hz_ratio': round(fs_pre['freq_hz'] / max(fs_fly['freq_hz'], 1e-6), 2),
                                'amp_ratio': round(fs_pre['amp_deg'] / max(fs_fly['amp_deg'], 1e-6), 2)}, ok11)
    chk('B12_onhand_flap', {'cycles': fs_hand['n_cycles'], 'hz': round(fs_hand['freq_hz'], 2), 'amp': round(fs_hand['amp_deg'], 1)},
        2 <= fs_hand['n_cycles'] <= 3 and fs_hand['freq_hz'] <= 1.5 and fs_hand['amp_deg'] >= 30)

    # ---- B13 날개 각도 범위 (몸통 관통 방지) [-30, 90]
    allf = [flap_angle(s, f + k / 2.0) for s in ('L', 'R') for f in rng(1, 263) for k in (0, 1)]
    chk('B13_wing_range', {'min': round(min(allf), 1), 'max': round(max(allf), 1)}, min(allf) >= -30 and max(allf) <= 90)

    # ---- B14 착지 중 날개-손 관통: 접점 좌표계에서 날개 점 y >= -3mm
    wing_pts = {}
    for n in ('wing_fore_L', 'wing_hind_L', 'wing_fore_R', 'wing_hind_R'):
        pts = hou.node(BF + '/' + n + '/OUT').geometry().points()
        wing_pts[n] = [p.position() for p in pts[::25]]
    miny = 1e9
    for f in range(132, 217, 4):
        inv = hcm[idx(f)].inverted()
        for n, pl in wing_pts.items():
            W = wxf(BF + '/' + n, f)
            for p in pl:
                q = (p * W) * inv
                miny = min(miny, q[1])
    chk('B14_wing_hand_clear', round(miny * 1000, 2), miny >= -0.003, 'mm')

    # ---- B15 이륙: F217-250에 접점 위 10~20cm(수평 8cm 이내) >=4프레임, F264 손에서 0.4m 이상
    lift = 0
    for f in rng(217, 250):
        d = bp[idx(f)] - hc[idx(f)]
        if 0.10 <= d[1] <= 0.20 and math.hypot(d[0], d[2]) <= 0.08:
            lift += 1
    away = (bp[idx(264)] - hc[idx(264)]).length()
    chk('B15_takeoff', {'lift_frames': lift, 'dist_F264': round(away, 3)},
        lift >= 4 and away >= 0.4 and fs_take['freq_hz'] >= 3)

    # ---- 소녀
    def head_yaw_pitch(f, target=None):
        hm = D['head_m'][idx(f)]
        v = axis(hm, 1) if target is None else (target - hou.Vector3(hm.extractTranslates())).normalized()
        return math.degrees(math.atan2(v[0], v[2])), math.degrees(math.asin(max(-1, min(1, v[1]))))

    hy = [head_yaw_pitch(f) for f in fr_all()]
    ty = [head_yaw_pitch(f, bp[idx(f)]) for f in fr_all()]
    # G1 발견: F1->F60 머리 방향 변화 >= 8도
    h1 = axis(D['head_m'][0], 1); h60 = axis(D['head_m'][idx(60)], 1)
    g1 = ang(h1, h60)
    chk('G01_discovery', round(g1, 2), g1 >= 8)

    # G2 시선 지연: 머리 yaw/pitch 와 나비 방향 yaw/pitch 교차상관 최대 지연 2~5프레임
    def xcorr_lag(a, b, lo=-6, hi=15):
        best = None
        for lag in range(lo, hi + 1):
            xs, ysr = [], []
            for i in range(len(a)):
                j = i - lag
                if 0 <= j < len(b):
                    xs.append(a[i]); ysr.append(b[j])
            mx, my = mean(xs), mean(ysr)
            sx = math.sqrt(sum((x - mx) ** 2 for x in xs)); sy = math.sqrt(sum((y - my) ** 2 for y in ysr))
            r = sum((x - mx) * (y - my) for x, y in zip(xs, ysr)) / (sx * sy) if sx > 0 and sy > 0 else 0
            if best is None or r > best[1]:
                best = (lag, r)
        return best
    lag_y = xcorr_lag([h[0] for h in hy], [t[0] for t in ty])
    lag_p = xcorr_lag([h[1] for h in hy], [t[1] for t in ty])
    lag = lag_y if abs(lag_y[1]) >= abs(lag_p[1]) else lag_p
    M['gaze_lag_yaw'] = lag_y; M['gaze_lag_pitch'] = lag_p
    # 민감도 분석용 보조 지표: 각속도(1차 차분) 교차상관 — 추세 영향 제거 (판정에는 미사용)
    dhy = [hy[i + 1][0] - hy[i][0] for i in range(len(hy) - 1)]
    dty = [ty[i + 1][0] - ty[i][0] for i in range(len(ty) - 1)]
    M['gaze_lag_velocity_yaw'] = xcorr_lag(dhy, dty)
    chk('G02_gaze_lag', {'lag_frames': lag[0], 'r': round(lag[1], 3)}, 2 <= lag[0] <= 5 and lag[1] >= 0.5)

    # G3 교감 중 바라보기: F145-216 머리 방향과 나비 방향 평균 각 <= 25도
    gz = mean([ang(axis(D['head_m'][idx(f)], 1), bp[idx(f)] - hou.Vector3(D['head_m'][idx(f)].extractTranslates())) for f in rng(145, 216)])
    chk('G03_look_at_butterfly', round(gz, 2), gz <= 25)

    # G4 머리 기울임(head tilt) F145-216 roll 변화 3~12도
    rolls = []
    for f in rng(145, 216):
        hm = D['head_m'][idx(f)]
        fwd = axis(hm, 1); up = -axis(hm, 2)
        side = fwd.cross(hou.Vector3(0, 1, 0)).normalized()
        rolls.append(math.degrees(math.asin(max(-1, min(1, up.dot(side))))))
    rr = max(rolls) - min(rolls)
    chk('G04_head_tilt', round(rr, 2), 3 <= rr <= 12)

    # G5 손 내밀기 타이밍/부드러움 (hand_contact 궤적)
    hs = vnorm(deriv(hc, dt))
    onset = next((f for f in rng(2, 140) if hs[idx(f)] > 0.02), None)
    end = None
    if onset:
        for f in rng(onset + 5, 131):
            if all(s < 0.02 for s in hs[idx(f):idx(131)]):
                end = f; break
    peaks = 0
    if onset and end:
        seg = hs[idx(onset):idx(end)]
        mx = max(seg)
        peaks = sum(1 for i in range(1, len(seg) - 1) if seg[i] > seg[i - 1] and seg[i] >= seg[i + 1] and seg[i] > 0.3 * mx)
    chk('G05_hand_reach', {'onset': onset, 'end': end, 'speed_peaks': peaks},
        onset is not None and 49 <= onset <= 72 and end is not None and 90 <= end <= 125 and 1 <= peaks <= 2)

    # G6 접촉 손 안정 F132-216: 평균 위치 대비 최대 이탈 <= 1.5cm
    seg = hc[idx(132):idx(216) + 1]
    mc = hou.Vector3(mean([p[0] for p in seg]), mean([p[1] for p in seg]), mean([p[2] for p in seg]))
    dev = max((p - mc).length() for p in seg)
    chk('G06_hand_stable', round(dev * 100, 2), dev <= 0.015, 'cm')

    # G7 손등 방향: F120-216 접점 Y축과 월드 업 각 <= 35도
    up = max(ang(axis(hcm[idx(f)], 1), hou.Vector3(0, 1, 0)) for f in rng(120, 216))
    chk('G07_hand_up', round(up, 2), up <= 35)

    # G8 CAM_B 화면 안: F120-216 손 접점과 나비 모두 화면 내부(5% 여백)
    inb = all(in_frame('/obj/CAM_B_HAND', hc[idx(f)], f) and in_frame('/obj/CAM_B_HAND', bp[idx(f)], f) for f in range(120, 217, 2))
    chk('G08_camB_framing', inb, inb)

    # G9 반대손 유지: 오른손 이동 <= 3cm (F1 및 기준씬 대비)
    ref = base.get('rhand', D['rhand'][0])
    rd = max((p - ref).length() for p in D['rhand'])
    chk('G09_other_hand_rest', round(rd * 100, 2), rd <= 0.03, 'cm')

    # G10 이륙 후 손 내리기 시점: 손이 2cm 내려가기 시작한 프레임 >= 나비가 15cm 멀어진 프레임
    far = next((f for f in rng(217, 264) if (bp[idx(f)] - hc[idx(f)]).length() >= 0.15), None)
    y216 = hc[idx(216)][1]
    low = next((f for f in rng(217, 264) if hc[idx(f)][1] < y216 - 0.02), None)
    ok10 = far is not None and (low is None or low >= far)
    chk('G10_hand_release_after', {'far': far, 'lower': low}, ok10)

    # G11 손가락 이완: F1/F180/F264 양손, 손가락 평균 curl 10~60도, 약지·새끼 >= 검지, 손가락간 표준편차 >= 3도
    fc = {}
    ok11 = True
    for side in ('left', 'right'):
        for f in (1, 180, 264):
            c = finger_curl(side, f)
            fc['%s_F%d' % (side, f)] = {k: round(v, 1) for k, v in c.items()}
            vals = list(c.values())
            if not (10 <= mean(vals) <= 60 and (c['ring'] + c['little']) / 2 >= c['index'] and std(vals) >= 3):
                ok11 = False
    M['finger_curl'] = fc
    chk('G11_relaxed_fingers', 'see metrics.finger_curl', ok11)

    # ---- 품질
    dv = [abs(spd[i + 1] - spd[i]) for i in range(len(spd) - 1)]
    pops_b = sum(1 for x in dv if x > 0.25)
    hdv = [abs(hs[i + 1] - hs[i]) for i in range(len(hs) - 1)]
    pops_h = sum(1 for x in hdv if x > 0.10)
    chk('Q01_no_pop', {'butterfly': pops_b, 'hand': pops_h}, pops_b == 0 and pops_h == 0)

    mind, minf = 1e9, None
    for f in list(range(1, 128, 2)) + list(range(222, 265, 2)):
        geo = skin_geo(f)
        r = geo.nearestPrim(bp[idx(f)])
        if r and r[3] < mind:
            mind, minf = r[3], f
    chk('Q02_no_body_penetration', {'min_dist_cm': round(mind * 100, 2), 'frame': minf}, mind >= 0.006)

    # ---- 보존
    if base:
        cam_diff = 0
        for c in CAMS:
            now = parm_snapshot(c)
            cam_diff += sum(1 for k, v in base['cams'][c].items() if now.get(k) != v)
        chk('P01_cameras_unchanged', cam_diff, cam_diff == 0, 'changed parms')
        gdiff = [n for n, h in base['geo'].items() if geo_hash(BF + '/' + n + '/OUT') != h]
        chk('P02_models_unchanged', gdiff, not gdiff)

    # ---- 선행조건: 사건이 일어나지 않았으면 해당 달성 항목은 '공허한 통과'로 보고 실패 처리
    hand_raised = (hc[idx(132)][1] - hc[0][1]) >= 0.10
    landed = C['B07_landing_contact']['pass']
    took_off = C['B15_takeoff']['pass'] or ((bp[idx(264)] - hc[idx(264)]).length() >= 0.25)
    PRE = {'B08_soft_landing': landed, 'B09_prelanding_calm': landed, 'B11_prelanding_flap': landed,
           'B12_onhand_flap': landed, 'B14_wing_hand_clear': landed, 'G06_hand_stable': hand_raised,
           'G07_hand_up': hand_raised, 'G08_camB_framing': hand_raised, 'G10_hand_release_after': took_off}
    for k, ok in PRE.items():
        if k in C and C[k]['pass'] and not ok:
            C[k]['pass'] = False
            C[k]['note'] = (C[k]['note'] + ' [prerequisite not met]').strip()
    M['hand_raised'] = hand_raised; M['landed'] = landed; M['took_off'] = took_off

    CONSTRAINT = {'B02_entry_accel', 'B13_wing_range', 'G09_other_hand_rest', 'Q01_no_pop',
                  'Q02_no_body_penetration', 'P01_cameras_unchanged', 'P02_models_unchanged'}
    for k in C:
        C[k]['type'] = 'constraint' if k in CONSTRAINT else 'achievement'
    keys = list(C.keys())
    ach = [k for k in keys if C[k]['type'] == 'achievement']
    con = [k for k in keys if C[k]['type'] == 'constraint']
    res['n_checks'] = len(keys)
    res['n_pass'] = sum(1 for k in keys if C[k]['pass'])
    res['pass_rate'] = res['n_pass'] / float(len(keys))
    res['achievement'] = {'n': len(ach), 'pass': sum(1 for k in ach if C[k]['pass'])}
    res['constraint'] = {'n': len(con), 'pass': sum(1 for k in con if C[k]['pass'])}
    if out_json:
        with open(out_json, 'w', encoding='utf-8') as fh:
            json.dump(res, fh, ensure_ascii=False, indent=1, default=str)
    return res


def fr_all():
    return list(rng(F0, F1))
