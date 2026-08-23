# ADR-01: 다관점 진단에 하이브리드 분석을 사용한다

- 날짜: 2026-08-23
- 상태: 제안
- 범위: 구조, 정확성, 성능, 동시성, 테스트 진단
- 지원 기준선: Python 3.14

## 1. 맥락

정적 규칙은 재현성이 높지만 프로젝트 의도와 런타임 현상을 직접 이해하지 못한다. 단일 LLM은 의도와 여러 관점을 설명할 수 있지만 저장소 사실을 누락하거나 근거 없는 인과를 만들 수 있다.

## 2. 결정

**AST/심볼/CFG/의존 그래프의 결정론적 사실 + 관점별 LLM 추론 + 승인된 test/profiler 증거**를 하나의 발견 상태 기계로 결합한다.

LLM의 역할은 다음으로 제한한다.

- 우선 조사할 관점과 경로 제안
- 구조·실행 증거 사이의 위험 인과 가설 생성
- 반례와 필요한 실행 검증 제안
- 확인·기각된 결과의 영향과 최소 조치 설명

구조 사실 추출, 명령 승인, 실행 결과, 상태 승격은 결정론적 계층이 담당한다.

## 3. 후보 비교

평가 기호: `++` 매우 적합, `+` 적합, `0` 중립, `-` 부적합, `--` 매우 부적합

| 후보 | 재현성 | 프로젝트 의도 | 저장소 관계 | 런타임 사실 | 환각 통제 | 비용 | 종합 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 정적 규칙만 | ++ | -- | 0 | -- | ++ | ++ | 규칙 기준선 |
| 단일 LLM | -- | + | 0 | -- | -- | + | 설명 기준선 |
| Code Graph + 단일 LLM | + | + | ++ | -- | + | + | 구조 기준선 |
| **구조 분석 + 다관점 LLM + 실행 피드백** | **++** | **++** | **++** | **++** | **++** | **0** | **제안 구성** |

최종 채택은 같은 run-level 예산의 P0~P4 실험 뒤 확정한다.

## 4. 공통 Finding 계약

```yaml
finding_id: F-0001
schema_version: finding-v2
contributors:
  - contributor_id: UUID
    contributor_lineage_id: UUID
    contributor_fingerprint: sha256(scope_id,perspective,root_cause_category,primary_location)
    revision: 1
    supersedes_contributor_id: null
    disposition: active | superseded | retracted
    perspective: performance
    severity: high
    severity_reason: 주요 사용자 경로의 반복 timeout
    severity_evidence_ids: [E-PROFILE-002]
root_cause_category: sync_io_in_async
primary_location:
  symbol_id: package.module:Class.method
  file: src/example.py
  start_line: 10
  end_line: 25
severity: critical | high | medium | low
severity_rubric_version: severity-v1
severity_impact_code: user_path_timeout
severity_reason: 주요 사용자 경로의 반복 timeout
severity_evidence_ids: [E-PROFILE-002]
status: hypothesis | statically_supported | runtime_confirmed | rejected | abstained
claim: 한 문장의 검증 가능한 주장
evidence:
  static: [E-AST-001, E-GRAPH-021]
  runtime: [E-PROFILE-002]
verification:
  request_status: not_considered | candidate | not_needed | awaiting_approval | approved | declined
  run_status: not_started | running | completed | blocked | failed | inconclusive
  result: not_applicable | supports | refutes
  run_id: null
  reason_code: null
runtime_eligibility:
  state: unassessed | eligible | not_eligible
  reason_code: null
  verification_kind: none | test | profiler
counterevidence: []
impact: 사용자 또는 운영 영향
recommended_action: 최소 조치
```

### 병합 규칙

- 정규화 키: `root_cause_category + primary_location.symbol_id + overlapping_span`
- 같은 원인의 관점별 결과는 `contributors`에 모두 보존한다.
- span overlap은 `intersection / min(span_length) ≥ 0.5`일 때 같은 위치 후보로 본다.
- 원인 범주가 다르면 위치가 같아도 병합하지 않는다.
- contributor severity와 이유·증거를 모두 보존한다. Canonical severity는 `severity-v1`의 필수 impact code와 evidence 조건을 만족하는 가장 높은 등급을 선택하고, 동률은 `contributor_id ASC`로 판정 근거 순서를 고정한다. 조건을 충족하지 못한 상위 등급은 다음 검증 가능한 등급으로 낮춘다.
- 자유 점수 `confidence`는 정의·보정된 사용처가 없으므로 계약에서 제거한다.
- D2 re-analysis는 같은 `contributor_lineage_id`, 증가한 `revision`, 이전 `contributor_id`를 `supersedes_contributor_id`로 내보낸다. `contributor_fingerprint`는 후보 매칭용이며 update key가 아니다. 결론이 사라지면 같은 lineage의 `disposition=retracted` tombstone을 내보낸다. M2는 lineage별 최신 revision만 canonical 계산에 사용하되 이전 contributor를 history로 보존한다.

### 불변 조건

