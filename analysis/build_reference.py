# -*- coding: utf-8 -*-
"""검증용 기준 해(reference solution) 생성 스크립트.
측정 스크립트(measure.py)가 모든 요구사항을 '달성 가능'한 것으로 판정하는지 확인하고,
실험 2(국소 수정 보존성)의 공통 출발 씬으로 사용한다.
"""
import hou, math

BASE = 'D:/claude/butterfly_mcp_paper/houdini/base_scene.hip'
OUT = 'D:/claude/butterfly_mcp_paper/houdini/reference.hip'
REACH = dict(t=[-0.19013106711217626, 0.2043415440898135, 0.38428164537850623],
             r=[3.125, -126.875, -59.375])
FPS = 24.0


def T(f):
    return (f - 1) / FPS


def setkeys(parm, pairs, flat=True):
    parm.deleteAllKeyframes()
    for f, v in pairs:
        k = hou.Keyframe()
        k.setFrame(f)
        k.setValue(v)
        if flat:
            k.setExpression('ease()', hou.exprLanguage.Hscript)
        else:
            k.setExpression('bezier()', hou.exprLanguage.Hscript)
            k.setSlopeAuto(True); k.setInSlopeAuto(True)
        parm.setKeyframe(k)


def setlin(parm, pairs):
    parm.deleteAllKeyframes()
    for f, v in pairs:
        k = hou.Keyframe(); k.setFrame(f); k.setValue(v)
        k.setExpression('linear()', hou.exprLanguage.Hscript)
        parm.setKeyframe(k)


