# -*- coding: utf-8 -*-
"""실험 2 국소 수정 지시문 생성기. 수정 내용 3종(R1~R3) × 보존 조항(P+/P-)."""

REF = 'D:/claude/butterfly_mcp_paper/houdini/reference.hip'

HEADER = """[수정 지시] Houdini MCP — 기존 애니메이션 부분 수정

■ 작업 대상
- Houdini MCP 도구로 기존 씬 {ref} 를 열어 작업하고, 수정본은 {out} 로 저장한다. 원본 파일은 덮어쓰지 않는다.
- 이 씬은 소녀와 호랑나비가 만나는 11초(F1–264, 24fps) 애니메이션이 이미 완성된 상태다.

■ 씬 구성
- /obj/girl : Houdini 기본 Dummy(simplefemale). 리그 컨트롤은 노드 파라미터로 노출되어 있다(머리 headrotate*, 팔 IK ikwrist*, 손가락 left/right{{index,middle,ring,little,thumb}}{{1,2,3}}rotate 등).
- /obj/butterfly : 호랑나비. CTRL_body(위치·회전), CTRL_wing_L / CTRL_wing_R(flap 파라미터, +값이 날개를 위로).
- /obj/hand_contact : 소녀 왼손 손등의 착지 지점. 나비는 F132에 여기에 착지해 F216까지 머문 뒤 이륙한다.
- 카메라: /obj/CAM_A_MASTER, /obj/CAM_B_HAND, /obj/CAM_C_TRANSITION.

■ 공통 조건
- 렌더링은 하지 않는다. 이 작업 폴더(D:/claude/butterfly_mcp_paper)의 다른 파일은 열거나 읽지 않는다.
- 작업이 끝나면 저장 경로와 함께 무엇을 어떻게 바꿨는지 간단히 보고한다.

■ 수정 내용
"""

EDITS = {
    'R1': '착지하기 직전 나비가 손 위에서 떠 있는 시간이 너무 짧다. 손 위에서 머무는 시간을 약 1초로 늘려줘. 착지 시점(F132)은 그대로 둔다.',
    'R2': '나비와 닿지 않는 오른손이 너무 정지해 보인다. 오른손을 허벅지 위에 둔 채로, F150–200 사이에 손가락이 살짝 오므려졌다가 다시 풀리는 작은 움직임을 넣어줘.',
    'R3': '2~4초(F49–96) 구간만 나비가 더 장난스럽게 날도록 바꿔줘.',
}

PRESERVE = '- 수정 대상이 아닌 부분, 즉 나비의 다른 구간 경로와 날갯짓, 착지 프레임, 카메라, 소녀의 다른 동작은 그대로 유지해줘.'


def build(rcode, preserve, out_path):
    s = HEADER.format(ref=REF, out=out_path) + '- ' + EDITS[rcode] + '\n'
    if preserve:
        s += PRESERVE + '\n'
    return s