- source 위치와 정적 증거가 없으면 최종 발견으로 승격하지 않는다.
- 정적 성능 발견은 `hypothesis` 또는 `statically_supported`다.
- `runtime_confirmed`는 `run_status=completed`, `result=supports`, 실행 ID와 raw hash가 모두 필요하다.
- 유효한 static counterevidence가 claim을 반박하면 `status=rejected`, `request_status=not_considered`, `run_status=not_started`, `result=not_applicable`, `reason_code=static_counterevidence`와 counterevidence ID를 기록한다.
- 실행 불가·실패·불안정은 `abstained`와 정확한 실행 상태를 기록한다.

## 5. Severity rubric v1

| 등급 | 관찰 가능한 영향 | 범위·전제 | 실행 증거 규칙 |
| --- | --- | --- | --- |
| Critical | 데이터 손실·보안/격리 위반·서비스 전면 불가·자원 고갈로 SLO 붕괴 | 일반 경로 또는 낮은 전제 | 실행 재현 또는 결정론적 안전 위반 증거 필요 |
| High | 주요 사용자 경로의 잘못된 결과·지속적 timeout·큰 성능 회귀 | 흔한 입력/트래픽에서 재현 | 가능한 경우 실행 확인; 불가 시 `statically_supported` |
| Medium | 제한된 경로의 오류·성능 저하·명확한 테스트 공백 | 특정 입력·구성·규모 필요 | 정적 경로 증거로 충분, 실행 시 상태 갱신 |
| Low | 직접 장애가 없는 유지보수·가독성·경미한 테스트 개선 | 현재 사용자 영향 없음 | 코드 위치와 규칙 근거 필요 |

Tie-break 규칙:

1. 관찰 가능한 영향이 없으면 상위 등급을 선택하지 않는다.
2. 범위가 불명확하면 낮은 등급으로 두고 `abstained` 검증 요청을 남긴다.
3. 보안·데이터·권한 경계의 결정론적 위반은 Critical을 우선한다.
4. labeler는 rubric version과 판정 이유를 저장한다.

Severity 가중치 `{critical:4, high:3, medium:2, low:1}`는 KPI 보조 집계와 초기 profiler 우선순위에만 사용한다. 실제 비용값으로 해석하지 않는다.

## 6. 관점별 책임

| 관점 | 입력 | 산출물 | 금지 |
| --- | --- | --- | --- |
| 구조 | module/class/function, import/call/extends | 순환·책임 집중·경계 위반 | 성능 확정 |
| 정확성 | CFG, 예외, 상태 전이 | 도달 가능한 실패 경로 | 미실행 경로를 재현됐다고 주장 |
| 성능 | 반복·I/O·fan-out, profile table | 병목 가설·hotspot 해석 | raw 없이 개선률 주장 |
| 동시성 | async/task/lock/shared-state | blocking/race/deadlock 후보 | scheduling 결과 확정 |
| 테스트 | 변경·위험 경로와 테스트 연결 | 테스트 공백·재현 후보 | coverage만으로 품질 단정 |

## 7. 초기 설정

| 설정 | 초기값 | 성격 |
| --- | ---: | --- |
| 관점 수 | 5 | 기획서 5관점 대응; ablation 대상 |
| 관점별 재시도 | 최대 1회 | 설계 상한 |
| 반대 검토자 | 1개 | ablation 대상 |
| 최종 정적 증거 | 최소 1개 | gate |
| 동일 입력 trial | 3회 | pilot 설정; power analysis 후 확정 |

모든 값은 프로젝트 가설이다. 외부 수치로 검증됐다고 표현하지 않는다.

## 8. 비용과 위험

| 위험 | 통제 |
| --- | --- |
| 다중 호출 비용 | 포괄 run-level 예산과 단일 LLM 비교 |
| 중복 발견 | 정규화 키와 contributor 보존 |
| LLM 검토자 편향 | 결정론적 gate 우선, blind human calibration |
| 동적 dispatch 누락 | unresolved 보존, 실행 또는 abstain |
| 잘못된 테스트 정답 | 기존 테스트·재현 테스트·사용자 관찰 분리 |

## 9. 채택 검증

- 같은 run-level 예산에서 단일 LLM보다 전체 Recall +5%p 이상
- Critical/High Recall ≥ 0.90
- 무근거 발견률 ≤ 5%, 근거 없는 `runtime_confirmed` 0건
- 구조·관점·실행 계층 제거 시 사전 등록 지표가 유의하게 하락
- 추가 비용을 포함한 수용 true finding/비용이 기준선보다 높음

## 10. 최신 근거

- [LARGER v1, 2026-05-08](https://arxiv.org/html/2605.16352v1) — lexical anchor와 구조 확장의 최근 코드 검색 근거.
- [Codebase-Memory v1, 2026-03-28](https://arxiv.org/abs/2603.27277v1) — 구조 검색의 품질·token trade-off.
- [REAP v4, 2026-07-28 revision](https://arxiv.org/abs/2604.01527v4) — 실행 테스트와 다중 실행 안정성 검증.
- [HackDetect v1, 2026-07-24](https://arxiv.org/abs/2607.22368v1) — trace와 protocol validity 감사.

위 연구는 하이브리드 5관점 구성이 우월하다고 직접 입증하지 않는다. 5관점·severity·상태 계약은 프로젝트 설계이며 P0~P4 실험으로 검증한다.

