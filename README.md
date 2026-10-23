# AI 에이전트 3D 애니메이션 지시문 표현 유형 실험 — 재현 자료

논문: 한명희, 「AI 에이전트 기반 3D 애니메이션 제작에서 지시문 표현 유형이 요구사항 충족도와 국소 수정 보존성에 미치는 영향 — Houdini MCP 환경에서의 실험적 검증 —」

이 저장소는 논문의 실험 1·2·3을 독립적으로 검증하거나 재실행하는 데 필요한 자료를 담고 있습니다.

- 실험 1: 지시 유형 비교(서술형 N, 기술형 T, 수치형 Q, 혼합형 M) 각 3회
- 실험 2: 국소 수정 보존성(R1~R3 × 보존 조항 P+/P−) 각 2회
- 실험 3: 심사 대응 대조 실험(기술형+수치 C, 서술형+검증 절차 NV, 기술형+검증 절차 TV) 각 3회

## 폴더 구성

| 폴더 | 내용 |
|---|---|
| `prompts/` | 시행별로 에이전트에 실제 입력된 메시지 원문(1차 지시, 재작업 지시, 중단 후 재개 메시지)을 작업 기록에서 그대로 추출 |
| `transcripts/` | 시행별 에이전트 작업 기록 정제본(JSONL: 지시, 도구 호출과 입력, 도구 결과(4,000자 초과 시 절단), 에이전트 문장과 보고, 시각) |
| `specs/` | 지시 유형별 지시문 전체(실험 1: N·T·Q·M, 실험 3: C·NV·TV)와 생성기(`specs.py`, `specs2.py`, `specs3.py`) |
| `data/measure/` | 시행·라운드별 30개 항목 측정 원자료(JSON, 항목별 측정값과 통과 여부) |
| `data/` | 요약 자료(`e1_summary.json`, `e2_summary.json`, `e3_summary.json`), 시행별 원점수표(`scores_by_trial.csv`), 통계 결과(`stats_exact.json`), 자기 검증 행동 분석(`selfcheck.json`) |
| `analysis/` | 측정 스크립트(`measure.py` 실험 1·3, `measure2.py`·`e2_eval.py` 실험 2), 비용 산출(`cost.py`), 통계(`analyze_e1.py`, `stats_exact.py`), 자기 검증 분석(`selfcheck.py`) |
| `houdini/` | 기준 씬(`base_scene.hip`), 검증용 기준 해(`reference.hip`), 기준 해 생성 스크립트, 시행별 결과 HIP |
| `mcp_server/` | 실험에 사용한 Houdini MCP 서버(외부 프로세스)와 Houdini 내부 브리지 |
| `logs/` | 시행 순서(무작위, seed 2026), 라운드별 기록(`trials.jsonl`), 측정 도구 변경 이력(`decisions.md`), 실행 조건(`run_conditions.json`) |

## 실행 조건

- DCC: SideFX Houdini 22.0.466 Non-Commercial, 24fps, Windows 11
- 에이전트: Claude Code(빌드 버전은 `logs/run_conditions.json`에 시행별 기록) 하위 에이전트(`general-purpose` 유형, 백그라운드 실행)
- 모델 식별자: `claude-opus-5-5`, 추론 강도(effort) medium, 확장 사고(thinking) 사용, fast mode 미사용
- 시행마다 새 하위 에이전트를 생성하였으므로 이전 시행의 대화 문맥은 공유되지 않습니다. 하위 에이전트의 시스템 프롬프트는 Claude Code가 제공하는 `general-purpose` 기본값이며, 연구자가 추가한 지시는 `prompts/`의 원문뿐입니다.
- 온도 등 샘플링 매개변수는 Claude Code에서 사용자가 지정할 수 없으므로 기본값입니다. 같은 지시문으로도 결과가 달라질 수 있습니다.

## 재측정 방법

1. Houdini 22.0을 실행하고 `mcp_server/houdini/`를 Houdini 패키지 경로에 등록합니다(브리지가 127.0.0.1:9876에서 대기).
2. Houdini Python 셸 또는 MCP의 `execute_python`에서 다음을 실행합니다.

```python
ms = {}
exec(open('analysis/measure.py', encoding='utf-8').read(), ms)
r = ms['run']('houdini/trials/E1_Q_r1_v0.hip', None, 'houdini/base_scene.hip')
print(r['achievement'], r['constraint'])
```

3. `analysis/stats_exact.py`는 Houdini 없이 일반 Python(numpy, scipy)으로 실행됩니다.

## 정제 기준

- 원본 작업 기록에는 실행 환경의 계정 정보(이메일 등)와 클라이언트 내부 기록이 포함되어 있어 공개하지 않았습니다. `transcripts/`는 `analysis/export_release.py`로 지시·도구 호출·도구 결과·에이전트 출력만 추린 것이며, 사용자 홈 경로는 `<HOME>`으로 바꾸었습니다.
- 원본 기록은 연구자가 보관하며, 검증 목적의 요청이 있으면 개인 정보를 가린 형태로 제공합니다.
- HIP 파일 내부에는 제작 환경의 Houdini 사용자 설정 경로(Windows 계정명)가 남아 있습니다.

## 라이선스와 주의

- 측정·분석 코드와 지시문은 연구 검증 목적으로 공개합니다.
- HIP 파일은 Houdini Non-Commercial(.hipnc 성격)로 제작되었습니다.
- 선행 사례(MGS KOREA, 2026)의 원본 작업지시서와 영상은 포함하지 않습니다.
