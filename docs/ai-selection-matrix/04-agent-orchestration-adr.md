# ADR-04: 증거 게이트가 있는 bounded DAG를 사용한다

- 날짜: 2026-08-23
- 상태: 제안
- 범위: 진단 계획, 제한적 재검색, 실행 검증, 보고서 생성

## 1. 맥락

단일 agent loop는 탐색·진단·실행·보고 책임이 섞인다. 모든 단계를 고정 순서로 실행하면 필요 없는 관점과 도구까지 수행한다. 자유형 swarm은 호출 수와 오류 전파를 통제하기 어렵다.

## 2. 결정

의존 관계와 최대 단계를 명시한 **bounded conditional DAG**를 사용한다.

- 5개 관점은 1차 분석에서 병렬 실행
- graph 확장은 typed request가 있을 때 최대 한 단계
- test/profiler는 immutable ExecutionPolicy와 opt-in 통과 시 실행
- 모든 노드는 구조화된 계약과 run-level 예산을 소비
- 최종 채택은 단일 loop와 fixed-chain 비교 뒤 확정

조건부 DAG는 프로젝트 설계 가설이다. 최근 연구가 이 정확한 topology의 우월성을 입증했다고 주장하지 않는다.

## 3. 후보 비교

| 후보 | 완전성 | 병렬 | 조건부 실행 | 오류 격리 | 비용 통제 | 추적 | 종합 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 단일 LLM | -- | -- | 0 | -- | ++ | -- | 기준선 |
| 단일 loop | - | -- | + | - | 0 | 0 | loop 기준선 |
| fixed chain | + | -- | - | + | 0 | ++ | orchestration 기준선 |
| 자유 swarm | 0 | ++ | ++ | 0 | -- | - | 통제 곤란 |
| **bounded DAG + gate** | **++** | **++** | **++** | **++** | **+** | **++** | **제안 구성** |

## 4. 실행 그래프

```mermaid
flowchart TD
    A[Scope Guard / ExecutionPolicy] --> B[Graph & Static Extractor]
    B --> C1[Initial Context]
    C1 --> PL[Diagnosis Planner]
    PL --> D1[Five-perspective First Pass]
    D1 --> M1[First Merger]
    M1 --> EG{Expansion Gate}
    M1 -. base artifact .-> J[Expansion Completion Join]
    EG -- no expansion disposition --> J
    EG -- selected request --> C2[Bounded Expanded Context]
    C2 --> D2[Affected Perspective Re-analysis]
    D2 -->|delta or tombstone| J
    J --> M2[Final Merger]
    M2 --> R{Runtime evidence?}
    R -- no --> K[Evidence Gate]
    R -- focused test --> X[Authorized Test Executor]
    R -- profiler candidate --> O{Rule + opt-in + policy}
    O -- no --> A1[Abstain / not-needed reason]
    O -- yes --> Y[Profiler Executor]
    X --> H[RuntimeEvidence Normalizer]
    Y --> H
    H --> K
    A1 --> K
    K --> Z[Report Composer]
```

`PL`은 versioned diagnosis plan을 만들고 D1은 이 artifact에 의존한다. Planner가 실패·예산 차단되면 모든 5관점과 seed anchor를 포함한 deterministic fallback plan을 만들고 실패 상태·소비 예산을 기록한다. `J`는 Expansion Gate disposition을 항상 기다리며 selected request가 있으면 D2 terminal까지 기다린 뒤 M2를 정확히 한 번 실행한다. M2는 M1 base에 D2 delta/tombstone을 fingerprint+revision 순으로 적용하고, superseded/retracted history와 재분석하지 않은 관점을 보존한다.

## 5. 노드 계약

