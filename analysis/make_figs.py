# -*- coding: utf-8 -*-
"""논문 도판 생성 (그림 1~7). 출력: results/figs/fig*.png (300dpi)"""
import json, os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from PIL import Image, ImageDraw, ImageFont

ROOT = 'D:/claude/butterfly_mcp_paper'
FIG = ROOT + '/results/figs'
os.makedirs(FIG, exist_ok=True)
FONT = 'C:/Windows/Fonts/malgun.ttf'
fm.fontManager.addfont(FONT)
plt.rcParams['font.family'] = fm.FontProperties(fname=FONT).get_name()
plt.rcParams['axes.unicode_minus'] = False

SURF = '#fcfcfb'; INK = '#0b0b0b'; INK2 = '#52514e'; GRID = '#e4e3df'
STY = ['N', 'T', 'Q', 'M']
SNAME = {'N': '서술형', 'T': '기술형', 'Q': '수치형', 'M': '혼합형'}
COL = {'N': '#2a78d6', 'T': '#eb6834', 'Q': '#1baf7a', 'M': '#eda100'}   # 검증 팔레트 slot 1~4


def style_ax(ax):
    ax.set_facecolor(SURF)
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    for s in ('left', 'bottom'):
        ax.spines[s].set_color(INK2); ax.spines[s].set_linewidth(0.8)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8); ax.set_axisbelow(True)


E1 = json.load(open(ROOT + '/data/e1_summary.json', encoding='utf-8'))
E2 = json.load(open(ROOT + '/data/e2_summary.json', encoding='utf-8'))
HV = json.load(open(ROOT + '/data/hover_final.json', encoding='utf-8'))

# ---------------------------------------------------------------- 그림 1 파이프라인
fig, ax = plt.subplots(figsize=(8, 3.2), dpi=300); fig.patch.set_facecolor('white'); ax.axis('off')
ax.set_xlim(0, 100); ax.set_ylim(0, 40)
boxes = [(1, 22, '작업지시서\n(4가지 지시 유형)'), (21, 22, 'AI 에이전트\nClaude Opus 5.5\n(새 컨텍스트)'),
         (41, 22, 'Houdini MCP\n(execute_python 등)'), (61, 22, 'Houdini 씬\n기준 씬 → 결과 HIP'), (81, 22, '자동 측정\n30개 항목 판정')]
for x, y, t in boxes:
    ax.add_patch(FancyBboxPatch((x, y), 17, 13, boxstyle='round,pad=0.4,rounding_size=1.5', fc='#eef4fc', ec='#2a78d6', lw=1))
    ax.text(x + 8.5, y + 6.5, t, ha='center', va='center', fontsize=7, color=INK)
for i in range(4):
    x0 = boxes[i][0] + 17.6; x1 = boxes[i + 1][0] - 0.6
    ax.add_patch(FancyArrowPatch((x0, 28.5), (x1, 28.5), arrowstyle='-|>', mutation_scale=10, color=INK2, lw=1))
ax.add_patch(FancyBboxPatch((39, 2), 21, 11, boxstyle='round,pad=0.4,rounding_size=1.5', fc='#fdf0ea', ec='#eb6834', lw=1))
ax.text(49.5, 7.5, '재작업 지시\n미충족 항목만 · 같은 문체\n최대 2회', ha='center', va='center', fontsize=7, color=INK)
ax.add_patch(FancyArrowPatch((89.5, 21.4), (60.8, 8), connectionstyle='arc3,rad=-0.25', arrowstyle='-|>', mutation_scale=10, color='#eb6834', lw=1))
ax.add_patch(FancyArrowPatch((39, 8), (29.5, 21.4), connectionstyle='arc3,rad=-0.25', arrowstyle='-|>', mutation_scale=10, color='#eb6834', lw=1))
fig.savefig(FIG + '/fig1_pipeline.png', bbox_inches='tight', facecolor='white'); plt.close(fig)

# ---------------------------------------------------------------- 그림 2 기준 씬 (렌더 6컷)
font = ImageFont.truetype(FONT, 22)
cells = [('ref_CAM_A_MASTER_F30.png', '(a) F30 등장 · CAM_A'), ('ref_CAM_A_MASTER_F66.png', '(b) F66 얼굴 앞 통과 · CAM_A'),
         ('ref_CAM_B_HAND_F110.png', '(c) F110 손 위 정지 비행 · CAM_B'), ('ref_CAM_B_HAND_F180.png', '(d) F180 손등 착지·교감 · CAM_B'),
         ('ref_CAM_C_TRANSITION_F238.png', '(e) F238 이륙 · CAM_C'), ('ref_CAM_A_MASTER_F256.png', '(f) F256 이탈 · CAM_A')]
