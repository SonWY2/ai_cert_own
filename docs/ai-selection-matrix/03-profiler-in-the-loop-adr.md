# ADR-03: 결정론적 정책으로 profiler를 선택 실행한다

- 날짜: 2026-08-23
- 상태: 제안
- 범위: Python 3.14 성능 가설의 실행 검증
- 도구 기준선: cProfile 3.14, py-spy 0.4.2, Scalene 2.3.0

## 1. 맥락

정적 코드만으로 호출 빈도, CPU/native 비중, 메모리 증가를 확정할 수 없다. 모든 진단에 profiler를 붙이면 지연·측정 왜곡·권한·workload 비용이 발생한다. 한 profiler도 모든 상황에 최적이지 않다.

## 2. 결정

**결정론적 초기 router + 사용자 opt-in + immutable ExecutionPolicy + 목적별 profiler + 구조화된 RuntimeEvidence**를 사용한다.

학습 router는 pilot과 power analysis가 요구하는 충분한 paired utility label을 확보한 뒤 별도 policy version으로만 비교한다. 이전의 고정 “100건” 기준은 근거가 없어 제거한다.

## 3. 도구 후보

| 도구 | 원리 | 호출 수 | live attach | Python/native | 메모리·copy | 주요 제약 | 역할 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `cProfile` | deterministic call 계측 | ++ | -- | - | -- | 계측 왜곡 | local 함수·test |
| `py-spy` 0.4.2 | out-of-process sampling | - | ++ | + | -- | ptrace, sampling 누락 | live CPU/hang |
| `Scalene` 2.3.0 | CPU/memory sampling | 0 | - | ++ | ++ | 프로젝트 overhead 미측정 | native/memory 심화 |

`낮은 overhead`는 vendor 특성 설명일 뿐 프로젝트 SLA가 아니다. 세 도구의 overhead와 안정성은 지원 환경에서 직접 측정한다.

## 4. 실행 상태 계약

Finding의 판단 상태와 실행 lifecycle을 분리한다.

```yaml
verification:
  request_status: not_considered | candidate | not_needed | awaiting_approval | approved | declined
  run_status: not_started | running | completed | blocked | failed | inconclusive
  result: not_applicable | supports | refutes
  run_id: null
  reason_code: null
```

### 상태 전이

```text
not_considered -> candidate | not_needed
candidate -> not_needed | awaiting_approval | blocked
awaiting_approval -> approved | declined
approved/not_started -> running | blocked
running -> completed | failed | inconclusive
completed -> supports | refutes
```

| terminal | Finding.status | 필수 증거 |
| --- | --- | --- |
| `completed + supports` | `runtime_confirmed` | run ID, raw hash, workload/environment/policy hash |
| `completed + refutes` | `rejected` | 같은 증거 + 반박 요약 |
| `not_needed` | 기존 정적 상태 유지 | 결정 규칙과 이유 |
| `declined/blocked/failed/inconclusive` | `abstained` | 상태별 reason code |

유효한 static counterevidence에 의한 `rejected`는 profiler lifecycle 밖의 전이다. 이 경우 `request_status=not_considered`, `run_status=not_started`, `result=not_applicable`, `reason_code=static_counterevidence`와 counterevidence ID를 사용한다.

LLM은 `approved`를 만들 수 없다. Scope Guard와 사용자 승인만 상태를 변경한다.

## 5. 결정론적 초기 router

### 5.1 후보 생성

다음 중 하나면 `candidate`다.

1. 사용자가 profiler를 명시적으로 요청
2. latency/CPU/memory 회귀 또는 장애 관찰이 있음
3. 같은 실행 경로에 정적 성능 신호가 2개 이상 있음
4. High/Critical 성능 가설의 우선순위가 실행 결과에 따라 달라짐

정적 신호: loop 내 I/O/DB, sync-in-async, call amplification, 반복 copy/serialization, unbounded task/queue/cache.

### 5.2 eligibility

다음 모두를 만족해야 `awaiting_approval`로 간다.

- 재현 workload와 immutable command manifest가 있음
- sandbox/reset 경계가 있음
- tool/platform capability가 있음
- 예상 실행 시간이 policy timeout 이내
- secret/개인정보 redaction 규칙이 있음

불충족이면 `blocked`; 후보가 아니면 `not_needed`다.

### 5.3 우선순위와 tie-break

| 순서 | 조건 | 조치 |
| ---: | --- | --- |
| 1 | unsafe 또는 policy 불일치 | `blocked` |
| 2 | 사용자가 명시 요청했고 eligible | 승인 요청 |
| 3 | 실제 회귀 관찰 + eligible | 승인 요청 |
| 4 | Critical/High + 정적 신호 2개 이상 + eligible | 승인 요청 |
| 5 | 그 외 | `not_needed` |

동시 후보가 실행 예산을 넘으면 severity weight `4/3/2/1`, 실제 관찰 유무, candidate 생성 시각 순으로 정렬한다. 이 weight는 비용 추정이 아니라 deterministic queue priority다.

