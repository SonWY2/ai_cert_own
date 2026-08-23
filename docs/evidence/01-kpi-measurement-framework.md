# 6대 KPI 정의 및 측정 체계

- 상태: 2026-08-23 감사 반영, 구현 실측 전
- 원칙: `FACT`, `DESIGN INFERENCE`, `TARGET`, `PROJECT RESULT`를 분리한다.

## 1. 평가 단위와 정답

### 사례 manifest

```yaml
case_id: PERF-001
dataset_version: v1
repository_commit: sha
scope: []
task_description: 동일한 사용자 설명
workload_or_test: 명령 manifest 또는 실행 불가 사유
ground_truth_findings: []
necessary_perspective_gold:
  - gold_finding_id: G-001
    perspective_ids: [correctness, concurrency]
hypothesis_gold:
  - gold_finding_id: G-001
    claim_quantifier: existential
    root_cause_category: race_on_shared_state
    independent_oracle_id: E-ORACLE-01
runtime_gold:
  - gold_finding_id: G-001
    severity: high
    runtime_eligibility: eligible | not_eligible
    verification_kind: test | profiler
    eligibility_reason: safe_reproducible_profile
profiler_gold:
  safe_to_run: true
  workload_available: true
  counterfactual_utility: beneficial | neutral | harmful
  should_profile: true
  utility_adjudication_id: UUID
  utility_label_version: utility-v1
  frozen_diagnostic_hashes:
    model: sha256
    prompt: sha256
    context_manifest: sha256
    run_budget: sha256
    paired_outputs: sha256
allowed_tools: [static, test, cprofile, py-spy, scalene]
```

`should_profile=true`가 profiler router의 유일한 positive gold class다. `safe_to_run=false` 또는 `workload_available=false`는 별도 exclusion stratum이며 positive class에 넣지 않는다. System candidate를 gold 분모로 사용하지 않는다. Frozen diagnostic hash가 하나라도 바뀌면 utility label을 재판정하거나 이전 version과 비교를 금지한다.

### Finding 정답

Python 전문가 2명이 variant를 모른 채 독립 판정하고 제3자가 중재한다. TP는 다음을 모두 만족한다.

1. 같은 versioned root-cause category
2. 영향 심볼 또는 실행 경로 일치
3. 원인을 검증·완화하는 조치 방향

Severity는 ADR-01 rubric version과 판정 이유를 저장한다. Cohen's $\kappa < 0.70$이면 지침을 수정하고 재라벨링한다.

## 2. 표본과 split

### Pilot

초기 60건은 측정 도구·라벨·효과 분포를 확인하는 pilot이다.

- 결함 40건: 5개 공통 관점을 주 결함 기준으로 균형화하되 필요한 관점은 multi-label로 판정
- 음성·경계 20건: 정상, profiler neutral/harmful, workload 없음, unsafe
- 최소 4개 Python 저장소
- async/concurrency ≥ 25%, single/cross-file 각각 ≥ 30%
- fixed-five shadow 출력은 gold로 사용하지 않고 evaluator가 finding·필요 관점·가설 계약을 독립 판정

60건 자체가 최종 A+ 통계 근거는 아니다.

### Final evaluation

Pilot에서 분산, base rate, intra-repository correlation을 얻고 아래 claim별 power analysis로 held-out 수를 정한다.

- Critical/High Recall
- profiler beneficial Recall/Precision
- 적응형 관점 선택의 perspective omission Recall과 `-2%p` 비열등
- critic의 incremental valid counterevidence yield
- ephemeral probe의 differential/hermetic validity와 confirmation coverage
- reviewer time reduction

각 분모에 사전 최소 건수를 정하고 0건 stratum이 있으면 그 claim을 보고하지 않는다. repository-disjoint train/calibration/regression을 개발에 사용하고, label과 manifest 접근이 차단된 temporal/OOD final holdout을 frozen version에 한 번만 실행한다.

비결정적 agent trial 횟수도 pilot 뒤 고정한다. 초기값 3회는 TARGET이지 외부 검증 수치가 아니다.

## 3. KPI 요약

| KPI | 1차 측정값 | 사전 목표 | 방어 지표 |
| --- | --- | --- | --- |
| 진단 소요 시간 | 전체 reviewer decision time | ≥ 50% 단축 | machine p95, timeout |
| 리스크 식별률 | Recall, Critical/High Recall | 전체 ≥ 0.85, 중요 ≥ 0.90 | Precision ≥ 0.75 |
| 실행 검증 연계율 | runtime confirmation rate | ≥ 0.70 | evidence attachment/rejection/failure |
| Profiler 활용률 | gold beneficial coverage | ≥ 0.80 | router R≥0.85, P≥0.80, unsafe 0 |
| 재작업 감소율 | 같은 원인 cycle 감소 | ≥ 30% | reopen rate |
| 리뷰 생산성 | reviewer time 또는 accepted TP/hour | 40% 단축 또는 50% 증가 | 수용률, FN |

