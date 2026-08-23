# AI 기술 고도화 심층 조사

- 조사일: 2026-08-23
- 상태: 권고를 기획서·ADR·기술 설계·평가 계약에 반영 — 구현·프로젝트 성과 미측정
- 범위: Diagnosis Planner, 다관점 추론, Code Graph retrieval, 실행 검증, Evidence Gate, feedback
- 원칙: AI 요소 수가 아니라 **진단 품질의 독립 기여, 같은 `B_run`의 효율, 반증 가능성**으로 채택 여부를 판단한다.
- 근거 원장: [`08-ai-advancement-evidence-ledger.json`](08-ai-advancement-evidence-ledger.json)
- 검토 산출물: [`09-ai-advancement-review-artifacts.json`](09-ai-advancement-review-artifacts.json)

## 1. 결론

현재의 **정적 분석 + Code Graph + LLM 관점 추론 + 실행 증거** 구조는 유지한다. 지금 필요한 것은 agent 수를 늘리는 것이 아니라 다음 세 가지를 순서대로 고도화하는 것이다.

1. **가설 중심 진단 계약을 먼저 추가한다.**
   - Finding을 자유 서술이 아니라 반증 가능한 `HypothesisContract`에 연결한다.
   - 어떤 실행 결과가 주장을 지지하거나 반박하는지, oracle은 무엇인지 실행 전에 고정한다.
2. **Diagnosis Planner를 shadow 방식의 적응형 scheduler로 시험한다.**
   - 기존 5관점은 taxonomy와 fallback으로 유지한다.
   - 곧바로 관점을 생략하지 않고, 먼저 `run | skip | defer | shadow` 제안과 근거만 기록한다.
   - frozen evaluator-owned defect·필요 관점 label과 blind adjudication으로 omission 위험을 측정한 뒤에만 실제 routing으로 승격한다. Fixed-five shadow 출력은 gold가 아니라 비교 후보다.
3. **근거가 있는 반증과 실행 probe를 선택적으로 붙인다.**
   - High/Critical 또는 관점 간 충돌에만 근거 인용형 critic을 한 번 실행한다.
   - 기존 테스트가 없는 명확한 가설에만 일회성 counterexample probe 생성을 별도 pilot으로 둔다.

자유형 specialist 생성, 반복 debate, persistent agent memory, cold-start learned router는 도입하지 않는다.

## 2. 조사 당시 확인된 AI gap

| 영역 | 조사 당시 상태 | 당시 gap |
| --- | --- | --- |
| Diagnosis Planner | versioned plan을 만든다고 정의 | plan schema, 관점 선택·생략·중단 계약이 없음 |
| 다관점 분석 | 5관점 모두 first pass | 사례별 관점의 한계효용을 사용하지 않음 |
| 추가 관점 | 고정 5개 | framework/domain-specific focus를 표현할 방법이 없음 |
| Focused test | 승인된 기존 명령만 실행 | 가설에 맞는 최소 반례·재현 입력을 설계하지 않음 |
| RuntimeEvidence | provenance와 상태 전이가 강함 | 실행 전 예상 관찰·oracle이 Finding에 고정되지 않음 |
| Evidence Gate | 구조·근거·반례를 검사 | semantic critic의 고유 이득과 기존 gate 중복 여부가 미측정 |
| Feedback | event·regression·promotion 계약 존재 | 반복 실패가 어느 subsystem에서 발생했는지 offline 진단하지 않음 |
| Retrieval | lexical/BM25 + bounded graph | partial trajectory에 따른 granularity·relation 선택은 미검증 |

아래 gap은 후속 문서 반영에서 `DiagnosisPlan v2`, Plan Gate, focus lens, `HypothesisContract v1`, fixed-five/shadow/routed 평가 계약으로 구체화했다. 구현과 성능은 여전히 미측정이다.

## 3. 권고 구조: Hypothesis-driven Adaptive Diagnosis

