# 기준선·Ablation 벤치마크 계획

- 상태: 무인 평가 설계안, 프로젝트 최종 결과 미측정. 기존 수작업 비교 계획은 현재 동결 평가 계약의 최종 성공 주장에 포함하지 않는다.
- 목적: 강한 모델의 단일 진단보다 작은 모델 전체 시스템이 더 많은 결함을 찾는지, 양쪽이 각각 놓친 결함은 무엇인지, 그때 실제 API 비용이 얼마인지를 먼저 검증한다. [현행 v30 계약](../../.wayfinder/ai-a-plus-code-health/field-input-manifest.yaml)의 강한 후보는 `gpt-6-sol`, 작은 후보는 `gpt-6-luna`다. 기존 80개 봉인 사례·같은 작은 모델 6군은 구성의 독립 기여를 별도로 확인한다. 복수 결함 집계기는 시험용 입력에서만 확인했다. 두 모델의 실제 **공개 개발 사례** 진단은 수행했지만 독립 최종 비교 결과는 없다([Starlette 새 프롬프트 실측](04-public-as-is-to-be-comparison.md#수정된-프롬프트-소유자-승인-후-네-건-실제-진단)).

`openai-oauth@2.0.0`의 ChatGPT 구독 경로는 모델 토큰을 반환하지만 호출별 실제 USD 청구 영수증은 없다. 이전 `page` 개발 사례의 강한 호출은 실패했고 작은 다관점 호출은 알려진 변이를 찾지 못했다([이전 호출](03-ai-pipeline-technical-design.md)). 새 Starlette 개발 사례는 같은 공개 결함의 임시 접수와 후보 위치·완료율 차이를 보여 주지만 독립 숨김 정답·전체 실행 피드백·청구 근거를 갖춘 최종 `S_strong_single` 대 `F_runtime_feedback`은 아니다. v27의 실제 비용 비교는 제공자 원본 청구 근거 전까지 차단된다.

v27의 `--boundary-review`는 기존 다섯 관점에 가정·경계조건 역할을 더하는 **개발 전용** 경로다. 최종 여섯 군 A~F의 수나 두 shadow 실험은 변경하지 않는다. 추가 역할의 효과는 같은 작은 모델에서 기본 다섯 관점·다섯 관점+일반 재검토·다섯 관점+가정 검토를 동일 총 예산으로 별도 비교한다. 시험 응답으로 여섯 역할의 승인·실패·리포트 경로를 확인한 것은 진단 품질 개선이나 이 비교의 완료 증거가 아니다.

정답 후보는 진단과 분리된 평가 절차가 만든다. 합성 결함은 결함판 실패·수정판 통과의 실행 검사로 걸러 봉인하고, 공개 사례는 시점·저장소 계보를 분리해 알려진 회귀 테스트로 확인한다. 같은 결함의 외형만 바꾼 중복은 독립 사례로 세지 않는다. 생성 모델의 주장이나 다른 LLM의 동의는 정답이 아니다. 정답·허용 우선순위·접근권한·해시를 군 실행 전에 동결하고, 진단 모델은 어느 사례의 정답에도 접근할 수 없게 한다.

근거·원인·다음 행동의 의미 일치는 다른 모델 계열과 고정 버전의 블라인드 LLM 판정으로 보조한다. 군 이름은 가리고 후보 순서는 섞으며, 유효/무효 사례로 판정을 사전 검정한다. 실행 검사·회귀 테스트·숨긴 변이 명세가 LLM보다 우선한다. 판정 실패는 해당 사례의 1차 지표 실패로 계수한다. 같은 계열의 하위 에이전트를 여러 명 호출해도 모델 독립성, 외부 독립 심사, 사람 성과가 입증되지는 않는다.

80개 적격 사례·서로 다른 판정 모델·안전한 격리 실행·강한 모델 대 작은 모델 비교와 같은 작은 모델의 실제 6군 결과 중 하나라도 없으면 최종 우월성은 미측정이다. 원 기획서의 사람 진단 시간·재작업·리뷰 생산성은 별도 실측 없이는 이 기계 지표로 대체 주장하지 않는다.

## 1. 연구 질문

| ID | 질문 | 주 지표 |
| --- | --- | --- |
| RQ0 | 작은 모델 전체 시스템이 강한 모델의 단일 진단보다 더 많은 봉인 결함을 찾고, 서로 다른 유형의 누락을 보완하는가? 그때의 실제 API 비용은 얼마인가? | 결함 단위 Recall 차이·가족 단위 CI, 독점 TP·FN, 전체 금액·TP당 금액 |
| RQ1 | Code Graph가 lexical/vector보다 cross-file evidence를 잘 찾는가? | localization/evidence Recall@K, tokens |
| RQ2 | bounded DAG가 같은 예산의 loop/fixed chain보다 좋은가? | 중요 Recall, 누락, latency, calls |
| RQ3 | runtime feedback가 환각을 줄이는가? | confirmation/rejection, grounding |
| RQ4 | 선택 profiler가 always의 품질을 유지하며 비용을 줄이는가? | gold trigger P/R, utility/cost |
| RQ5 | 같은 작은 모델의 전체 시스템이 단순 LLM보다 같은 20분·자원 예산에서 검증 가능한 권고를 더 자주 제시하는가? | 80개 짝비교 유효 권고율 차이와 CI |
| RQ6 | 적응형 Planner가 fixed-five의 Recall을 유지하며 관점 비용을 줄이는가? | perspective omission, 중요 누락, tokens/calls |
| RQ7 | 가설 계약·critic·probe가 기존 Evidence Gate보다 유효한 추가 증거를 만드는가? | counterevidence, probe validity, false retraction |

## 2. 비교 구성

### 공정성 계약

같은 작은 모델의 A~F 여섯 군에는 동일한 commit, task, model version, 허용 도구, evidence snapshot과 전체 `B_run`을 적용한다. `B_run`에는 input/output/cached tokens, planner, 실행 관점, retry, critic, gate, composer가 포함된다. Evaluator-only fixed-five shadow·gold adjudication 비용은 운영 `B_run` 밖에 분리해 보고하고 system 입력으로 되돌리지 않는다. 추가 강한 모델 1회 진단은 같은 사례·스냅샷·범위·결과 형식·20분·총 토큰 상한을 쓰지만 **같은 모델 버전 조건을 적용하지 않는다**. 도구·검색의 차이는 전체 시스템 효과이며 모델 자체 효과로 주장하지 않는다.

| ID | 구성 | 분리하는 효과 |
| --- | --- | --- |
| S | 강한 모델 1회 + 전체 지정 소스 범위, 구조 검색·실행 없음 | 작은 모델 전체 시스템 대비 결함 발견률·고유 누락·실제 호출 금액 |
| B0 | 수작업 reviewer (원 기획서 비교안; 무인 최종 평가 제외) | 사람 수행을 요구하므로 최종 군에 포함하지 않음 |
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
- 평가 전용 정답 생성·재현 검사·블라인드 LLM 판정 비용은 운영 `B_run` 밖에 분리해 공개한다. 사람 판정 비용이나 성과는 주장하지 않는다.
- 강한 모델 1회와 작은 모델 전체 시스템은 같은 총 토큰·20분 상한에서 비교하고, 계획·관점·병합·실패·재시도·캐시를 포함한 실제 청구 금액과 TP당 금액을 함께 보고
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
- 결함/수정판의 차등 실행 검사와 알려진 회귀 테스트를 우선 봉인하고, 의미 매칭은 별도 모델 계열의 블라인드 LLM이 보조한다. 실행 증거 없이 합의만으로 정답을 확정하지 않는다.
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
6. 독립 실행 정답과 별도 모델 계열의 블라인드 판정으로 Finding을 매칭; 판정 모델은 정답을 덮어쓰지 않음
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

같은 case·context·model·B_run에서 no-profile과 profile 결과를 생성한다. 두 결과의 순서를 가리고 봉인된 실행 정답·발견 근거와 대조한다. 근거·조치의 의미 일치에만 별도 모델 계열의 블라인드 판정을 사용한다. 독립적인 차등 검증이나 유효한 판정이 없으면 해당 사례의 효용을 확정하지 않고 분모 부족을 보고한다.

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
5. 동결 v22의 80개 paired case에서 단순 LLM 대비 20분 내 유효 권고율 ≥ +30%p, family bootstrap 95% CI 하한 > 0, Critical/High 부당 기각 0건
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

