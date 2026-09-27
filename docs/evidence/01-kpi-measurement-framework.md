# 진단 KPI 정의 및 측정 체계

- 상태: 이미 제출한 제안서의 수정 허용에 따라 무인 성과 목표를 반영한 설계안이며, 수정본의 심사 접수·수용과 프로젝트 최종 실측은 미확인. 이전 사람 진단 시간 50%·재작업 30%·리뷰 생산성은 미측정이고 현재 성과 목표가 아니다.
- 원칙: `FACT`, `DESIGN INFERENCE`, `TARGET`, `PROJECT RESULT`를 분리한다. [현행 v30 평가 계약](../../.wayfinder/ai-a-plus-code-health/field-input-manifest.yaml)의 `gpt-6-luna` 전체 시스템 대 `gpt-6-sol` 단일 진단을 최우선으로, 기존 같은 작은 모델 여섯 군을 기여 검증으로 측정한다. [복수 결함 집계기](../../src/modules/evaluation/USAGE.md)는 시험용 봉인 입력만 확인했다. Starlette 공개 개발 사례의 새 프롬프트 네 호출에는 수정 전 알려진 EOF 임시 접수 가설이 있지만 작은 모델의 위치 오류·관점 실패가 있고 최종 독립 평가나 실제 USD 청구 근거는 없다([개발 실측](04-public-as-is-to-be-comparison.md#수정된-프롬프트-소유자-승인-후-네-건-실제-진단)).

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

최종 정답은 진단 모델의 출력 전에 봉인한다. 결함 사례는 독립된 재현 테스트가 결함 버전에서 실패하고 수정 버전에서 통과해야 한다. 정상·안전 제외 사례도 같은 방식으로 자동 검사한다. 실행으로 입증할 수 없는 원인·영향 경로는 별도 모델 계열의 블라인드 판정 후보로만 남기며, 판정 모델의 일치만으로 정답이나 실행 확인을 확정하지 않는다.

TP 매칭은 버전이 고정된 원인 분류, 영향 심볼·실행 경로, 검증 가능한 조치 방향을 모두 요구한다. 정답 생성·실행 검사·의미 매칭의 모델/코드 버전과 입력 해시를 기록한다. 모호하거나 독립 재현에 실패한 사례는 군별 결과를 보기 전에 사유와 함께 제외한다. 개발 모델이 봉인된 정답·판정 입력에 접근한 사례는 최종 평가에서 제외한다.

**결과보고서 판정 주체 표기:** 별도 판정 모델의 실제 기록이 있는 경우에만 “사람의 평가를 대신해 LLM 판정을 활용했다. LLM은 발견의 원인·근거·권고가 봉인된 정답과 의미상 일치하는지만 판정했으며, 정답은 독립 실행 검사·회귀 검사·봉인된 변이 명세를 우선했다. 사람 평가는 수행하지 않았다.”라고 명시한다. 판정 모델·버전, 판정 입력·출력 해시, 사전 검정 결과, 판정 실패 건수도 함께 보고한다. 이는 사람과 동등한 정확도나 사람의 진단 시간·재작업 개선을 뜻하지 않는다. 실제 LLM 판정 기록이 없으면 이 문구를 결과로 사용하지 않는다.

## 2. 표본과 split

### Pilot

초기 60건은 측정 도구·라벨·효과 분포를 확인하는 pilot이다.

- 결함 40건: 5개 공통 관점을 주 결함 기준으로 균형화하되 필요한 관점은 multi-label로 판정
- 음성·경계 20건: 정상, profiler neutral/harmful, workload 없음, unsafe
- 최소 4개 Python 저장소
- async/concurrency ≥ 25%, single/cross-file 각각 ≥ 30%
- fixed-five shadow 출력은 정답으로 사용하지 않는다. 평가 전용 생성기가 만든 결함·정상 후보 중 독립 재현 검사와 접근 분리 검사를 통과한 사례만 채택한다.

60건 자체가 최종 A+ 통계 근거는 아니다.

### Final evaluation

현행 v30의 최종 표본은 기존 80사례(정기 점검/후보 점검 × 숨긴 합성/시간 분리 공개 사례 각 20건)를 재사용해 강한 모델 단일 진단과 작은 모델 전체 시스템을 짝지어 비교하도록 설계했다. 같은 작은 모델 여섯 군도 별도 검증한다. Pilot에서 결함 단위 발견률의 분산, base rate, 가족 내 상관성을 추정하고 검정력을 확인한다. 80건으로 부족하면 우월성 주장을 보류한다. 최종 결과를 본 뒤 표본이나 성공 기준을 조용히 바꾸지 않는다.

- Critical/High Recall
- profiler beneficial Recall/Precision
- 적응형 관점 선택의 perspective omission Recall과 `-2%p` 비열등
- critic의 incremental valid counterevidence yield
- ephemeral probe의 differential/hermetic validity와 confirmation coverage
- 같은 20분 안에 검증 가능한 권고를 낸 비율

각 분모에 사전 최소 건수를 정하고 0건 stratum이 있으면 그 claim을 보고하지 않는다. 저장소·템플릿 가족과 가까운 중복 사례가 개발과 최종 집합을 가로지르지 않게 분리하고, label과 manifest 접근이 차단된 최종 holdout을 동결 버전으로 한 번만 실행한다.

비결정적 agent trial 횟수도 pilot 뒤 고정한다. 초기값 3회는 TARGET이지 외부 검증 수치가 아니다.

## 3. KPI 요약

| KPI | 1차 측정값 | 사전 목표 | 방어 지표 |
| --- | --- | --- | --- |
| 강한 단일 모델 대비 문제 발견률(최우선) | 같은 사례의 봉인된 모든 결함에 대한 작은 모델 전체 시스템과 강한 모델 1회 진단의 Recall 차이 | 가족 단위 bootstrap 95% CI 하한 > 0 | 중요 Recall ≥ 0.90, Precision ≥ 0.75, 중요 위험 부당 기각 0건 |
| 고유 발견·누락 | 두 방식 중 한쪽만 독립 검증한 결함 및 누락 목록 | 유형·교차 파일 여부별 모두 공개 | 정상 사례 오탐, 모든 미보고 결함을 FN에 포함 |
| LLM 호출 비용 | 두 방식의 실제 API 청구 금액 합계·확인된 TP당 금액 | 실측 후 공개; 사전 절감 주장 없음 | 모든 호출·실패·재시도·캐시 토큰 포함 |
| 20분 내 유효 권고율(기존 구성 기여 관문) | 봉인된 사례에서 기한 내 독립 검증 가능한 권고 / 전체 사례 | 같은 작은 모델 A 대비 F ≥ +30%p | 같은 예산, bootstrap CI 하한 > 0, 타임아웃 포함 |
| 실행 검증 연계율 | runtime confirmation rate | ≥ 0.70 | evidence attachment/rejection/failure |
| Profiler 활용률 | gold beneficial coverage | ≥ 0.80 | router R≥0.85, P≥0.80, unsafe 0 |
| 무근거 발견률 | 유효 근거 없는 최종 발견 / 전체 최종 발견 | ≤ 5%; 중요 위험 부당 기각 0건 | 근거 없는 실행 확인 0건 |
| 기계 생산성 | 독립 검증된 유효 권고 / 전체 시스템 컴퓨팅 시간 | 기준선 대비 수치와 신뢰구간 보고, 목표는 pilot 뒤 동결 | 전체 호출·토큰·실행 시간 포함 |

새 모델 간 비교는 사례당 권고 하나가 아니라 **모든 봉인 결함**을 분모로 한다. 진단 전에 별도 절차가 결함별 원인·유형·중요도·재현 근거를 봉인한다. 두 방식은 같은 스냅샷·입력 범위·결과 형식·20분·총 토큰 상한을 쓰되, 강한 모델은 1회 진단하고 작은 모델 시스템은 모든 관점과 도구를 사용한다. 따라서 이는 모델만의 우열이 아니라 **전체 시스템 대 강한 단일 진단**의 비교다. 매칭 실패·시간 초과는 FN이고, 정상 사례에서 근거 없는 주장은 FP다. 한쪽만 찾은 결함과 양쪽 모두 놓친 결함을 모두 공개한다. 평가 CLI의 v1은 6군·권고 하나, v2는 결함별 비교를 집계하지만, 실제 모델 호출·독립 정답·청구 원본을 생성하거나 증명하지 못한다.

## 4. KPI 1: 20분 내 유효 권고율(기존 구성 기여 관문)

같은 사례·작은 모델·전체 호출/토큰·도구 시간 상한에서 단순 LLM(A)과 제안 시스템(F)을 짝지어 비교한다. 독립 검사로 확인할 수 있는 원인·위치·조치를 마감 전에 제시한 사례만 성공이다. 실패·시간 초과·판정 불가는 성공에서 빼지 않고 분모에 남긴다. 이 지표 하나로 강한 모델보다 결함을 많이 찾았다고 주장하지 않는다.

$$
ValidRecommendationRate=\frac{N_{\mathrm{eligible\ cases\ with\ verified\ recommendation\ within\ 20min}}}{N_{\mathrm{eligible\ cases}}}
$$

두 군의 차이와 동일 가족을 묶어 재표본 추출한 95% 신뢰구간을 보고한다. 이는 실제 리뷰어의 진단 시간 단축률이 아니다. 시스템 지연 시간 median/p95는 별도 보고한다.

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

## 8. KPI 5: 무근거 발견률

최종 근거 객체의 모든 발견을 분모로 하여, 지정한 출처·줄·테스트/프로파일 결과로 뒷받침되지 않는 발견을 계수한다. 독립 실행 증거 없이 `runtime_confirmed`로 표시한 건수와 실제 Critical/High 결함을 부당하게 기각한 건수는 별도로 0건을 요구한다. 발견 0건이면 비율을 0으로 간주하지 않고 측정 불가로 보고한다.

## 9. KPI 6: 기계 생산성

$$
VerifiedRecommendationsPerComputeHour=
\frac{N_{\mathrm{independently\ verified\ recommendations}}}
{\mathrm{total\ system\ compute\ hours}}
$$

두 모델의 실제 API 청구 금액은 모든 입력·출력·캐시 토큰, 관점별 호출, 재시도, 실패한 호출까지 합산해 전체 사례 비용과 독립 확인된 TP당 비용으로 보고한다. 청구 금액·고정 가격표·사용량 로그를 연결하고 도구 실행 비용은 별도로 공개한다. 0 TP면 TP당 비용을 계산하지 않는다. 사람이 작업하는 시간이나 재작업 감소 효과로 해석하지 않는다.

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
- [`../project-context/ai-professional-project-proposal.md`](../project-context/ai-professional-project-proposal.md) — 무인 6대 KPI를 반영한 제출 기획서 수정 초안. 이전 사람 성과는 미측정.

REAP의 multi-run 검증과 본 과제 agent trial은 다른 절차다. Pilot 60건·3 trial은 프로젝트 설계안이며 파일럿에서 확정한다. 최종 표본은 현행 v30 계약의 80건으로 고정되고, power analysis가 부족한 부가 주장은 결과로 보고하지 않는다.