| 노드 | 입력 | 성공 출력 | 실패 출력 |
| --- | --- | --- | --- |
| Scope Guard | 사용자 범위·승인 | versioned ExecutionPolicy | 차단 사유 |
| Extractor | source snapshot | graph ID, static evidence | parse/unresolved |
| Planner | initial context·budget | versioned DiagnosisPlan | deterministic fallback plan |
| Analyst | DiagnosisPlan slice·budget | contributor Finding[] | abstained |
| Expansion Gate | 전체 first-pass request | 선택 request 1개 + 모든 거부 disposition | invalid/lower-priority/budget reason |
| Expansion Completion Join | M1 base, gate disposition, optional D2 terminal | atomic base+delta input | missing branch terminal |
| First/Final Merger | contributors; base + optional delta/tombstone | canonical findings, full history | schema/severity conflict |
| Runtime Router | finding·policy | test/profile/not-needed | blocked |
| Executor | authorized manifest | RuntimeEvidence | failed/inconclusive |
| Evidence Gate | findings·evidence | accepted/rejected/abstained | violations |
| Composer | gated findings | report | missing fields |

## 6. 증거 게이트

### 구조 무결성

- symbol과 source hash가 graph snapshot과 일치
- unresolved를 임의 관계로 바꾸지 않음

### 주장 근거

- claim마다 코드 위치 또는 runtime evidence 존재
- `runtime_confirmed`는 completed/supports RuntimeEvidence 필수
- 요청 범위 밖 일반 조언 제거

### 반례 검토

- 도달 가능한 경로인지 확인
- guard/cache/lock/test 반례 확인
- 해결되지 않은 반례는 confidence 조정이 아니라 `abstained`

### 보고 완전성

- perspectives, root cause, severity, 상태, 근거, 영향, 최소 조치 포함
- 실행 미승인·실패·불안정 상태 보존

## 7. 문맥과 예산

각 관점은 전체 대화 이력이 아니라 목표, graph snapshot, Finding schema, 자신의 context만 받는다.

모든 비교 가능한 LLM variant는 하나의 inclusive `B_run`을 공유한다.

- input, output, cached token, retry, planner, analyst, gate, composer 모두 포함
- 제안 초기 allocation: planner 10%, 5관점 합계 50%, merger/gate 20%, composer 20%
- allocation은 pilot 후보이며 calibration 뒤 고정
- 예산 초과 trial은 실패 또는 non-comparable로 표시
- unconstrained 운영점은 별도로만 보고

## 8. 초기 상한

| 설정 | 초기값 | 성격 |
| --- | ---: | --- |
| 최대 동시 관점 | 5 | 기획 관점 |
| graph expansion | 1회 | hard bound |
| node retry | 1회 | hard bound |
| executor timeout | 120초 | policy default |
| 최종 finding | 20개 | review budget |
| 동일 사례 trial | 3회 | pilot 후보 |

## 9. 위험과 통제

| 위험 | 통제 |
| --- | --- |
| 전달 맥락 손실 | canonical Finding + RuntimeEvidence |
| 병렬 결과 상충 | contributor 보존 + deterministic merge |
| judge 편향 | deterministic gate + blind calibration |
| 상태 변경 | immutable policy, sandbox, opt-in |
| 추가 계산량 | inclusive B_run |
| expansion 반복 | typed request 최대 1회 |

## 10. 채택 검증

- 단일 loop 대비 요구사항 누락 50% 감소
- 같은 B_run에서 Critical/High Recall +5%p
- same-router fixed chain 대비 wall time·tool call 개선
- mandatory-chain 대비 불필요 test/profiler call 30% 감소
- 무근거 발견률 ≤ 5%
- node 실패 시 독립 관점 결과 보존률 100%

비교 구성과 budget이 같지 않으면 DAG 우월성 주장을 하지 않는다.

## 11. 최신 근거

- [REAP v4, 2026-07-28 revision](https://arxiv.org/abs/2604.01527v4) — production-derived task, 실행 테스트, multi-run stability.
- [SWE-EVO v5, 2026-04-04 revision](https://arxiv.org/abs/2512.18470v5) — 평균 21개 파일의 장기 multi-file task와 부분 진행 평가.
- [HackDetect v1, 2026-07-24](https://arxiv.org/abs/2607.22368v1) — trace exposure·exploit·score inflation 감사.

내부 자막은 2026-08 동향을 찾는 2차 영감 자료로만 보존한다. DAG 성능·생산성의 1차 근거로 사용하지 않는다.