def build():
    hou.hipFile.load(BASE, suppress_save_prompt=True)
    g = hou.node('/obj/girl')
    bf = hou.node('/obj/butterfly')
    body = bf.node('CTRL_body')
    hc = hou.node('/obj/hand_contact')

    # ---------------- 1. 왼손 내밀기 (F54 시작 → F104 도달, 유지, F240 이후 천천히 내림)
    b_t = [g.parm('ikwristlefttranslate' + a).eval() for a in 'xyz']
    b_r = [g.parm('ikwristleftrotate' + a).eval() for a in 'xyz']
    lower_t = [b_t[i] * 0.55 + REACH['t'][i] * 0.45 for i in range(3)]
    lower_r = [b_r[i] * 0.55 + REACH['r'][i] * 0.45 for i in range(3)]
    for i, a in enumerate('xyz'):
        setkeys(g.parm('ikwristlefttranslate' + a), [(1, b_t[i]), (54, b_t[i]), (104, REACH['t'][i]), (240, REACH['t'][i]), (290, lower_t[i])])
        setkeys(g.parm('ikwristleftrotate' + a), [(1, b_r[i]), (58, b_r[i]), (106, REACH['r'][i]), (240, REACH['r'][i]), (290, lower_r[i])])

    # ---------------- 2. 손가락 이완 (손가락별 차등, 좌우 비대칭, 느린 미세 변화)
    curl = {'index': 10, 'middle': 14, 'ring': 18, 'little': 22}
    for side, off in (('left', 0.0), ('right', 3.0)):
        for fn, c in curl.items():
            for j in (2, 3):
                p = g.parm('%s%s%drotate' % (side, fn, j))
                v = c + off
                setkeys(p, [(1, v), (70, v + 2), (150, v - 1), (200, v + 2), (264, v)], flat=True)

    hou.setFrame(132)
    C = hou.Vector3(hc.worldTransform().extractTranslates())
    CR = hc.worldTransform().extractRotates()

    # ---------------- 3. 나비 경로 (키포인트 + Hermite, stop 지점은 접선 0)
    KP = [
        (1, hou.Vector3(1.22, 1.05, 0.92), False),
        (26, hou.Vector3(0.74, 1.03, 0.76), False),
        (50, hou.Vector3(0.36, 1.03, 0.46), False),
        (66, hou.Vector3(0.10, 1.00, 0.25), False),
        (84, hou.Vector3(0.32, 0.88, 0.46), False),
        (96, C + hou.Vector3(0.04, 0.13, -0.03), False),
        (104, C + hou.Vector3(0.0, 0.125, 0.0), True),
        (112, C + hou.Vector3(0.004, 0.122, 0.003), True),
        (126, C + hou.Vector3(0.0, 0.012, 0.0), True),
        (132, C, True),
        (216, C, True),
        (226, C + hou.Vector3(0.0, 0.05, 0.0), False),
        (238, C + hou.Vector3(0.01, 0.15, 0.01), False),
        (250, C + hou.Vector3(-0.12, 0.32, 0.10), False),
        (264, hou.Vector3(-0.40, 1.38, 0.58), False),
    ]

    def tangent(i):
        f, p, stop = KP[i]
        if stop:
            return hou.Vector3(0, 0, 0)
        a = KP[max(i - 1, 0)]; b = KP[min(i + 1, len(KP) - 1)]
        return (b[1] - a[1]) * (1.0 / max(b[0] - a[0], 1))

    def path(f):
        for i in range(len(KP) - 1):
            f0, p0, _ = KP[i]; f1, p1, _ = KP[i + 1]
            if f0 <= f <= f1:
                h = f1 - f0; s = (f - f0) / h
                m0 = tangent(i) * h; m1 = tangent(i + 1) * h
                h00 = 2 * s**3 - 3 * s**2 + 1; h10 = s**3 - 2 * s**2 + s
                h01 = -2 * s**3 + 3 * s**2; h11 = s**3 - s**2
                return p0 * h00 + m0 * h10 + p1 * h01 + m1 * h11
        return KP[-1][1]

    def bob(f):
        w = 1.0 if f <= 96 else max(0.0, 1 - (f - 96) / 14.0)
        if 132 <= f <= 222:
            w = 0.0
        if f > 222:
            w = min(1.0, (f - 222) / 20.0) * 0.6
        return hou.Vector3(0.004 * math.sin(f * 0.23 + 1.0), 0.014 * math.sin(f * 0.42), 0.003 * math.sin(f * 0.17)) * w

    pos = {f: path(f) + bob(f) for f in range(1, 265)}
    for a in 'xyz':
        body.parm('t' + a).deleteAllKeyframes(); body.parm('r' + a).deleteAllKeyframes()
    prev_yaw = None
    for f in range(1, 265):
        p = pos[f]
        for i, a in enumerate('xyz'):
            k = hou.Keyframe(); k.setFrame(f); k.setValue(p[i]); k.setExpression('linear()', hou.exprLanguage.Hscript)
            body.parm('t' + a).setKeyframe(k)
        v = pos[min(f + 1, 264)] - pos[max(f - 1, 1)]
        yaw = math.degrees(math.atan2(v[0], v[2])) if math.hypot(v[0], v[2]) > 1e-4 else (prev_yaw or 0)
        if prev_yaw is not None:
            while yaw - prev_yaw > 180: yaw -= 360
            while yaw - prev_yaw < -180: yaw += 360
        prev_yaw = yaw
        # 착지 전후 접점 회전으로 블렌드
        if 118 <= f <= 226:
            w = 1.0
            if f < 132: w = (f - 118) / 14.0
            if f > 216: w = 1 - (f - 216) / 10.0
            w = w * w * (3 - 2 * w)
        else:
            w = 0.0
        rot = [CR[0] * w, yaw * (1 - w) + CR[1] * w, CR[2] * w]
        for i, a in enumerate('xyz'):
            k = hou.Keyframe(); k.setFrame(f); k.setValue(rot[i]); k.setExpression('linear()', hou.exprLanguage.Hscript)
            body.parm('r' + a).setKeyframe(k)

    # ---------------- 4. 날갯짓 (서브프레임 키, 위상 적분)
    def flap_params(f):
        if f < 97: return 6.0, 45, 35
        if f < 110: return 6.5, 38, 35
        if f < 132: return 7.5 + (f - 110) * 0.05, 28 - (f - 110) * 0.6, 35
        if f < 217: return None
        if f < 245: return 3.0 + (f - 217) * 0.12, 20 + (f - 217) * 0.9, 38
        return 6.5, 44, 35

    for side, damp, dph in (('L', 1.0, 0.0), ('R', 0.96, 0.15)):
        p = bf.node('CTRL_wing_' + side).parm('flap')
        p.deleteAllKeyframes()
        phase = 0.0
        t = 1.0
        while t <= 264.0:
            fp = flap_params(t)
            if fp is None:
                # 손 위: 반쯤 펼친 상태에서 천천히 2~3회 여닫기 (주기 28프레임)
                s = (t - 132) / 13.0
                settle = min(1.0, s)
                base = 35 + (50 - 35) * settle
                val = base + 28 * math.sin(2 * math.pi * (t - 145) / 28.0 + math.pi / 2) * min(1.0, max(0.0, (t - 136) / 10.0))
                if t > 208:
                    val = val * (1 - min(1.0, (t - 208) / 9.0)) + 35 * min(1.0, (t - 208) / 9.0)
                phase = 0.0
            else:
                hz, amp, off = fp
                phase += 2 * math.pi * hz * (0.25 / FPS)
                val = off + amp * damp * math.sin(phase + dph)
            k = hou.Keyframe(); k.setFrame(t); k.setValue(val); k.setExpression('linear()', hou.exprLanguage.Hscript)
            p.setKeyframe(k)
            t += 0.25

    # ---------------- 5. 머리 시선 (3프레임 지연 추적, 발견 블렌드, 교감 중 head tilt)
    hb = g.node('rig_bone_head')
    hou.setFrame(1)
    hpos = hou.Vector3(hb.worldTransform().extractTranslates())
    raw = {}
    for f in range(1, 265):
        d = pos[f] - hpos
        yaw = math.degrees(math.atan2(d[0], d[2]))
        pitch = math.degrees(math.atan2(d[1], math.hypot(d[0], d[2])))
        raw[f] = (max(-65, min(65, yaw)), max(-40, min(35, pitch)))
    for name in ('headrotatex', 'headrotatey', 'headrotatez'):
        g.parm(name).deleteAllKeyframes()
    for f in range(1, 265, 2):
        src = max(1, f - 3)
        # 3프레임 지연 + 5프레임 이동평균
        ys = [raw[max(1, min(264, src + k))] for k in range(-2, 3)]
        yaw = sum(y[0] for y in ys) / 5.0; pitch = sum(y[1] for y in ys) / 5.0
        disc = min(1.0, max(0.0, (f - 12) / 26.0)); disc = disc * disc * (3 - 2 * disc)
        rest_pitch = -12.0  # 처음엔 약간 아래를 봄
        yaw_v = yaw * disc
        pitch_v = rest_pitch * (1 - disc) + pitch * disc
        tilt = 7.0 * math.sin(math.pi * min(1, max(0, (f - 150) / 56.0)))
        for name, v in (('headrotatey', yaw_v * 0.9), ('headrotatex', -pitch_v * 0.9), ('headrotatez', tilt)):
            k = hou.Keyframe(); k.setFrame(f); k.setValue(v)
            k.setExpression('bezier()', hou.exprLanguage.Hscript); k.setSlopeAuto(True); k.setInSlopeAuto(True)
            g.parm(name).setKeyframe(k)

    hou.setFrame(1)
    hou.hipFile.save(OUT)
    return OUT


if __name__ == '__main__':
    build()
