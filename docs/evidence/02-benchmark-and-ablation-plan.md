# 기준선·Ablation 벤치마크 계획

- 상태: 2026-08-23 감사 반영, 프로젝트 결과 미측정
- 목적: 제안 기술의 독립 기여와 비용을 반증 가능하게 검증

## 1. 연구 질문

| ID | 질문 | 주 지표 |
| --- | --- | --- |
| RQ1 | Code Graph가 lexical/vector보다 cross-file evidence를 잘 찾는가? | localization/evidence Recall@K, tokens |
| RQ2 | bounded DAG가 같은 예산의 loop/fixed chain보다 좋은가? | 중요 Recall, 누락, latency, calls |
| RQ3 | runtime feedback가 환각을 줄이는가? | confirmation/rejection, grounding |
| RQ4 | 선택 profiler가 always의 품질을 유지하며 비용을 줄이는가? | gold trigger P/R, utility/cost |
| RQ5 | 전체 시스템이 실제 reviewer 성과를 높이는가? | 6 KPI, paired CI |
| RQ6 | 적응형 Planner가 fixed-five의 Recall을 유지하며 관점 비용을 줄이는가? | perspective omission, 중요 누락, tokens/calls |
| RQ7 | 가설 계약·critic·probe가 기존 Evidence Gate보다 유효한 추가 증거를 만드는가? | counterevidence, probe validity, false retraction |

## 2. 비교 구성

### 공정성 계약

모든 LLM variant는 같은 commit, task, model version, 허용 도구, evidence snapshot과 inclusive `B_run`을 사용한다. `B_run`에는 input/output/cached tokens, planner, 실행 관점, retry, critic, gate, composer가 포함된다. Evaluator-only fixed-five shadow·gold adjudication 비용은 운영 `B_run` 밖에 분리해 보고하고 system 입력으로 되돌리지 않는다.

| ID | 구성 | 분리하는 효과 |
| --- | --- | --- |
| B0 | 수작업 reviewer | 현행 workflow |
| B1 | 정적 규칙 | deterministic baseline |
| B2 | 단일 LLM + full scoped input | 단순 LLM |
| B3 | 단일 LLM + BM25/vector | flat retrieval |
| P0 | Code Graph + 단일 LLM | graph |
| P1 | Graph + fixed-five DAG + evidence gate, runtime 없음 | 관점·gate |
| P2 | P1 + focused test | test feedback |
| P3 | P2 + always profiler | profiler ceiling |
| **P4-F5** | **P2 + deterministic selective profiler + fixed-five** | **안전 기준선; 기존 P4** |
| P4-S1 | P4-F5 + DiagnosisPlan v2 shadow, 실제 5관점 실행 | plan 계약·누락 추정 |
| P4-S2 | deterministic mandatory + 승격된 Planner 선택 관점 | 적응형 routing |
| P4-CR | 동일 plan arm + 조건부 evidence-cited critic | critic 고유 효과 |
| P4-PR | 동일 plan arm + 제한적 ephemeral probe | 가설 판별 실행 효과 |
| P4-NG | P4-F5에서 evidence gate 제거 | gate 효과 |
| C1 | P4-F5와 같은 router/gate/tools/budget, 5관점 sequential fixed chain | DAG 병렬 효과 |
| C2 | 같은 graph/model/gate/budget, eligible test/profile을 모두 수행하는 mandatory chain | 조건부 도구 상한 |
| O | paired utility를 아는 oracle | 이론적 상한, 운영 금지 |

P3와 P4는 gate가 동일하다. Selective policy 평가는 gate 이전 invocation decision과 gate 이후 finding quality를 분리한다.

### Run budget

Pilot에서 동일 품질을 낼 수 있는 공통 `B_run`을 정하고 final 전에 동결한다.

- P4-F5 초기 allocation 후보: planner 10%, 관점 합계 50%, merger/gate 20%, composer 20%
- P4-S2는 절감한 관점 budget을 실행 관점·gate에만 재배분
- Critic·probe 호출과 자동 실행 검증은 해당 operational arm의 `B_run`·tool-second에 포함
- Evaluator shadow·gold·사람 oracle 판정은 별도 평가 비용으로 공개
- B2/B3도 같은 total token과 tool seconds 상한
- 초과 trial은 `non_comparable`; 결과를 우월성 집계에 섞지 않음
- unconstrained operating point는 별도 Pareto 점으로만 보고