```text
Deterministic signals
  AST / symbol / CFG / graph / diff / existing tests
          |
          v
Diagnosis Planner v2 (shadow first)
  - perspective dispositions
  - registered focus lens
  - evidence IDs / budget / stop conditions
          |
          v
Selected analyst set + fixed-five shadow evaluator
          |
          v
Canonical Finding + HypothesisContract
          |
          +---- conflict/high-risk ----> one evidence-cited challenge
          |
          +---- testable evidence gap -> optional ephemeral probe
          |
          v
RuntimeEvidence -> deterministic state transition -> Evidence Gate
          |
          v
Offline failure localization -> frozen regression -> human promotion
```

AI는 다음을 담당한다.

- 어떤 위험 가설을 먼저 조사할지 제안
- 등록된 관점과 focus lens를 선택
- 반례와 더 단순한 설명을 제안
- 독립 oracle이 있는 경우 최소 counterexample probe 후보를 생성
- 반복 실패를 subsystem 단위로 분류

코드는 다음을 계속 담당한다.

- graph 사실, source hash, reachability, policy, budget, stop, state transition
- 관점 admission과 fallback
- 실행 권한과 sandbox
- runtime evidence 정규화
- 최종 확인 상태 승격

## 4. Diagnosis Planner v2

### 4.1 5관점의 역할 변경

기존 5관점을 삭제하지 않는다. **항상 실행되는 5개 agent**에서 **공통 taxonomy와 등록 specialist 집합**으로 역할을 바꾼다.

| 관점 | 초기 정책 | 비고 |
| --- | --- | --- |
| 정확성 | 보호 관점 후보 | pilot에서 항상 실행하는 안을 먼저 평가 |
| 구조 | 보호 관점 후보 | 정적 graph가 있어도 책임·경계 해석은 LLM 가치가 있음 |
| 성능 | 조건부 후보 | 반복·복잡도·I/O·회귀 신호가 있을 때 |
| 동시성 | 조건부 후보 | async, lock, task, shared state 신호가 있을 때 |
| 테스트 | 조건부 후보 | 중요 경로·변경 영향·기존 test 연결 신호가 있을 때 |

`정확성+구조`를 보호 관점으로 두는 것은 **초기 pilot 가설**이지 외부 연구로 확정된 최적값이 아니다.

### 4.2 추가 관점은 permanent agent가 아니라 focus lens로 둔다

| focus lens | trigger 예시 | parent 관점 |
| --- | --- | --- |
| `change-impact` | public API, shared symbol, 다수 caller, schema 변경 | 구조 + 테스트 |
| `resource-lifecycle` | file/socket/session/task, timeout, retry, cancellation | 정확성 + 동시성 |
| `data-transaction-contract` | ORM, transaction, idempotency, schema validation | 정확성 |
| `security-boundary` | 외부 입력, auth, secret, command/query 생성 | 정확성, 별도 scope 승인 시 |

Planner는 임의 specialist agent를 만들지 않는다. 등록된 lens에서 선택하고, 미등록 관점이 필요하면 다음만 생성한다.

```yaml
supplemental_focus:
  parent_perspective: correctness
  focus_question: "취소 시 열린 resource가 남는가?"
  novelty_reason: resource_lifecycle_gap
  trigger_evidence_ids: [E-GRAPH-21]
  disposition: shadow | offline_taxonomy_review
```

현재 run에서는 parent 관점이 이를 처리한다. 반복적으로 유효성이 확인된 focus만 registry revision을 거쳐 승격한다.

### 4.3 최소 plan 계약

```yaml
diagnosis_plan:
  schema_version: diagnosis-plan-v2
  plan_id: UUID
  source_commit: sha
  graph_hash: sha256
  planner_model_hash: sha256
  budget_version: B-run-v1
  perspectives:
    - perspective_id: concurrency
      disposition: run | skip | defer | shadow
      source: deterministic_mandatory | planner_proposed | fallback
      reason_code: async_shared_state
      trigger_evidence_ids: [E-GRAPH-21]
      focus_lens_ids: [resource-lifecycle]
      allocated_tokens: 0
      stop_condition: evidence_gap_closed
  fallback_reason: null | schema_invalid | ood | unresolved_high_risk | budget_invalid
```

불변 조건:

