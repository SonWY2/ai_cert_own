# 평가 항목-증적 추적 인덱스

- 상태: 2026-08-23 감사 반영, 구현·실측 전
- 목적: 심사 기준에서 설계·실행·감사 증거까지 추적

## 1. 문서 목록

| ID | 문서 | 질문 | 상태 |
| --- | --- | --- | --- |
| D-00 | [`../eval-rubric-analysis.md`](../eval-rubric-analysis.md) | A+에 무엇을 입증하는가? | 감사 반영 |
| ADR-01 | [`../ai-selection-matrix/01-multi-perspective-diagnosis-adr.md`](../ai-selection-matrix/01-multi-perspective-diagnosis-adr.md) | 왜 hybrid 5관점인가? | 제안 |
| ADR-02 | [`../ai-selection-matrix/02-code-context-retrieval-adr.md`](../ai-selection-matrix/02-code-context-retrieval-adr.md) | 왜 bounded Code Graph인가? | 제안 |
| ADR-03 | [`../ai-selection-matrix/03-profiler-in-the-loop-adr.md`](../ai-selection-matrix/03-profiler-in-the-loop-adr.md) | 왜 selective profiler인가? | 제안 |
| ADR-04 | [`../ai-selection-matrix/04-agent-orchestration-adr.md`](../ai-selection-matrix/04-agent-orchestration-adr.md) | 왜 bounded DAG인가? | 제안 |
| E-01 | [`01-kpi-measurement-framework.md`](01-kpi-measurement-framework.md) | KPI를 어떻게 측정하는가? | 감사 반영 |
| E-02 | [`02-benchmark-and-ablation-plan.md`](02-benchmark-and-ablation-plan.md) | 기여와 우월성을 어떻게 검증하는가? | 감사 반영 |
| E-03 | [`03-ai-pipeline-technical-design.md`](03-ai-pipeline-technical-design.md) | pipeline은 어떻게 실행되는가? | 감사 반영 |
| E-04 | [`04-external-technical-evidence.md`](04-external-technical-evidence.md) | 최신 근거와 한계는 무엇인가? | 최신성 감사 완료 |
| E-06 | [`06-design-audit-report.md`](06-design-audit-report.md) | 무엇을 발견·교정했는가? | 재감사 예정 |

## 2. 심사 기준 추적

| 평가 항목 | 설계 근거 | 실행 증적 | A+ gate |
| --- | --- | --- | --- |
| 문제 정의 10% | D-00, ADR 후보표 | 등록 후보의 Pareto 결과 | 제약 내 Pareto 구성 |
| 성과 지표 10% | E-01 | final KPI raw/CI | 분모·power·holdout 적합 |
| 제안서 달성 10% | E-03 | 정상/실패 end-to-end trace | 5관점·실행·profiler 전부 작동 |
| 시스템 완성도 10% | D-00 §6 | auth/retention/audit/SLO/recovery/owner | 사업화 수준 운영 증거 |
| 기술 이해도 20% | ADR-01~04, E-04 | config·한계·실험 | 설정의 FACT/INFERENCE 구분 |
| AI기술 선택 20% | ADR, E-02 | same-B_run B2~P4/C1/C2 | 추가 계산량과 기술 효과 분리 |
| 최적화 20% | E-02 ablation | quality/cost Pareto | graph/router/DAG/gate 독립 기여 |

운영 준비 증거가 없으면 시스템 완성도는 A급 내부 자산으로 제한한다.

## 3. 기획 요구 추적

| 요구 | 설계 | 완료 증거 |
| --- | --- | --- |
| Python 백엔드 | E-03 §3~4 | Python 3.14 manifest/fixtures |
| 구조/정확성/성능/동시성/테스트 | ADR-01, E-03 §7 | 관점별 contributor Finding |
| 진단 계획 | ADR-04 | planner + bounded DAG trace |
| graph 문맥 | ADR-02, E-03 §5 | context manifest/expansion request |
| focused test | E-03 §3, §9 | ExecutionPolicy + RuntimeEvidence |
| opt-in profiler | ADR-03 | request/run/result lifecycle |
| profile 요약 | ADR-03 §7, E-03 §10 | raw hash + HotspotRow |
| 결과 표준화 | ADR-01 | finding-v2 |
| 피드백 개선 | E-02 §11 | FeedbackEvent→proposal→regression→promotion |

## 4. 제한 사항 방어

| 제한 | 방어 | 증거 |
| --- | --- | --- |
| 단순 LLM | deterministic graph + runtime feedback | graph/evidence trace |
| prompt-only | retrieval/router/DAG/gate | ablation |
| 노코드 | extractor/resolver/pruner/router/normalizer | source/test |
| 단일 복제 | 과제 고유 schema/policy/gold | versioned artifacts |

## 5. 증거 ID와 공통 provenance

| ID | 의미 |
| --- | --- |
| `E-AST` | AST fact |
| `E-GRAPH` | graph path |
| `E-CFG` | control-flow path |
| `E-TEST` | focused test |
| `E-PROFILE` | profile |
| `E-JUDGE` | blind adjudication |
| `E-KPI` | KPI result |
| `E-AUDIT` | protocol/design audit |

모든 runtime 증거는 `case_id`, `run_id`, `execution_policy_id`, source/graph/command/workload/environment/policy hash, tool/version, raw URI/SHA-256, redaction manifest를 가진다.

## 6. 사례별 증적 묶음

```text
case/<case_id>/
  manifest.yaml
  gold/locked-manifest.ref
  variants/<variant>/<trial>/run.yaml
  policy/execution-policy.yaml
  graph/snapshot.json
  retrieval/context-manifest.json
  retrieval/expansion-requests.json
  findings/contributors.json
  findings/gated.json
  runtime/<evidence-id>/raw.*
  runtime/<evidence-id>/envelope.yaml
  runtime/<evidence-id>/hotspots.json
  review/adjudication.json
  audit/protocol-validity.json
```

## 7. A+ evidence ledger

| Gate | 현재 | 완료 조건 |
| --- | --- | --- |
| 문제·후보 정의 | 설계 완료 | registered Pareto 비교 |
| KPI 계약 | 감사 반영 | powered final holdout |
| Graph | 최신 외부 가능성 확인 | project localization ablation |
| Profiler | current tools·rule 계약 | gold trigger P/R·overhead |
| DAG | bounded 계약 | loop/fixed-chain same-B_run 비교 |
| Runtime safety | policy 설계 | exact-match deny/allow 실행 |
| Grounding | gate 설계 | ≤5%, confirmed violation 0 |
| 시간 50% | 미측정 | counterbalanced human study |
| 재작업 30% | 미측정 | 4주 추적 |
| Final validity | 설계 완료 | locked temporal/OOD 1회 + HackDetect-style audit |
| 시스템 A+ | 운영 gate 정의 | auth/retention/audit/SLO/recovery/owner |

Pilot 60건은 KPI 계약 검증용이다. Final claim 수는 power analysis로 정한다.

## 8. 심사위원 검증 순서

1. E-06에서 초기 결함과 교정을 확인
2. D-00에서 bounded A+ claim과 최신성 정책 확인
3. ADR에서 계약·설정·한계 확인
4. E-04에서 FACT/INFERENCE/TARGET 구분 확인
5. E-03에서 source→graph→Finding→RuntimeEvidence→report 추적
6. E-01/E-02에서 gold, budget, power, holdout, ablation 확인
7. 구현 후 사례 증적을 역추적

## 9. 결론

현재는 감사된 설계와 실험 계약이다. PROJECT RESULT는 없다. E-02 final gate를 통과한 항목만 결과보고서 주장으로 승격한다.