## 3. 데이터셋

### 3.1 Pilot 60건

- 결함 40건: 5개 공통 관점의 주 결함을 균형화하되 필요한 관점은 multi-label로 판정
- 음성·경계 20건: 정상, profiler neutral/harmful, workload 없음, unsafe
- 최소 4개 Python 저장소
- async/concurrency ≥25%, single/cross-file 각각 ≥30%
- fixed-five 출력과 독립적으로 finding·필요 관점·HypothesisContract gold를 evaluator가 고정
- 외부 사례는 license와 commit 고정

Pilot 목적은 label quality, base rate, variance, correlation, 비용 분포 확인이다. 최종 A+ 표본으로 간주하지 않는다.

### 3.2 개발 split과 최종 holdout

| split | 용도 |
| --- | --- |
| train | 오류 taxonomy·learned router 후보 |
| calibration | retrieval/router threshold와 B_run 고정 |
| regression | version promotion 반복 평가 |
| final-temporal | 사전 cutoff 이후 issue/commit의 frozen version 1회 평가 |
| final-OOD | 개발에 없는 repository family의 frozen version 1회 평가 |

- Repository family는 공통 upstream/조직·framework 계보가 없는 단위로 정의하고 development family와 완전 분리한다.
- Temporal cutoff, issue 공개 시각, source commit 가용 조건을 pilot 종료 시 immutable manifest로 고정한다.
- 두 final cohort는 별도 power와 primary endpoint를 갖고 최소 분모를 각각 충족해야 한다.
- Final manifest/label은 tuning 담당자와 agent가 접근할 수 없다.
- Temporal/OOD를 별도 보고한 뒤에만 보조 pooled 결과를 낸다.
- Final을 다시 실행하면 그 결과는 regression evidence로 강등한다.

Final artifact contract:

```yaml
final_temporal_manifest:
  manifest_id: UUID
  version: v1
  manifest_sha256: sha256
  label_sha256: sha256
  cutoff_and_eligibility_rules_sha256: sha256
  access_policy_sha256: sha256
  one_run_record_id: null
final_ood_manifest:
  manifest_id: UUID
  version: v1
  manifest_sha256: sha256
  label_sha256: sha256
  family_and_eligibility_rules_sha256: sha256
  access_policy_sha256: sha256
  one_run_record_id: null
```

Final 보고서와 pooled 분석은 두 manifest ID/hash와 각각의 one-run record를 모두 참조한다.

### 3.3 Power와 strata

Pilot 뒤 claim별 power analysis로 final 수를 정한다. 다음 분모에 사전 최소 건수를 둔다.

- Critical/High
- performance beneficial/neutral/harmful
- concurrency
- negative/unsafe
- repository family
- temporal/OOD

분모가 부족하면 해당 A+ claim을 하지 않는다. Trial 반복은 독립 사례로 부풀리지 않는다.

### 3.4 Ground truth

- 실제 issue/commit, 주입 결함, 성능 회귀를 혼합
- root-cause taxonomy와 Severity rubric v1 사용
- 전문가 2명 blind 판정 + tie-breaker
- Finding마다 필요한 perspective multi-label, claim quantifier, independent oracle 가능 여부를 고정
- fixed-five shadow 출력은 gold가 아니라 evaluator candidate로만 사용
- open-ended 개선은 capability 탐색군으로 분리
- `profiler_gold`는 safe/workload/utility/should_profile을 별도 필드로 고정

## 4. 실행 절차

1. 사례마다 고정 container/virtual environment 초기화
2. source/model/prompt/policy/tool/version과 B_run 동결
3. variant·case 순서 무작위화
4. gold·hidden test·평가 artifact 접근 차단
5. profiler fixture 평가와 실제 end-to-end 평가 분리
6. reviewer는 variant를 가린 채 Finding 매칭
7. trace, token, tool call, timeout, RuntimeEvidence hash 보존
8. DiagnosisPlan disposition, mandatory route, fallback, HypothesisContract, critic/probe trace 보존
9. regression으로 version 선택
10. frozen version을 final temporal/OOD에 한 번 실행

HackDetect 방식으로 trace가 hidden artifact, public solution, scorer 경로를 이용했는지 별도 감사한다.

## 5. 검색 실험

### 비교

- exact/BM25
- vector-only
- 1-hop graph
- typed conditional 2-hop
- tiered hybrid pruning

### 지표