- LLM은 deterministic mandatory 관점을 제거할 수 없다.
- 모든 5관점에 disposition과 reason을 남긴다.
- schema 실패, OOD, extractor 불완전, unresolved High/Critical은 fixed-five fallback이다.
- pilot에서는 생략 관점도 evaluator-only shadow로 실행하되 출력은 gold로 쓰지 않는다. Frozen evaluator-owned defect·필요 관점 multi-label에 blind adjudication한 결과만 omission gold다.
- final holdout 전 taxonomy, trigger, planner, budget을 동결한다.

## 5. 선행 계약: HypothesisContract v1

현재 focused-test request는 실행 명령은 고정하지만 어떤 결과가 주장을 반박하는지는 고정하지 않는다. A4 probe나 RuntimeEvidence 재해석보다 먼저 다음 계약이 필요하다.

```yaml
hypothesis_contract:
  schema_version: hypothesis-v1
  hypothesis_id: UUID
  finding_id: F-0001
  claim_quantifier: universal | existential | probabilistic | normative
  root_cause_category: sync_io_in_async
  primary_location: symbol-id
  preconditions: []
  action: "동시 요청 N개 실행"
  predicted_observations:
    supports: []
    refutes: []
  oracle:
    kind: user_observation | doc_contract | evaluator_spec | existing_test | benchmark
    evidence_id: E-ORACLE-01
  workload_hash: sha256 | null
  execution_policy_id: UUID
```

규칙:

- universal 주장은 하나의 유효 counterexample로 반박할 수 있다.
- existential·race·확률적 주장은 probe가 재현하지 못했다는 이유로 반박할 수 없다.
- independent oracle이 없으면 실행 결과는 `inconclusive` 또는 사람 검토용 artifact다.
- 실행 후 root cause나 위치를 바꾸면 새 hypothesis ID를 발급한다.
- `completed/refutes` 결과를 LLM이 다른 설명으로 바꿔 기존 finding을 유지할 수 없다.

이 계약은 AI 성능을 직접 높인다는 주장이 아니라 이후 AI probe·critic·re-analysis를 검증 가능하게 만드는 선행 조건이다.

## 6. 후보 판정

3개 독립 관점이 품질 가치 25%, AI 깊이 15%, 근거 20%, 단순성 15%, 측정 가능성 15%, 역위험 10%로 평가했다. 점수·관점별 근거·후보 매핑·A1/A3/A4/A5 반대 검토 원문은 [`09-ai-advancement-review-artifacts.json`](09-ai-advancement-review-artifacts.json)에 보존했다. 점수는 연구 우선순위이며 프로젝트 KPI가 아니다.

| 후보 | 종합점수/5 | 판정 | 이유 |
| --- | ---: | --- | --- |
| 근거 인용형 semantic critic | 4.08 | 조건부 pilot | 측정하기 쉽지만 현행 Evidence Gate 대비 고유 이득이 미측정 |
| RuntimeEvidence 후 1회 재분석 | 4.08 | 보류 | 단순하지만 post-hoc contradiction laundering 위험 |
| 등록형 적응 관점 scheduler | 3.95 | shadow pilot | 중심 AI 고도화이나 관점 omission gold가 없음 |
| 가설 판별용 ephemeral probe | 3.92 | 2단계 pilot | AI 깊이와 잠재 효과가 크지만 oracle·sandbox 비용과 위험이 큼 |
| Semgrep corroboration | 3.80 | 지원 기술 | 유용하지만 새로운 AI 추론 기술은 아님 |
| Adaptive evidence aperture | 3.53 | 보류 | history/retrieval downstream 이득 근거가 혼재 |
| Offline failure localizer | 3.00 | 데이터 축적 후 | frozen feedback 사례가 쌓인 뒤 의미가 있음 |
| Trace/log reasoning | 2.85 | telemetry 존재 시 | 인프라·보존·개인정보 비용이 큼 |
| Learned model/specialist router | 2.82 | 보류 | cold-start label과 안정된 verifier가 없음 |
| 자유형 supplemental specialist | 2.77 | 제외, focus lens로 축소 | schema drift와 중복 관점 위험 |
| 반복 debate/reflection swarm | 2.02 | 제외 | 비용 증가와 false consensus 근거 |
| 자유형 persistent memory | 1.95 | 제외 | stale memory·split leakage·오염 위험 |