### 5.4 도구 선택

| 조건 | 도구 | 초기 설정 |
| --- | --- | --- |
| live process CPU/hang | py-spy 0.4.2 | 100 Hz, 30초; `--native`와 `--nonblocking` 동시 금지 |
| memory/copy 또는 Python/native stack | Scalene 2.3.0 | CPU mode 먼저; memory는 별도 승인 |
| local 함수/test의 호출 수·누적 시간 | cProfile 3.14 | pstats 저장, 3회 pilot |
| I/O/async wait 원인 | profiler 단독 금지 | test/trace/log와 결합 |

같은 사례가 여러 조건이면 `live → memory/native → local` 순서로 한 도구를 선택한다. 추가 도구는 첫 결과가 inconclusive이고 예산·승인을 다시 통과할 때만 허용한다.

## 6. 학습 router 전환 조건

각 사례의 `no-profile`과 `profile` 진단을 같은 입력·모델·예산에서 생성하고 blind 전문가 2명과 tie-breaker가 다음 utility를 판정한다.

- `beneficial`: true finding 또는 severity 판단이 개선
- `neutral`: 최종 정답 변화 없음
- `harmful`: 잡음으로 FP/FN 또는 severity가 악화

train/calibration/final holdout을 repository 단위로 분리한다. 표본 크기는 pilot 분포와 목표 오차로 power analysis한다. rule/logistic/GBDT/calibrated policy를 비교하고 threshold와 cost matrix는 calibration 뒤 동결한다.

## 7. RuntimeEvidence와 HotspotRow

모든 raw profile은 공통 envelope를 먼저 가진다.

```yaml
runtime_evidence:
  schema_version: runtime-evidence-v1
  evidence_id: E-PROFILE-0001
  evidence_kind: profile
  case_id: PERF-001
  run_id: UUID
  execution_policy_id: UUID
  source_commit: sha
  source_hash: sha256
  graph_hash: sha256
  command_hash: sha256
  workload_hash: sha256
  environment_hash: sha256
  execution_policy_hash: sha256
  tool: py-spy
  tool_version: 0.4.2
  outcome: completed
  raw_uri: evidence://...
  raw_sha256: sha256
  redaction_manifest_hash: sha256
```

`HotspotRow`는 이 envelope ID를 참조하고 지원하지 않는 값은 `null`로 둔다.

초기 축약값(CPU 누적 80%, 항목 5%, 최대 20행, 3회, CV 20%)은 검증된 threshold가 아니라 pilot 후보다. 어떤 자원 축의 CV인지 명시하고 calibration에서 고정한다.

## 8. 도구 원리와 최신 상태

### cProfile 3.14

- 현재 Python 문서는 deterministic profiler와 `ncalls/tottime/cumtime`을 정의한다.
- benchmark 용도가 아니며 Python/C 비교를 왜곡할 수 있다.

### py-spy 0.4.2

- [2026-04-24 release](https://github.com/benfred/py-spy/releases/tag/v0.4.2)는 Python 3.14와 Linux aarch64 native extension을 지원한다.
- live attach는 ptrace/SYS_PTRACE가 필요할 수 있다.
- nonblocking은 partial stack 위험이 있다.

### Scalene 2.3.0

- [2026-05-12 release](https://github.com/plasma-umass/scalene/releases/tag/v2.3.0)는 Python/native stitched call graph, timeline, memory flame graph, free-threaded Python 지원을 추가했다.
- 현재 release의 프로젝트 workload overhead 수치는 없다. 과거 profiler benchmark 수치를 현재 선택·SLA 근거로 사용하지 않는다.

## 9. 채택 검증

비교: `never`, `always`, `LLM self-decision`, `deterministic rule`, `calibrated model`, `oracle`.

- gold beneficial Recall ≥ 0.85
- invocation Precision ≥ 0.80
- unsafe-run 0건
- always 대비 profiler time 30% 절감, performance Recall 비열등 -2%p
- confirmed true finding당 시간·비용이 always보다 낮음
- learned policy는 ECE/Brier와 final holdout을 통과

## 10. 최신 근거

- [Python 3.14.7 profiler documentation, updated 2026-08-22](https://docs.python.org/3.14/library/profile.html)
- [py-spy 0.4.2, 2026-04-24](https://github.com/benfred/py-spy/releases/tag/v0.4.2)
- [Scalene 2.3.0, 2026-05-12](https://github.com/plasma-umass/scalene/releases/tag/v2.3.0)
- [To Call or Not to Call v3, 2026-08-06](https://arxiv.org/abs/2605.00737v3)
- [UCCI v1, 2026-05-11](https://arxiv.org/abs/2605.18796v1)
- [SWE-Perf v2, 2026-07-01 revision](https://arxiv.org/html/2507.12415v2)

To Call·UCCI·SWE-Perf는 profiler trigger 성능을 직접 입증하지 않는다. Utility·calibration·반복 성능 평가 원리만 차용하고 프로젝트 paired 실험으로 검증한다.