- file/function Accuracy@1/5/10
- evidence Recall@5/10/20
- graph path completeness
- gold evidence/1k tokens
- index/retrieval latency
- expansion 요청당 추가 true evidence와 tokens

[LARGER v1](https://arxiv.org/html/2605.16352v1)와 [Codebase-Memory v1](https://arxiv.org/abs/2603.27277v1)은 최근 graph retrieval 가능성을 보여주지만 본 과제의 최적 hop·node·token 값을 정하지 않는다.

## 6. Profiler router 실험

### 정책

- never
- always
- LLM self-decision
- deterministic rule
- logistic/GBDT
- calibrated model
- oracle

### Paired utility label

같은 case·context·model·B_run에서 no-profile과 profile 결과를 생성한다. 두 결과의 순서를 가린 뒤 전문가 2명과 tie-breaker가 판정한다.

- `beneficial`: true finding, severity, 또는 필요한 조치가 개선
- `neutral`: 정답 변화 없음
- `harmful`: FP/FN/severity 악화

Label은 agent 판단과 별도 version을 갖고 trial별 판정을 case-level로 사전 등록 방식에 따라 집계한다.

### 지표

- invocation Precision/Recall/$F_\beta$/PR-AUC
- beneficial coverage, neutral/harmful run rate
- unsafe-run
- ECE, Brier, reliability
- utility gain vs call budget
- profiler wall p50/p95/timeout
- confirmed true finding당 시간·비용

Threshold, cost matrix, tie-break는 calibration 뒤 동결한다. To Call/UCCI 수치를 profiler 성능으로 전용하지 않는다.

## 7. Ablation

| ID | 제거/변경 | 주 지표 |
| --- | --- | --- |
| A1 | Code Graph 제거 | localization, Recall |
| A2 | exact/BM25 anchor 제거 | anchor Recall |
| A3 | tiered pruning 제거 | tokens, Recall |
| A4 | fixed-five→단일 관점 | 관점 Recall, budget |
| A5 | evidence gate 제거(P4-NG) | grounding, Precision |
| A6 | focused test 제거 | confirmation |
| A7 | profiler 제거 | performance Recall |
| A8 | selective→always(P3) | utility/cost |
| A9 | runtime feedback 반영 제거 | confirmation 반영 |
| A10 | bounded DAG→same-router fixed chain(C1) | latency, calls, 누락 |
| A11 | conditional tools→mandatory chain(C2) | calls, cost, Recall |
| A12 | P4-F5↔P4-S1↔P4-S2 | plan overhead, omission Recall, token/calls |
| A13 | gate/self-review↔P4-CR | incremental counterevidence, false retraction |
| A14 | HypothesisContract 제거 | 상태 위반, contradiction laundering |
| A15 | existing-test-only↔P4-PR | confirmation coverage, differential/hermetic validity |

P3↔P4-F5는 gate-on 상태의 profiler router 차이, P4-F5↔P4-NG는 fixed-five selective-profiler 상태의 gate 차이만 추정한다. 완전한 `router × gate` 상호작용은 no-gate always variant가 없으므로 주장하지 않는다.

## 8. 성능 개선 검증

Profiler 시간이 아니라 별도 benchmark로 개선을 판정한다.

- correctness/hidden tests 선행
- warm-up 3회와 최소 20회는 [SWE-Perf v2](https://arxiv.org/html/2507.12415v2)의 최근 절차를 시작점으로 사용
- 실제 반복 수·outlier·검정은 pilot에서 동결
- median speedup과 CI
- 환경(CPU, Python, dependency, OS) 기록
- shortcut/exploit 여부 trajectory audit

[PERFOPT-Bench v1 HTML](https://arxiv.org/html/2607.07744v1)은 self-contained C benchmark의 방법론적 비유로만 사용한다. Raw speedup만으로 성공을 판단하면 안 된다는 절차는 참고하되 Python/profiler 직접 근거가 아니다. [ArXiv API](https://arxiv.org/abs/2607.07744v1)와 HTML의 task 수가 충돌하므로 수를 인용하지 않는다.

## 9. 최신 외부 근거

| 출처 | 현재 조건·사실 | 적용 범위 |
| --- | --- | --- |
| LARGER v1, 2026-05-08 | MuLocBench fixed Acc@5/Recall@5 55.7/68.6, Codex 50.0/65.1 | graph retrieval 가능성 |
| Codebase-Memory v1, 2026-03-28 | 31 repos, quality .83 vs .92, 약 10× fewer tokens | 구조 검색 trade-off |
| To Call v3, 2026-08-06 | 6 open+1 proprietary, 2 tools, 6 tasks | 필요성/효용/비용 틀 |
| UCCI v1, 2026-05-11 | 75K NER, held-out calibration, cost/F1 제약 | calibration analog |
| SWE-Perf v2, 2026-07-01 revision | 140 real-repo performance instances | 반복 성능 평가 |
| PERFOPT v1, 2026-07-08 | self-contained C benchmark; task count disputed | Python 직접 근거가 아닌 shortcut 방지 방법론 |
| REAP v4, 2026-07-28 revision | production-derived executable eval | task/test 안정성 |
| HackDetect v1, 2026-07-24 | 2,385 traces, protocol exposure audit | benchmark validity |

모든 외부 수치는 FACT이며 PROJECT RESULT가 아니다. Preprint 결과는 독립 재현 전 일반화하지 않는다.

## 10. 우월성 판정

P4-F5는 등록 후보 안에서 다음을 모두 만족할 때만 Pareto 우월로 보고한다.

1. 같은 B_run에서 B2/B3보다 Critical/High Recall +5%p, paired CI가 0 초과
2. 무근거 finding ≤5%, 확인 상태 위반 0
3. token 절감 구성의 Recall one-sided CI 하한 > -2%p
4. P3 대비 profiler time 30% 절감, performance Recall 하한 > -2%p
5. B0 대비 reviewer decision time 50% 절감, 중요 Recall 비열등
6. final temporal/OOD에서 방향 유지

P4-S2·P4-CR·P4-PR은 이 gate를 상속하면서 [`07-ai-technology-advancement-research.md`](07-ai-technology-advancement-research.md) §7과 [`09-ai-advancement-review-artifacts.json`](09-ai-advancement-review-artifacts.json)의 canonical preregistration을 각각 통과해야 한다. 하나라도 실패하면 해당 arm을 승격하지 않고 P4-F5 또는 직전 통과 arm을 유지한다.

Power, alpha, multiplicity, trial aggregation을 final 전에 사전 등록한다. 하나라도 미달이면 해당 범위의 superiority만 주장한다.

## 11. Feedback와 promotion

### FeedbackEvent v2

```yaml
feedback_id: UUID
producing_run_id: UUID
trial: 1
finding_id: F-0001
finding_fingerprint: sha256
gated_finding_uri: evidence://findings/F-0001.json
gated_finding_sha256: sha256
runtime_evidence_id: E-PROFILE-0001
execution_policy_id: UUID
execution_policy_hash: sha256
evidence_uri: evidence://...
evidence_sha256: sha256
source_commit: sha
dataset_version: v1
graph_schema_version: v1
policy_version: v1
prompt_version: v1
model_version: exact
label_taxonomy_version: v1
labeler_role: expert
adjudication_id: UUID
reason_code: false_positive
```

변경 제안은 exact feedback IDs, code/config diff, frozen regression artifact를 참조한다. Promotion validator는 gated finding이 `producing_run_id`에 속하고 source/policy ID·hash/evidence hash가 RuntimeEvidence와 정확히 일치하는지 검사한다. Train/calibration/regression만 promotion에 사용하고 final holdout은 사용하지 않는다.

Promotion gate:

- 대상 오류 cluster 개선
- 새 Critical/High regression 0
- 전체 Recall 하락 ≤2%p
- grounding ≤5%, 안전 위반 0
- cost p95 악화 없음
- shadow 후 rollback 가능

## 12. 오류 분류와 보존

오류: retrieval, graph resolution, pruning, plan invalid/OOD, wrong perspective route, omission, reasoning, hypothesis/oracle mismatch, unsupported claim, wrong severity, critic false retraction, invalid probe/workload, under/overtrigger, instability, merge loss, report omission, protocol exposure.

보존:

- case/gold manifest
- variant config와 B_run hash
- full trace/tool calls
- graph/context manifest
- RuntimeEvidence raw/normalized hash
- blind adjudication
- 통계 script/version/result
- failure/timeout/abstention/non-comparable

## 13. 현재 상태

모든 비교값은 미측정이다. P4-F5는 안전 기준선이고 적응형·critic·probe arm은 승격 전 pilot 후보다. 이 문서는 실험 계약이며 외부 숫자를 결과처럼 채우지 않는다.