반대 검토에서는 상위 A1/A3/A4/A5도 모두 **바로 채택할 외부 전이 근거가 부족**하다고 판정했다. 따라서 본 보고서의 `pilot`은 도입 승인이 아니라 반증 실험 대상으로 선정했다는 뜻이다.

## 7. 도입 순서

### 단계 0 — 현재 baseline 구현

- 현재 P4-F5 DAG, Finding v2, ExecutionPolicy, RuntimeEvidence, Evidence Gate를 먼저 동작시킨다.
- baseline 결과가 없으면 새 AI 기술의 독립 효과를 측정할 수 없다.

### 단계 1 — 계약만 고도화

- `DiagnosisPlan v2`
- `HypothesisContract v1`
- 모든 perspective disposition·evidence·budget ledger
- 동작은 fixed-five 그대로 유지

검증: 기존 P4와 finding 결과가 동일하고 lineage·budget만 추가돼야 한다.

### 단계 2 — shadow adaptive planner

비교:

```text
F5: fixed five
S1: planner 제안만 기록, 실행은 fixed five
S2: deterministic mandatory + planner optional routing
```

평가 단위와 gold:

- 표본 단위는 case이며 repository로 군집화한다.
- Gold는 frozen evaluator-owned defect와 필요한 perspective의 multi-label이다.
- Fixed-five shadow 출력은 evaluator가 확인할 candidate이며 gold가 아니다.
- Shadow 실행 비용은 운영 variant의 `B_run` 밖 evaluator 비용으로 분리하되 token·wall time·tool call을 별도 보고하고 S1/S2 입력으로 되돌리지 않는다.
- F5와 S2의 실제 운영 비교는 planner·analyst·gate·composer를 포함한 동일 `B_run`을 사용한다.

Pilot 사전등록 gate 후보:

- 주 gate: Critical/High Recall 비열등 한계 `-2%p`, one-sided 95% CI, repository-cluster bootstrap 통과
- route-attributable evaluator-confirmed Critical/High miss 0건
- 전체 Recall 비열등 한계 `-2%p`
- 무근거 finding 비율 5% 이하
- fixed-five 대비 analyst call 또는 input/output token 20% 이상 감소

하나라도 실패하면 S2를 승격하지 않고 fixed-five를 유지한다. `-2%p`와 20%는 외부 성능값이 아닌 pilot gate 후보이며 final 전 power analysis와 함께 동결한다.

### 단계 3 — selective critic

비교:

1. 현재 Evidence Gate
2. 같은 token의 merger self-review
3. fresh-context typed critic
4. 가능하면 다른 model family critic

critic은 `DISAGREE_EVIDENCE`, `DISAGREE_CONCERN`, `REQUEST_PROBE`, `NO_NEW_EVIDENCE`만 출력한다. finding 생성, severity 상승, `runtime_confirmed` 승격은 금지한다.

평가 단위는 High/Critical·관점 충돌·미해결 반례 finding batch다. 같은 evidence snapshot과 `B_run`에서 current gate, equal-token merger self-review, same-backbone critic, 가능한 경우 다른 model-family critic을 비교한다.

실행 전에 evaluator가 다음 gold packet을 동결한다.

- case·finding ID와 trigger eligibility
- 원 finding의 true/false, gold root cause와 severity
- evidence snapshot과 허용 counterevidence 종류
- 유효한 신규 counterevidence·severity correction·false retraction 판정 rubric

모든 arm은 gold label을 보지 못한다. Trigger case와 matched non-trigger control을 함께 평가하고, 출력 순서를 가린 evaluator가 잠긴 rubric으로 신규 counterevidence를 판정한다. 독립적으로 잠글 gold가 없는 case는 pilot에서 제외하거나 `inconclusive`로 별도 보고한다.

Pilot gate:

