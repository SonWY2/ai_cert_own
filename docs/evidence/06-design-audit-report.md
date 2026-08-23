# AI 설계 다각도 감사 보고서

- 감사일: 2026-08-23
- 대상: `docs/eval-rubric-analysis.md`, ADR 4개, evidence 문서, proposal/evaluation criteria
- 상태: 초기 설계 문서 감사 통과; 후속 가설 중심 적응형 계약 반영, 구현·성과 미측정

## 1. 방법

서로 독립된 4개 관점으로 문서를 검토했다.

1. AI 기술 선택과 Lv3 적합성
2. KPI·통계·benchmark 타당성
3. pipeline·상태·권한·증거 계약
4. 외부 출처의 날짜·수치·적용 범위

각 검토자는 기존 결정을 지지하지 말고 반박하도록 지시했다. 1차 결과는 Critical 0건, Major 34건, Minor 7건이었다. 같은 원인의 중복을 포함한 원시 finding 수이며 결함 수로 부풀리지 않는다.

## 2. 핵심 발견과 조치

| 영역 | 발견 | 조치 |
| --- | --- | --- |
| 최신성 | RepoGraph, CGM, GraphCoder, When2Call, 과거 Scalene 수치가 현재 선택 근거에 남아 있음 | 현재 선택 목록에서 제거하고 2026 자료·공식 release로 교체 |
| Graph | 오래된 1-hop 결과가 프로젝트 기본값을 확정 | 1-hop/80 node/24k를 pilot 가설로 강등, LARGER·Codebase-Memory로 현재 가능성만 지지 |
| DAG | first-pass severity가 pre-retrieval 2-hop을 만드는 순환 계약 | typed expansion request와 1회 second-stage DAG로 변경 |
| 실행 안전 | 승인된 명령의 exact contract 없음 | immutable ExecutionPolicy와 command manifest 추가 |
| Finding | perspective, merge key, confidence, severity가 불명확 | contributor 배열, root-cause taxonomy, canonical location, severity rubric v1, confidence 제거 |
| Runtime state | profiler lifecycle와 Finding verification enum 불일치 | request/run/result 3개 상태축과 deterministic mapping 통일 |
| Router | 학습 전 초기 rule과 cost threshold가 구현 불가 | 명시적 ordered rule·eligibility·tie-break 추가, 고정 100 label 제거 |
| Evidence | normalized row가 source/workload/policy provenance를 잃음 | RuntimeEvidence v1 envelope 추가 |
| KPI 3 | 실행 시도와 실행 확인을 같은 분자에 포함 | confirmation rate와 attachment rate 분리 |
| KPI 4 | system candidate가 활용률 분모를 결정 | evaluator-owned beneficial/neutral/harmful gold table 도입 |
| Human KPI | machine latency와 reviewer time 혼동 | 전체 reviewer decision time을 1차 KPI로 변경 |
| Benchmark | P3/P4의 gate가 달라 router 효과 confound | gate 고정, P4-NG와 2×2 ablation 추가 |
| DAG benchmark | fixed-chain 기준선 없음 | same-router fixed chain C1과 mandatory chain C2 추가 |
| 비용 공정성 | multi-agent가 더 많은 token으로 Recall을 살 수 있음 | 모든 agent/retry/cache를 포함한 B_run 도입 |
| 표본 | 60건을 최종 근거처럼 사용 | 60건은 pilot, final 수는 power analysis, locked temporal/OOD 1회 평가 |
| Feedback | producing run·artifact를 완전히 참조하지 않음 | FeedbackEvent v2와 immutable version/hash chain 추가 |
| A+ 완성도 | 내부 재사용 증거를 사업화 수준으로 해석 | auth/retention/audit/SLO/recovery/owner 최소 gate 추가 |

## 3. 최신성 기준

- 원칙: 2026-02-23 이후 자료
- 예외: 6개월 내 대체가 없을 때 2025-08-23 이후 자료와 이유
- 현재 official docs/release는 운용 기능 근거로 허용
- 오래된 연구 수치는 현재 성능·설정 선택에서 제거
- preprint/vendor 결과는 독립 재현 전 일반화 금지

## 4. 교체한 현재 근거

### Code retrieval