## 4. KPI 1: 진단 소요 시간

### 두 시간축

```text
Machine latency: scope 확정 → gated report 생성
Reviewer decision time: scope 수신 → 증거 열람·승인/기각을 마친 최종 보고서
```

제안서의 생산성 비교는 reviewer decision time을 사용한다. 사용자 승인 대기와 evidence inspection을 제외하지 않는다. machine latency는 별도 운영 지표다.

$$
Reduction_{time}=1-\frac{median(T_{assisted,reviewer})}{median(T_{manual,reviewer})}
$$

### Human study

- reviewer×case 무작위·counterbalanced 배정
- manual/assisted의 허용 도구와 정보 고정
- 같은 reviewer가 같은 case를 두 번 보지 않음
- 숙련도, 순서, repository 효과 기록
- reviewer와 repository를 paired/random effect로 분석
- timeout·중단은 삭제하지 않음

## 5. KPI 2: 리스크 식별률

$$
Recall=\frac{TP}{TP+FN},\quad Precision=\frac{TP}{TP+FP},\quad F1=\frac{2PR}{P+R}
$$

Critical/High를 별도 보고한다. Severity 가중치는 보조값이다.

$$
WeightedRecall=\frac{\sum_i w_iTP_i}{\sum_iw_i(TP_i+FN_i)},\quad
w=\{critical:4,high:3,medium:2,low:1\}
$$

`abstained`에 정답 결함이 있으면 Recall에서는 FN이다. 안전한 abstention rate는 별도 보고한다. 반복 trial은 per-trial 성공률, pass@1, 모든 trial 일관성을 분리한다.

## 6. KPI 3: 실행 검증 연계율

Primary cohort는 evaluator가 final 전에 고정한 `runtime_gold`의 eligible Critical/High finding이다.

$$
RuntimeConfirmationCoverage=
\frac{N_{gold\ cohort\ findings\ matched\ to\ runtime\_confirmed\ TP}}
{N_{gold\ runtime\_eligible\ Critical/High\ findings}}
$$

$$
RuntimeEvidenceAttachmentCoverage=
\frac{N_{gold\ cohort\ findings\ matched\ to\ completed\ runtime\ attempt}}
{N_{gold\ runtime\_eligible\ Critical/High\ findings}}
$$

Primary KPI는 `RuntimeConfirmationCoverage`다. Variant가 출력한 finding 중 eligible finding이 확인으로 전환된 비율은 `OutputConditionedConfirmationConversion`이라는 별도 운영 지표로 보고하며 TP/FP 매칭을 함께 공개한다.

모든 deduplicated emitted High/Critical finding은 routing 전에 `runtime_eligibility=eligible|not_eligible`과 `eligible_test | eligible_profile | no_workload | unsafe | tool_unavailable | policy_forbidden` reason code를 기록한다. Opt-in decline은 eligibility를 바꾸지 않고 lifecycle outcome으로 별도 보고한다.

## 7. KPI 4: Profiler 활용률

정책과 무관하게 final 전에 고정한 `should_profile`을 positive class로 사용한다.

$$
ShouldProfileCoverage=\frac{N_{run\ where\ should\_profile=true}}{N_{should\_profile=true}}
$$

$$
ProfilerRecall=\frac{TP_{run}}{TP_{run}+FN_{skip}},\quad
ProfilerPrecision=\frac{TP_{run}}{TP_{run}+FP_{run}}
$$

$$
UnnecessaryRunRate=\frac{N_{run\ where\ should\_profile=false}}{N_{should\_profile=false,\ safe,\ workload}}
$$

Unsafe와 no-workload는 별도 evaluator-owned stratum으로 보고하며 실행 시 safety failure다.

추가 보고:

- system candidate rate
- exclusion·opt-in decline rate
- total profiler time/p95
- confirmed true finding당 시간·비용
- utility label version과 frozen diagnostic hashes

Counterfactual utility는 같은 model·prompt·context·B_run의 paired outputs를 blind 판정한다. 이 입력 중 하나가 바뀌면 utility label version을 재생성하지 않는 한 정책 비교에 재사용하지 않는다.

## 8. KPI 5: 재작업 감소율

$$
Reduction_{rework}=1-\frac{Rate_{assisted}}{Rate_{manual}}
$$