- `incremental_valid_counterevidence`를 해당 critic arm의 유효 counterevidence 중 gate-only arm에 없던 것으로 정의한다. Fresh critic의 이 값과 유효 severity correction이 gate-only·equal-token self-review 모두보다 높고 repository-cluster 95% CI 하한이 0보다 커야 한다.
- Critical/High Recall 비열등 한계 `-2%p`
- 무근거 finding 비율 5% 이하
- critic-created confirmation 0건
- critic-caused false retraction 0건

실패하면 별도 critic을 제거하고 typed disagreement 계약만 기존 Evidence Gate에 남긴다.

### 단계 4 — ephemeral probe pilot

대상:

- 기존 관련 test가 없음
- High/Critical correctness 또는 제한된 concurrency 가설
- 독립 oracle과 claim quantifier가 있음
- 한 파일·한 test·한 sandbox·한 번의 bounded repair

probe는 repository test나 gold로 자동 승격하지 않는다. buggy/fixed/wrong-patch triple을 이용해 fail-on-buggy, pass-on-fixed, wrong-patch rejection을 blind 평가한다.
성능 문제는 대표 workload 계약이 없으면 probe 대상에서 제외한다.

평가 단위와 gold:

- 단위는 evaluator-owned finding별 `buggy/fixed/adversarial-wrong-patch` triple이며 case와 repository로 군집화한다.
- Frozen gold는 root cause, claim quantifier, independent oracle, expected support/refute observation을 가진다.
- Generator는 buggy snapshot과 허용 oracle provenance만 보고 fixed diff·hidden test·label·final holdout에 접근하지 못한다.
- Generator token, sandbox 시작·reset, probe 실행·반복·자동 validity 검사는 같은 operational `B_run`과 tool-second 예산에 포함한다.
- 사람의 gold·oracle 판정은 evaluator 비용으로 분리해 보고하고 generator·critic 입력으로 되돌리지 않는다.

Pilot gate:

- 기존 P4-F5 대비 실행으로 확인 가능한 finding coverage `+5%p` 이상
- accepted finding precision 향상 또는 false-positive 감소가 P4-F5보다 유리하고 repository-cluster 95% CI가 0을 포함하지 않음
- buggy/fixed/wrong-patch differential validity와 hermetic validity 각각 80% 이상
- 채택 probe 반복 실행 안정성 100%
- unsafe 실행·hidden artifact 접근·gold 자동 편입 0건
- Critical/High Recall 저하와 false confirmation/rejection 0건


하나라도 실패하면 A4를 승격하지 않고 기존 test만 사용하는 P4-F5 또는 `abstained`를 유지한다. CI·군집화·다중 비교 방식은 아래 공통 계약을 적용한다.
`+5%p`와 80%는 pilot 사전등록 후보이며 외부 성능값이 아니다. 생성·sandbox reset·반복 실행·검증·사람 oracle 판정 비용을 모두 보고한다.

### 공통 통계와 비용

- 최종 표본 수는 pilot effect와 variance를 이용한 power analysis로 정한다.
- 각 실험은 주 가설 하나를 사전등록한다. 여러 주 가설을 동시에 주장하면 Holm 방식으로 다중 비교를 보정한다.
- 비열등성은 one-sided 95% CI, 그 외 차이는 repository-cluster bootstrap 95% CI로 보고한다.
- evaluator gold·shadow 비용은 시스템 `B_run`과 분리해 보고하지만 숨기지 않는다.
- pass는 해당 pilot의 승격 결정만 바꾼다. 다른 AI 후보의 성과로 전이하지 않는다.


### 단계 5 — offline feedback AI

충분한 evaluator-confirmed 실패가 쌓인 뒤 AI가 다음 원인을 분류한다.

- retrieval miss
- graph unresolved/stale
- wrong perspective route
- analyst reasoning error
- merge/severity error
- tool/router error
- evidence gate error

자동 변경하지 않는다. versioned 변경안 → frozen regression → shadow → 사람 승인 → rollback 가능한 promotion 순서를 유지한다.

## 8. 기획서 변경 권고

`docs/project-context/ai-professional-project-proposal.md`는 구현 전에 다음 방향으로 변경하는 것이 타당하다.