- [LARGER v1, 2026-05-08](https://arxiv.org/html/2605.16352v1)
- [Codebase-Memory v1, 2026-03-28](https://arxiv.org/abs/2603.27277v1)

### Profiler·성능

- [Python 3.14.7 profiler docs, updated 2026-08-22](https://docs.python.org/3.14/library/profile.html)
- [py-spy 0.4.2, 2026-04-24](https://github.com/benfred/py-spy/releases/tag/v0.4.2)
- [Scalene 2.3.0, 2026-05-12](https://github.com/plasma-umass/scalene/releases/tag/v2.3.0)
- [SWE-Perf v2, 2026-07-01 revision](https://arxiv.org/html/2507.12415v2)
- [PERFOPT-Bench v1, 2026-07-08](https://arxiv.org/html/2607.07744v1) — self-contained C benchmark의 방법론 참고이며 Python 직접 근거가 아님; 공식 rendering의 task 수 충돌로 수는 인용하지 않음

### Selective routing

- [To Call or Not to Call v3, 2026-08-06](https://arxiv.org/abs/2605.00737v3)
- [UCCI v1, 2026-05-11](https://arxiv.org/abs/2605.18796v1)
- [CostBench v3, 2026-06-29](https://arxiv.org/abs/2511.02734v3)

### Agent evaluation

- [REAP v4, 2026-07-28 revision](https://arxiv.org/abs/2604.01527v4)
- [SWE-EVO v5, 2026-04-04 revision](https://arxiv.org/abs/2512.18470v5)
- [HackDetect v1, 2026-07-24](https://arxiv.org/abs/2607.22368v1)

## 5. 교정된 수치·주장

- To Call 최신 v3의 범위는 `6 open + 1 proprietary model, 2 tools, 6 tasks`다. 이전 v1 표 숫자는 제거했다.
- Scalene 과거 overhead 숫자는 현재 release 선택 근거에서 제거했다.
- PERFOPT v1은 arXiv API와 HTML의 task 수가 충돌하므로 task 수를 근거로 사용하지 않는다.
- LARGER/Codebase-Memory 결과는 graph 가능성의 FACT이며 프로젝트 hop/token 성능이 아니다.
- 60 cases, 3 trials, 1-hop, 80 nodes, 24k evidence tokens는 모두 TARGET 또는 pilot 설정이다.

## 6. 잔여 위험

구현·실측 전이므로 다음은 여전히 미입증이다.

- Python 3.14 resolver가 framework DI/reflection을 충분히 다루는지
- P4-F5 5관점 DAG가 같은 `B_run`의 단일 LLM/fixed chain보다 우수한지
- P4-S2 적응형 관점 선택이 Critical/High Recall을 유지하며 token·호출을 줄이는지
- semantic critic·ephemeral probe가 기존 Evidence Gate보다 유효한 추가 증거를 만드는지
- profiler gold utility를 충분한 표본에서 blind 판정할 수 있는지
- py-spy/Scalene overhead와 안정성
- final sample size와 KPI 달성
- A+ 운영 준비 gate

## 7. 현재 판정

기존 설계는 방향은 타당했지만 최신성 위반과 평가·상태 계약의 Major 문제가 있어 그대로 승인할 수 없었다. 모든 지적을 반영한 뒤 링크·fence·출처 pin·핵심 계약을 자동 검사했고, 아키텍처/계약과 KPI/평가를 맡은 독립 reviewer 2명이 최종 폐쇄 검토에서 모두 `pass`를 반환했다. 최신성 검토의 PERFOPT task-count·Graphify benchmark-date Minor 지적도 수치 미인용과 commit-pinned 출처로 교정했다. 따라서 **설계 문서 수준에서는 승인**한다. 구현 성능과 A+ KPI 달성은 §6의 잔여 위험이며 PROJECT RESULT가 생기기 전에는 승인한 것으로 간주하지 않는다.

후속 가설 중심 적응형 계약의 선택 근거·반증·사전등록은 [`07-ai-technology-advancement-research.md`](07-ai-technology-advancement-research.md), [`08-ai-advancement-evidence-ledger.json`](08-ai-advancement-evidence-ledger.json), [`09-ai-advancement-review-artifacts.json`](09-ai-advancement-review-artifacts.json)에 분리해 보존한다.