W, H, CAP = 640, 360, 40
sheet = Image.new('RGB', (W * 2 + 10, (H + CAP) * 3), 'white'); d = ImageDraw.Draw(sheet)
for i, (fn, cap) in enumerate(cells):
    im = Image.open(FIG + '/' + fn).convert('RGB').resize((W, H))
    x = (i % 2) * (W + 10); y = (i // 2) * (H + CAP)
    sheet.paste(im, (x, y)); d.text((x + W // 2, y + H + 8), cap, fill=INK, font=font, anchor='mt')
sheet.save(FIG + '/fig2_scene.png', dpi=(300, 300))

# ---------------------------------------------------------------- 그림 3 문체별 충족 점수
fig, ax = plt.subplots(figsize=(6.4, 3.4), dpi=300); fig.patch.set_facecolor('white'); style_ax(ax)
T = E1['trials']; xs = range(len(STY)); w = 0.34
for k, (key, lab, col) in enumerate((('first_total', '1차 결과', '#2a78d6'), ('final_total', '재작업 후 최종', '#eb6834'))):
    means = []
    for i, s in enumerate(STY):
        vals = [r[key] for r in T.values() if r['style'] == s]
        m = sum(vals) / len(vals); means.append(m)
        x = i + (k - 0.5) * (w + 0.03)
        ax.bar(x, m, width=w, color=col, edgecolor='white', linewidth=1.5, label=lab if i == 0 else None, zorder=2)
        ax.scatter([x] * len(vals), vals, s=14, color='white', edgecolor=INK, linewidth=0.7, zorder=3)
        ax.text(x, 15.4, '%.1f' % m, ha='center', va='bottom', fontsize=8, color='white', fontweight='bold')
ax.set_xticks(list(xs)); ax.set_xticklabels([SNAME[s] for s in STY], fontsize=10, color=INK)
ax.set_ylim(15, 31.5); ax.set_ylabel('충족 항목 수 (/30)', fontsize=9, color=INK2)
ax.axhline(30, color=INK2, lw=0.8, ls='--'); ax.legend(frameon=False, fontsize=8, loc='upper left', bbox_to_anchor=(0, 1.13), ncol=2)
fig.savefig(FIG + '/fig3_scores.png', bbox_inches='tight', facecolor='white'); plt.close(fig)

# ---------------------------------------------------------------- 그림 4 항목별 1차 실패 빈도 (히트맵)
ITEMNAME = {'B02_entry_accel': 'B02 첫 등장 가속', 'B05_face_pass': 'B05 얼굴 앞 통과', 'B06_hover': 'B06 착지 전 정지 비행',
            'B08_soft_landing': 'B08 부드러운 착지', 'B09_prelanding_calm': 'B09 착지 전 안정화', 'B11_prelanding_flap': 'B11 착지 직전 날갯짓',
            'B15_takeoff': 'B15 이륙 후 체공', 'G02_gaze_lag': 'G02 시선 지연', 'G03_look_at_butterfly': 'G03 교감 중 응시', 'Q01_no_pop': 'Q01 튐(pop) 없음'}
items = [k for k in ITEMNAME if sum(E1['item_fail'].get(k, [0])) > 0]
import numpy as np
M = np.array([E1['item_fail'][k] for k in items])
fig, ax = plt.subplots(figsize=(5.2, 4.2), dpi=300); fig.patch.set_facecolor('white')
cmap = matplotlib.colors.ListedColormap(['#f4f3f0', '#b5d1f4', '#5d9be6', '#1c5aa6'])
ax.imshow(M, cmap=cmap, vmin=-0.5, vmax=3.5, aspect='auto')
for i in range(M.shape[0]):
    for j in range(M.shape[1]):
        v = M[i, j]
        ax.text(j, i, str(v) if v else '·', ha='center', va='center', fontsize=9, color='white' if v >= 2 else INK)
ax.set_xticks(range(4)); ax.set_xticklabels([SNAME[s] for s in STY], fontsize=9)
ax.set_yticks(range(len(items))); ax.set_yticklabels([ITEMNAME[k] for k in items], fontsize=8.5)
ax.tick_params(length=0); [s.set_visible(False) for s in ax.spines.values()]
ax.set_xticks(np.arange(-.5, 4, 1), minor=True); ax.set_yticks(np.arange(-.5, len(items), 1), minor=True)
ax.grid(which='minor', color='white', linewidth=2); ax.tick_params(which='minor', length=0)
fig.savefig(FIG + '/fig4_items.png', bbox_inches='tight', facecolor='white'); plt.close(fig)

# ---------------------------------------------------------------- 그림 5 착지 전 hover 높이 (해석 분포)
fig, ax = plt.subplots(figsize=(6.0, 3.2), dpi=300); fig.patch.set_facecolor('white'); style_ax(ax)
ax.axhspan(10, 15, color='#1baf7a', alpha=0.12, lw=0); ax.text(-0.45, 14.6, '목표 범위 10~15cm', fontsize=8, color='#0d6b4a', va='center', ha='left')
for i, s in enumerate(STY):
    vals = [v['pre_hover_cm'] for t, v in HV.items() if t.split('_')[1] == s]
    ax.scatter([i + dx for dx in (-0.08, 0, 0.08)], vals, s=46, color=COL[s], edgecolor='white', linewidth=1.5, zorder=3)
    m = sum(vals) / len(vals); ax.plot([i - 0.22, i + 0.22], [m, m], color=INK, lw=1.2, zorder=2)
    ax.text(i + 0.26, m, '%.1f' % m, fontsize=8, va='center', color=INK)
ax.set_xticks(range(4)); ax.set_xticklabels([SNAME[s] for s in STY], fontsize=10, color=INK)
ax.set_xlim(-0.5, 3.6); ax.set_ylim(4, 16.5); ax.set_ylabel('손 위 정지 비행 높이 (cm)', fontsize=9, color=INK2)
fig.savefig(FIG + '/fig5_hover.png', bbox_inches='tight', facecolor='white'); plt.close(fig)

# ---------------------------------------------------------------- 그림 6 hover 렌더 비교
cells = [('hover_E1_N_r2_v2_F110.png', '(a) 서술형 — 7.1cm'), ('hover_E1_T_r3_v2_F110.png', '(b) 기술형 — 5.5cm'),
         ('hover_E1_Q_r3_v0_F110.png', '(c) 수치형 — 14.6cm'), ('hover_E1_M_r1_v0_F110.png', '(d) 혼합형 — 12.5cm')]
sheet = Image.new('RGB', (W * 2 + 10, (H + CAP) * 2), 'white'); d = ImageDraw.Draw(sheet)
for i, (fn, cap) in enumerate(cells):
    im = Image.open(FIG + '/' + fn).convert('RGB').resize((W, H))
    x = (i % 2) * (W + 10); y = (i // 2) * (H + CAP)
    sheet.paste(im, (x, y)); d.text((x + W // 2, y + H + 8), cap, fill=INK, font=font, anchor='mt')
sheet.save(FIG + '/fig6_hover_render.png', dpi=(300, 300))

# ---------------------------------------------------------------- 그림 7 실험 2 구간 밖 경로 편차
rows = sorted(E2['rows'], key=lambda r: (r['R'], r['P'] != 'Pp', r['trial']))
fig, ax = plt.subplots(figsize=(6.6, 3.3), dpi=300); fig.patch.set_facecolor('white'); style_ax(ax)
PC = {'Pp': '#2a78d6', 'Pm': '#eb6834'}
xpos = []; x = 0; prevR = None
for r in rows:
    if prevR and r['R'] != prevR: x += 0.8
    xpos.append(x); prevR = r['R']; x += 1
for xp, r in zip(xpos, rows):
    ax.bar(xp, max(r['path_rms_cm'], 0.05), width=0.8, color=PC[r['P']], edgecolor='white', linewidth=1.5, zorder=2)
    lab = ', '.join(g.split('_')[0] for g in r['regressions']) or '없음'
    ax.text(xp, max(r['path_rms_cm'], 0.05) + 0.25, lab, ha='center', va='bottom', fontsize=6.5, color=INK, rotation=90)
groups = {'R1': 'R1 나비 hover 연장', 'R2': 'R2 오른손 손가락', 'R3': 'R3 2~4초 장난스럽게'}
for R in ('R1', 'R2', 'R3'):
    xs_ = [xp for xp, r in zip(xpos, rows) if r['R'] == R]
    ax.text(sum(xs_) / len(xs_), -1.6, groups[R], ha='center', fontsize=8.5, color=INK)
ax.set_xticks(xpos); ax.set_xticklabels(['P+' if r['P'] == 'Pp' else 'P-' for r in rows], fontsize=8)
ax.set_ylim(0, 12.5); ax.set_ylabel('수정 구간 밖 나비 경로\nRMS 편차 (cm)', fontsize=9, color=INK2)
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=PC['Pp'], label='보존 조항 명시(P+)'), Patch(color=PC['Pm'], label='미명시(P-)')], frameon=False, fontsize=8, loc='upper right')
fig.savefig(FIG + '/fig7_e2.png', bbox_inches='tight', facecolor='white'); plt.close(fig)
print('done')