- PR/case 진입 시 eligible root-cause cohort를 고정한다.
- Repository와 severity strata 안에서 assisted/manual을 무작위 배정하거나 사전 matching한다.
- 공통 follow-up window를 사용한다. PR 조기 종료는 censoring과 time-at-risk로 모델링한다.
- Eligible root cause당 rework/reopen rate와 clustered CI를 보고한다.
- 기능 범위 변경은 사전 reason code로 제외한다.
- 최소 4주 또는 PR 종료까지 추적
- cycle, reopen, 추가 변경 lines를 함께 보고

## 9. KPI 6: 리뷰 생산성

$$
TimeReduction=1-\frac{median(T_{assisted,reviewer})}{median(T_{manual,reviewer})}
$$

$$
AcceptedTPPerHour=\frac{N_{accepted\ true\ findings}}{reviewer\ hours}
$$

속도와 함께 finding 수용률, Critical/High FN, reviewer 간 편차를 보고한다.

## 10. AI 파이프라인 방어 지표

| 지표 | 정의 | 목표 |
| --- | --- | ---: |
| 무근거 발견률 | 유효 evidence 없는 최종 finding / 전체 | ≤ 5% |
| 확인 상태 위반 | 근거 없는 runtime_confirmed | 0 |
| context evidence Recall | gold evidence 중 context 포함 | ≥ 0.90 |
| perspective omission Recall | routed arm이 필요한 gold perspective를 실행·보존 | 비열등 하한 > -2%p |
| route-attributable 중요 누락 | 관점 skip/defer가 원인인 Critical/High FN | 0 |
| analyst 절감 | fixed-five 대비 analyst calls 또는 input/output tokens | ≥ 20% pilot 후보 |
| critic 추가 근거 | gate-only에 없던 blind-valid counterevidence | self-review보다 CI 하한 > 0 |
| probe validity | buggy/fixed/wrong-patch differential·hermetic validity | 각각 ≥ 80% pilot 후보 |
| run-level token | 모든 agent·retry·critic·cache 포함 | variant 공정 비교 |
| Recall 비열등 | token 절감 구성 - 기준선 | 하한 > -2%p |
| 안전 실행 위반 | policy/승인 밖 명령 | 0 |
| protocol exposure | agent가 gold/test artifact 접근 | 0 |

## 11. 통계와 보고

- time/cost: median, IQR, p95, cluster bootstrap CI
- paired binary: McNemar 또는 사전 등록 paired test
- -2%p 비열등: one-sided CI와 alpha 사전 고정
- 여러 비교: Holm 보정
- trial은 독립 case로 부풀리지 않고 case 내 반복으로 모델링
- failure/timeout 삭제 금지
- final holdout은 한 번만 집계

## 12. 실행 기록

```yaml
run_id: UUID
case_id: PERF-001
dataset_version: v1
variant: P4-F5
trial: 1
source_commit: sha
model: exact-version
prompt_version: sha256
policy_version: sha256
graph_hash: sha256
diagnosis_plan_version: diagnosis-plan-v2
perspective_dispositions: {}
hypothesis_contract_ids: []
critic_disposition: null
execution_attempt_policy_ledger:
  - execution_request_id: UUID
    runtime_evidence_id: E-PROFILE-0001
    execution_policy_id: UUID
    execution_policy_hash: sha256
    predecessor_execution_policy_id: UUID
run_budget:
  max_total_tokens: 0
  max_tool_seconds: 0
tokens:
  input: 0
  output: 0
  cached: 0
cost:
  llm: 0.0
  tools: 0.0
latency_ms: {}
findings: []
runtime_evidence_ids: []
outcome: success | partial | failed | timeout | non_comparable
```

`0`은 실제값일 때만 사용한다. 실측 전 표는 `미측정`으로 표시한다.

## 13. 현재 상태

모든 KPI는 TARGET이며 프로젝트 결과가 아니다. 외부 논문 숫자를 본 과제 결과로 전용하지 않는다.

## 14. 최신 근거

- [REAP v4, 2026-07-28 revision](https://arxiv.org/abs/2604.01527v4) — 실행 가능성, test relevance, multi-run stability.
- [SWE-EVO v5, 2026-04-04 revision](https://arxiv.org/abs/2512.18470v5) — 장기 multi-file task와 partial progress.
- [HackDetect v1, 2026-07-24](https://arxiv.org/abs/2607.22368v1) — benchmark protocol exposure와 score inflation.
- [`../project-context/ai-professional-project-proposal.md`](../project-context/ai-professional-project-proposal.md) — 6대 KPI, 시간 50%, 재작업 30% 목표.

REAP의 multi-run 검증과 본 과제 agent trial은 다른 절차다. Pilot 60건·3 trial·최종 표본 수는 프로젝트 설계이며 power analysis로 확정한다.

