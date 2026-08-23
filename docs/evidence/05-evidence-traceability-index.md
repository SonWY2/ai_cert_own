# 평가 항목-증적 추적 인덱스

- 상태: 2026-08-23 감사 반영, 구현·실측 전
- 목적: 심사 기준에서 설계·실행·감사 증거까지 추적

## 1. 문서 목록

| ID | 문서 | 질문 | 상태 |
| --- | --- | --- | --- |
| D-00 | [`../eval-rubric-analysis.md`](../eval-rubric-analysis.md) | A+에 무엇을 입증하는가? | 감사 반영 |
| ADR-01 | [`../ai-selection-matrix/01-multi-perspective-diagnosis-adr.md`](../ai-selection-matrix/01-multi-perspective-diagnosis-adr.md) | 왜 5관점 taxonomy와 가설 중심 적응형 진단인가? | 제안 |
| ADR-02 | [`../ai-selection-matrix/02-code-context-retrieval-adr.md`](../ai-selection-matrix/02-code-context-retrieval-adr.md) | 왜 bounded Code Graph인가? | 제안 |
| ADR-03 | [`../ai-selection-matrix/03-profiler-in-the-loop-adr.md`](../ai-selection-matrix/03-profiler-in-the-loop-adr.md) | 왜 selective profiler인가? | 제안 |
| ADR-04 | [`../ai-selection-matrix/04-agent-orchestration-adr.md`](../ai-selection-matrix/04-agent-orchestration-adr.md) | 왜 bounded DAG인가? | 제안 |
| E-01 | [`01-kpi-measurement-framework.md`](01-kpi-measurement-framework.md) | KPI를 어떻게 측정하는가? | 감사 반영 |
| E-02 | [`02-benchmark-and-ablation-plan.md`](02-benchmark-and-ablation-plan.md) | 기여와 우월성을 어떻게 검증하는가? | 감사 반영 |
| E-03 | [`03-ai-pipeline-technical-design.md`](03-ai-pipeline-technical-design.md) | pipeline은 어떻게 실행되는가? | 감사 반영 |
| E-04 | [`04-external-technical-evidence.md`](04-external-technical-evidence.md) | 최신 근거와 한계는 무엇인가? | 최신성 감사 완료 |
| E-06 | [`06-design-audit-report.md`](06-design-audit-report.md) | 무엇을 발견·교정했는가? | 문서 감사 통과 |
| E-07 | [`07-ai-technology-advancement-research.md`](07-ai-technology-advancement-research.md) | 어떤 AI 기술을 추가·고도화할 것인가? | 심층 조사 완료, pilot 권고 |
| E-08 | [`08-ai-advancement-evidence-ledger.json`](08-ai-advancement-evidence-ledger.json) | AI 고도화 권고의 근거와 한계는 무엇인가? | 1차 출처 검증 |
| E-09 | [`09-ai-advancement-review-artifacts.json`](09-ai-advancement-review-artifacts.json) | 원시 조사·점수·반증이 최종 판정에 어떻게 연결됐는가? | 원시 트랙 URI/hash·판정·사전등록 보존 |
| E-10 | [`10-ai-advancement-research-brief.json`](10-ai-advancement-research-brief.json) | 조사 질문·범위·최신성·완료 기준은 무엇인가? | 입력 계약·hash 보존 |

## 2. 심사 기준 추적

| 평가 항목 | 설계 근거 | 실행 증적 | A+ gate |
| --- | --- | --- | --- |
| 문제 정의 10% | D-00, ADR 후보표 | 등록 후보의 Pareto 결과 | 제약 내 Pareto 구성 |
| 성과 지표 10% | E-01 | final KPI raw/CI | 분모·power·holdout 적합 |
| 제안서 달성 10% | E-03, E-07 | 정상/실패 end-to-end trace | fixed-five baseline 작동 후 승격된 routing 계약 검증 |
| 시스템 완성도 10% | D-00 §6 | auth/retention/audit/SLO/recovery/owner | 사업화 수준 운영 증거 |
| 기술 이해도 20% | ADR-01~04, E-04, E-07 | config·한계·실험 | 설정의 FACT/INFERENCE 구분 |
| AI기술 선택 20% | ADR, E-02, E-07 | same-B_run B2~P4-F5/S1/S2/C1/C2와 critic·probe pilot | 추가 계산량과 기술 효과 분리 |
| 최적화 20% | E-02 ablation | quality/cost Pareto | graph/planner/router/DAG/hypothesis/gate 독립 기여 |

운영 준비 증거가 없으면 시스템 완성도는 A급 내부 자산으로 제한한다.

## 3. 기획 요구 추적

| 요구 | 설계 | 완료 증거 |
| --- | --- | --- |
| Python 백엔드 | E-03 §3~4 | Python 3.14 manifest/fixtures |
| 구조/정확성/성능/동시성/테스트 | ADR-01, E-03 §7, E-07 §4 | arm별 perspective disposition·contributor·missed-gold audit |
| 진단 계획 | ADR-04, E-03 §7, E-07 §4 | DiagnosisPlan v2 + Plan Gate + perspective disposition |
| graph 문맥 | ADR-02, E-03 §5 | context manifest/expansion request |
| 가설 중심 실행 검증 | ADR-01, E-03 §9 | HypothesisContract + ExecutionPolicy + RuntimeEvidence |
| opt-in profiler | ADR-03 | request/run/result lifecycle |
| profile 요약 | ADR-03 §7, E-03 §10 | raw hash + HotspotRow |
| 결과 표준화 | ADR-01 | finding-v2 + hypothesis-v1 |
| 피드백 개선 | E-02 §11, E-07 §7 | FeedbackEvent→failure localization→regression→promotion |

Perspective 증적은 arm별로 다르다.

- Fixed-five baseline: 5개 contributor terminal이 모두 필요하다.
- Shadow planner: 5개 disposition과 5개 contributor terminal을 모두 보존한다. Shadow 출력은 gold가 아니다.
- Routed arm: 5개 disposition, `run` 관점의 contributor terminal, blind missed-gold audit, fallback reason을 보존한다.
- Routed arm 요구는 E-07의 pilot gate를 통과해 승격된 경우에만 적용한다.

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
3. E-07/E-08/E-09/E-10에서 AI 고도화 권고·근거 원장·원시 트랙·판정·조사 계약을 확인
4. ADR에서 계약·설정·한계 확인
5. E-04에서 FACT/INFERENCE/TARGET 구분 확인
6. E-03에서 source→graph→Finding→RuntimeEvidence→report 추적
7. E-01/E-02에서 gold, budget, power, holdout, ablation 확인
8. 구현 후 사례 증적을 역추적

## 9. 결론

현재는 감사된 설계와 실험 계약이다. PROJECT RESULT는 없다. E-02 final gate를 통과한 항목만 결과보고서 주장으로 승격한다.

