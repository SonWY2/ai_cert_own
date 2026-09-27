# 평가 항목-증적 추적 인덱스

- 상태: Git 정적 스캔·그래프 문맥·5관점 승인형 진단·출처 전용 5종 봉인 보고서·일회용 RunManifest 승인 및 미인증 실행 흔적 검증기 구현. 소유자 승인 개발 사례에서 두 모델을 실제로 호출했으나 강한 단일 결과는 거절됐고 작은 모델의 유효 후보는 0건이었다. 자원 제한이 강제된 대상 코드 실행·독립 최종 oracle·프로젝트 최종 성과는 미검증. [관측 범위와 차단 조건](03-ai-pipeline-technical-design.md)을 우선한다.
- 목적: 심사 기준에서 설계·실행·감사 증거까지 추적
- 현재 적용 범위와 평가 주장은 [Wayfinder 동결 명세](../../.wayfinder/ai-a-plus-code-health/field-input-manifest.yaml)가 우선한다. 아래 기존 인덱스의 사람 시간·재작업 등 구상은 현재 평가 목표가 아니다.

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

구현 진입점: [`scan_sources.py`](../../src/scan_sources.py)는 Git 원본에서 정적 출처를 만든다. [`plan_scan.py`](../../src/plan_scan.py)는 main·후보 범위를 선택한다. [`diagnose_approved.py`](../../src/diagnose_approved.py)는 일회용 승인 아래 다섯 관점의 모델 후보를 수집하고 미분석 범위를 기록한다. [`run_approved.py`](../../src/run_approved.py)는 Docker 자원 한도 지원을 확인한 뒤 승인된 명령만 실행하도록 구현됐으나, 현재 WSL 호스트에서는 거절된다. [`seal_report.py`](../../src/seal_report.py)는 Git 근거·선택 범위를 대조해 불변 출처 전용 보고서를 만든다. [`evaluate_cases.py`](../../src/evaluate_cases.py)는 평가자가 별도 봉인한 입력만 오프라인 검증·집계하며 실제 평가 결과는 없다.

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

운영 준비 증거가 없어 사업화 가능한 시스템 수준은 입증되지 않았다. 사내 자산 수준도 실제 사용 근거가 있어야 판단할 수 있다.

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
| Graph | Git AST·심볼·import·호출 문맥 및 바이트 한도 구현, 실제 공개 저장소 문맥 크기 관찰 | 동일 예산 localization·품질·토큰 ablation |
| Profiler | 신뢰한 기존 cProfile 파일의 미인증 요약·Git 함수 위치 확인, 승인형 cProfile 실행 코드; 대상 profiler 실행 없음 | 재현 workload·승인 실행·gold trigger P/R·overhead |
| DAG | bounded 계약 | loop/fixed-chain same-B_run 비교 |
| Runtime safety | RunManifest 수동 승인·1회 소비·Docker 호스트 확인 구현; 현 호스트의 cgroup 한도 미지원은 **경고 후 개발용 실행 허용**, 자원 강제 미입증 | 자원 강제 호스트의 exact-match deny/allow·격리 실행 증거 |
| Grounding | Git blob·심볼 문맥의 파일·줄 재검사와 출처 전용 보류 보고서 구현; 미검증 모델 주장은 `report.md`에 별도 표시 | 독립 oracle에서 최종 무근거 발견률 ≤5%, 근거 없는 확증 0건 |
| 진단·실행·사용자 리포트 연결 | 단일 CLI·실패 원인 분리·검증된 실행 발췌·5종 봉인 파생 Markdown 구현; 통합 CLI는 임시 Git과 시험용 승인/응답에서 확인. 별도 공개 Prefect 좁은 Docker 실행과 Starlette 두 모델 호출은 **개발용**, 이 통합 경로의 최종 기능 실증이 아님 | 승인형 모델·가설별 선택 실행·독립 판정 경로와 최종 강제 격리 정확도 관문 |
| 강한 단일 모델 대비 문제 발견률·호출 비용 | 현행 v30의 복수 결함·누락·오탐·신고 비용 집계는 시험용 입력에서만 확인. Starlette 새 프롬프트 공개 개발 네 진단의 수정 전 강한 모델은 알려진 EOF 읽기 루프 임시 접수 1건, 작은 모델은 동일 원인의 중복 접수 2건·부정확한 위치·한 관점 실패; 실제 USD 청구 없음. P1 새 지침과 P2 구조 카드·P3 개발 비교기는 합성 CLI·고정 Git 오프라인 경로만 확인 | 봉인된 동일 사례에서 독립 판정한 결함 단위 Recall 차이·신뢰구간·고유 발견 및 누락·원본 API 청구 금액·TP당 비용 |
| 20분 내 유효 권고율(동일 작은 모델의 6군 기여 검증) | 시험용 평가 CLI만 구현, 최종 실측 없음 | 봉인된 80개 사례에서 동예산 6군, 일반 LLM 대비 +30%p·CI·중요 위험 부당 기각 0건 |
| 이미 제출한 기획서의 사람 시간 50%·재작업 30%·리뷰 생산성 | 미측정·제안서 수정 초안에서 무인 목표로 대체 | 수정본의 공식 접수·수용 확인 전에는 기존 약속 달성 주장 금지 |
| Final validity | 설계 완료 | locked temporal/OOD 1회 + HackDetect-style audit |
| 시스템 A+ | 운영 gate 정의 | auth/retention/audit/SLO/recovery/owner |

Pilot 60건은 KPI 계약 검증용이다. 현행 v30의 최종 설계는 봉인된 80건에 강한 단일 모델 비교를 추가하고 동일 작은 모델 6군을 별도로 유지한다. 두 비교 모두 실제 최종 입력·결과가 없으며, 각 층과 결함 단위 분모의 충족 여부를 보고해야 한다.

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

현재는 정적 출처·Code Graph·승인형 다섯 관점·실행 전 관측 연결의 개발 경로·단일 CLI와 파생 Markdown·출처 전용 5종 보고서·오프라인 평가 입력 검증기까지 구현됐다. 시험용 모델 응답과 실행 trace 및 평가 기록은 프로젝트 성과가 아니다. 대상 저장소 승인 실행·독립 oracle·봉인된 최종 80사례가 없어 위험 확증 및 PROJECT RESULT는 아직 없다. 최종 동결 자료의 평가 관문을 통과한 항목만 결과보고서 주장으로 승격한다.

