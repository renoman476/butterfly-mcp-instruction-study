# -*- coding: utf-8 -*-
"""수정본 도판: 7개 조건(실험 1 N·T·Q·M + 실험 3 C·NV·TV)의 1차 충족 수와 항목별 1차 실패 빈도."""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm

ROOT = 'D:/claude/butterfly_mcp_paper'
FIG = ROOT + '/results/figs'
FONT = 'C:/Windows/Fonts/malgun.ttf'
fm.fontManager.addfont(FONT)
plt.rcParams['font.family'] = fm.FontProperties(fname=FONT).get_name()
plt.rcParams['axes.unicode_minus'] = False
INK = '#0b0b0b'; INK2 = '#52514e'; GRID = '#e4e3df'; SURF = '#fcfcfb'

E1 = json.load(open(ROOT + '/data/e1_summary.json', encoding='utf-8'))['trials']
E3 = json.load(open(ROOT + '/data/e3_summary.json', encoding='utf-8'))['trials']
CONDS = ['N', 'T', 'NV', 'TV', 'M', 'C', 'Q']
NAME = {'N': '서술형', 'T': '기술형', 'NV': '서술형\n+검증 절차', 'TV': '기술형\n+검증 절차', 'M': '혼합형\n(서술+수치)', 'C': '기술형\n+수치', 'Q': '수치형'}
GROUP = {'N': 0, 'T': 0, 'NV': 1, 'TV': 1, 'M': 2, 'C': 2, 'Q': 2}
GCOL = ['#9a9893', '#eb6834', '#2a78d6']
GLAB = ['수치 기준 없음', '수치 기준 없음 + 검증 절차', '수치 기준 있음']


def first(c):
    if c in 'NTQM' and len(c) == 1:
        return [r['first_total'] for r in E1.values() if r['style'] == c]
    return [r['first_total'] for r in E3.values() if r['cond'] == c]


def first_fails(c):
    out = []
    if len(c) == 1 and c in 'NTQM':
        for r in E1.values():
            if r['style'] == c:
                out.append(set(r['v'][0]['fails']))
    else:
        for r in E3.values():
            if r['cond'] == c:
                out.append(set(r['v'][0]['fails']))
    return out


def style_ax(ax):
    ax.set_facecolor(SURF)
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    for s in ('left', 'bottom'):
        ax.spines[s].set_color(INK2); ax.spines[s].set_linewidth(0.8)
    ax.tick_params(colors=INK2, labelsize=8.5)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8); ax.set_axisbelow(True)


# 그림: 조건별 1차 충족 수
fig, ax = plt.subplots(figsize=(6.6, 3.0), dpi=300); fig.patch.set_facecolor('white'); style_ax(ax)
for i, c in enumerate(CONDS):
    v = first(c); m = sum(v) / len(v); col = GCOL[GROUP[c]]
    ax.bar(i, m, width=0.62, color=col, alpha=0.85, edgecolor='white', linewidth=1.2, zorder=2)
    ax.scatter([i - 0.12, i, i + 0.12], sorted(v), s=13, color='white', edgecolor=INK, linewidth=0.7, zorder=3)
    ax.text(i, 18.5, '%.1f' % m, ha='center', fontsize=8.5, color='white', fontweight='bold')
ax.set_xticks(range(len(CONDS))); ax.set_xticklabels([NAME[c] for c in CONDS], fontsize=7.8, color=INK)
ax.set_ylim(18, 33.5); ax.set_ylabel('1차 충족 항목 수 (/30)', fontsize=8.5, color=INK2)
ax.axhline(30, color=INK2, lw=0.8, ls='--')
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=GCOL[k], alpha=0.85, label=GLAB[k]) for k in range(3)], frameon=False, fontsize=7.5, loc='upper left', bbox_to_anchor=(0, 1.0))
fig.savefig(FIG + '/figR_scores7.png', bbox_inches='tight', facecolor='white'); plt.close(fig)

# 그림: 항목별 1차 실패 빈도 (7개 조건)
ITEMS = ['B02', 'B05', 'B06', 'B08', 'B09', 'B11', 'B12', 'B15', 'G02', 'G03', 'G05', 'Q01', 'Q02']
INAME = {'B02': 'B02 첫 등장 가속', 'B05': 'B05 얼굴 앞 통과', 'B06': 'B06 착지 전 정지 비행', 'B08': 'B08 부드러운 착지',
         'B09': 'B09 착지 전 안정화', 'B11': 'B11 착지 직전 날갯짓', 'B12': 'B12 손 위 날개 여닫기', 'B15': 'B15 이륙 후 체공',
         'G02': 'G02 시선 지연', 'G03': 'G03 교감 중 응시', 'G05': 'G05 손 내밀기', 'Q01': 'Q01 튐 없음', 'Q02': 'Q02 몸 관통 없음'}
M = np.array([[sum(any(f.startswith(it) for f in s) for s in first_fails(c)) for c in CONDS] for it in ITEMS])
keep = [i for i in range(len(ITEMS)) if M[i].sum() > 0]
M = M[keep]; items = [ITEMS[i] for i in keep]
fig, ax = plt.subplots(figsize=(5.6, 0.32 * len(items) + 1.2), dpi=300); fig.patch.set_facecolor('white')
cmap = matplotlib.colors.ListedColormap(['#f4f3f0', '#b5d1f4', '#5d9be6', '#1c5aa6'])
ax.imshow(M, cmap=cmap, vmin=-0.5, vmax=3.5, aspect='auto')
for i in range(M.shape[0]):
    for j in range(M.shape[1]):
        v = M[i, j]
        ax.text(j, i, str(v) if v else '·', ha='center', va='center', fontsize=8.5, color='white' if v >= 2 else INK)
ax.set_xticks(range(len(CONDS))); ax.set_xticklabels([NAME[c] for c in CONDS], fontsize=7.2)
ax.set_yticks(range(len(items))); ax.set_yticklabels([INAME[k] for k in items], fontsize=8)
ax.tick_params(length=0); [s.set_visible(False) for s in ax.spines.values()]
ax.set_xticks(np.arange(-.5, len(CONDS), 1), minor=True); ax.set_yticks(np.arange(-.5, len(items), 1), minor=True)
ax.grid(which='minor', color='white', linewidth=2); ax.tick_params(which='minor', length=0)
fig.savefig(FIG + '/figR_items7.png', bbox_inches='tight', facecolor='white'); plt.close(fig)
print('items', items); print(M)