1. “5개 관점을 고정 실행한다”를 “5개 관점을 공통 taxonomy와 baseline으로 유지하고, pilot에서 증거 기반 선택 실행을 검증한다”로 변경한다.
2. “진단 계획 자동 생성”에 perspective disposition, focus lens, evidence-linked stop을 추가한다.
3. “실행 검증 연계”에 falsifiable hypothesis, independent oracle, counterexample probe 후보를 추가한다.
4. 최적화 지표에 perspective omission Recall, critic unique-evidence yield, valid probe yield를 추가한다.
5. 적응형 planner·critic·probe의 성과는 project pilot 전까지 목표나 후보로만 표기한다.

## 9. 제외·보류 근거

- **자유형 관점 생성**: 관점 수보다 계약과 누락 통제가 중요하다. 미등록 요구는 focus question과 offline taxonomy review로 보존한다.
- **반복 debate**: [The Cost of Consensus](https://arxiv.org/html/2605.00914v1)은 제한된 7–8B 조건에서 debate가 self-correction보다 2.1–3.4배 token을 쓰고 같거나 낮은 정확도를 보고했다.
- **LLM confidence routing**: [AgentAbstain](https://arxiv.org/html/2607.10059v1)의 최고 agent도 act/abstain paired accuracy가 59.5%였다. free-form confidence는 routing 상태로 쓰지 않는다.
- **항상 skill 주입**: [SWE-Skills-Bench](https://arxiv.org/html/2603.15401v1)는 49개 중 39개 skill이 pass-rate 개선 0, 평균 +1.2%, 최대 +451% token 증가를 보고했다.
- **장기 free-form memory**: [CommitDistill](https://arxiv.org/html/2605.18284v1)은 retrieval 장점과 별개로 downstream headline 평균의 통계적 개선을 확인하지 못했다.
- **생성 test를 oracle로 사용**: [Beyond Test Presence](https://arxiv.org/html/2607.12068v1)와 [Verification Horizon](https://arxiv.org/html/2606.26300v1)은 test quality·stability·verification 한계를 보여준다.

## 10. 핵심 1차 출처

- [SWE-Router v1, 2026-06-30](https://arxiv.org/html/2607.00053v1) — partial trajectory 기반 coding-agent model routing.
- [AgentAbstain v1, 2026-07-11](https://arxiv.org/html/2607.10059v1) — act/abstain paired calibration 한계.
- [Adversarial Review v1, 2026-08-16](https://arxiv.org/html/2608.18167v1) — naive critic의 false consensus와 구조화된 이견 형식.
- [Improving Dynamic Specification Inference with LLM-Generated Counterexamples v1, 2026-04-12](https://arxiv.org/html/2604.10761v1) — 실행 가능한 counterexample 후보와 검증.
- [The Verification Horizon v1, 2026-06-24](https://arxiv.org/html/2606.26300v1) — coding-agent verifier의 scalability·faithfulness·robustness 한계.
- [To Call or Not to Call v3, 2026-08-06](https://arxiv.org/html/2605.00737v3) — need·utility·affordability와 tool self-decision 한계.
- [Beyond Test Presence v1, 2026-07-13](https://arxiv.org/html/2607.12068v1) — agent-generated test quality와 stability.
- [The Cost of Consensus v1, 2026-04-29](https://arxiv.org/html/2605.00914v1) — unguided homogeneous debate 비용·오류.
- [CommitDistill v1, 2026-05-18](https://arxiv.org/html/2605.18284v1) — repository history memory의 retrieval/downstream 차이.
- [SWE-Skills-Bench v1, 2026-03-16](https://arxiv.org/html/2603.15401v1) — skill injection의 비용 대비 제한된 평균 효과.

## 11. 최종 판정

가장 AI다운 개선은 agent를 더 만드는 것이 아니다. **LLM이 증거를 보고 관점과 검증 행동을 선택하되, 모든 선택을 typed contract·counterfactual shadow·실행 oracle로 검증하는 구조**다.

따라서 현재 기획의 다음 버전은 다음 문장으로 요약할 수 있다.

> 고정 5관점 진단을 baseline과 taxonomy로 유지하고, 반증 가능한 가설을 중심으로 적응형 관점 routing·구조화된 반대 검토·제한적 counterexample probe를 단계적으로 검증한다.
