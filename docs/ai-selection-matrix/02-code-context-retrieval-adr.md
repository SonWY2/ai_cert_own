# ADR-02: 공급자 중립 Code Graph와 bounded retrieval을 사용한다

- 날짜: 2026-08-23
- 상태: 제안
- 범위: 저장소 문맥 구성과 token 최적화
- 지원 기준선: Python 3.14

## 1. 맥락

Python 백엔드 결함은 호출자, 피호출자, 예외 경로, 테스트에 걸쳐 있다. 전체 저장소 입력은 비싸고 무관 문맥을 늘린다. lexical/vector 검색은 이름·의미가 가까운 코드를 찾지만 구조적으로 연결된 명칭 불일치 코드를 놓칠 수 있다.

## 2. 결정

Python 3.14 AST와 심볼 해석으로 **프로젝트 고유 Code Graph**를 만들고 exact/BM25 검색과 결합한다. 1-hop은 초기 운용 가설이며 외부 연구로 최적이라고 확정하지 않는다. 2-hop은 typed expansion request가 있을 때 최대 한 번 수행한다.

- 정확한 파일·심볼: exact/BM25
- 호출·상속·import·테스트 관계: Code Graph
- 자연어 기능 설명: vector를 보조 anchor로 사용
- unresolved/reflection/DI: 관계를 만들지 않고 원문 또는 실행 증거 요청

## 3. 후보 비교

| 후보 | 구조 Recall | 단순 조회 | token 효율 | 갱신 | 설명 가능성 | 종합 |
| --- | --- | --- | --- | --- | --- | --- |
| 전체 저장소 입력 | ++ | 0 | -- | ++ | + | 작은 저장소 기준선 |
| exact/BM25 | 0 | ++ | ++ | ++ | ++ | lexical 기준선 |
| vector-only | + | + | + | + | 0 | 보조 기준선 |
| 일반 지식 GraphRAG | + | - | - | -- | + | 코드에는 과도함 |
| **AST/심볼 graph + lexical anchor** | **++** | **++** | **++** | **+** | **++** | **제안 구성** |

최종 선택은 localization·evidence Recall·run-level token의 Pareto 비교 후 확정한다.

## 4. 최소 그래프 스키마

### 노드

| 종류 | 필수 속성 |
| --- | --- |
| `MODULE` | `symbol_id`, `path`, `source_hash` |
| `CLASS` | 위 속성 + source span |
| `FUNCTION`/`METHOD` | 위 속성 + `is_async`, `signature` |
| `CALLSITE` | 위치, 대상 또는 `unresolved_reason` |
| `TEST` | 테스트 심볼, 대상 후보, marker |
| `BASIC_BLOCK` | 함수 내 CFG path ID, source span |

### 엣지

| 관계 | 의미 |
| --- | --- |
| `CONTAINS` | module/class/function 계층 |
| `IMPORTS` | 모듈 의존 |
| `CALLS` | 정적으로 해석 가능한 호출 |
| `EXTENDS` | 클래스 상속 |
| `REFERENCES` | 심볼 참조 |
| `TESTS` | 테스트와 대상 연결 |
| `FLOWS_TO` | CFG basic block 전이 |
| `AWAITS` | await 대상 |
| `SPAWNS_TASK` | 정적으로 확인된 task 생성 |

AST source span과 CFG path ID를 분리한다. Python AST grammar가 release별로 변하므로 extractor와 fixture를 Python 3.14에 고정하고 다른 버전은 별도 adapter·회귀 검증 후 지원한다.

## 5. 검색과 가지치기

### 5.1 초기 단계

1. diff, 사용자 심볼, 진단 메시지에서 exact/BM25 anchor를 얻는다.
2. 자연어 질의에만 vector anchor를 추가한다.
3. anchor의 owner, caller, callee, import, direct test를 1-hop 확장한다.
4. 아래 tier 순으로 evidence budget을 채운다.

| tier | 포함 기준 |
| --- | --- |
| 0 | 사용자 지정·diff·exact symbol과 직접 원문 |
| 1 | 직접 caller/callee/import/owner와 direct test |
| 2 | BM25 상위 anchor, unresolved callsite 원문 |
| 3 | vector-only anchor와 조건부 2-hop 결과 |

같은 tier의 순서는 `graph_distance ASC → exact match DESC → BM25 score DESC → symbol_id ASC`로 결정한다. 임의의 선형 가중 점수는 사용하지 않는다.

### 5.2 조건부 확장 계약

```yaml
retrieval_expansion_request:
  request_id: UUID
  producer: structure | correctness | performance | concurrency | test
  target_perspective: structure | correctness | performance | concurrency | test
  reason: unresolved_path | missing_test_link | cross_module_boundary | evidence_gap
  anchor_symbol_ids: []
  allowed_relations: [CALLS, IMPORTS, TESTS]
  max_hops: 2
  remaining_token_budget: 0
```

- Static extractor는 request를 직접 만들지 않는다. Unresolved 정적 사실은 structure 관점 입력으로 전달하고 first-pass analyst가 필요성을 판단한다.
- 모든 1차 관점 분석이 끝난 뒤 Expansion Gate가 요청을 한꺼번에 수집한다.
- `target_perspective == producer`를 필수 검증하고 D2를 해당 관점으로 dispatch한다.
- Schema와 budget을 검증한 후 최대 하나만 선택한다.
- 안정 정렬 키: `reason_priority ASC → producer_priority ASC → anchor_symbol_ids lexical ASC → request_id ASC`.
- `reason_priority`: unresolved_path, cross_module_boundary, missing_test_link, evidence_gap 순서다.
- `producer_priority`: correctness, concurrency, performance, structure, test 순서다.
- 선택 request, 거부 request, `invalid | lower_priority | budget_exceeded` reason code와 미사용 budget을 모두 기록한다.
- 선택된 relation과 anchor만 최대 2-hop 확장하고 target perspective만 재분석한다.
- `max_hops > 2`, 빈 anchor/reason, producer/target 불일치는 거부한다.

### 5.3 초기 상한

| 설정 | 초기값 | 성격 |
| --- | ---: | --- |
| exact/BM25 anchor | 12 | calibration 후보 |
| 기본 깊이 | 1-hop | 프로젝트 가설 |
| 최대 graph node | 80 | calibration 후보 |
| symbol 원문 | 최대 200 tokens | calibration 후보 |
| evidence budget | `min(24,000, 0.25 × model_context)` | run-level 예산 내부 상한 |
| expansion | 최대 1회 | 안전 상한 |

이 값은 현재 성능 근거가 아니라 pilot 설정이다. test 전에 calibration으로 고정한다.

## 6. 최신 외부 근거와 적용 한계

- [LARGER v1, 2026-05-08](https://arxiv.org/html/2605.16352v1)은 lexical anchor에서 confidence-filtered graph neighborhood를 노출한다. MuLocBench fixed 설정에서 Acc@5/Recall@5 55.7/68.6, Codex 50.0/65.1을 보고했고 graph expansion 제거 시 Acc@5가 55.7에서 48.2로 낮아졌다.
- [Codebase-Memory v1, 2026-03-28](https://arxiv.org/abs/2603.27277v1)은 31개 저장소에서 graph 질의 품질 0.83 대 file explorer 0.92를 보고하는 대신 token을 약 1/10, tool call을 2.1배 줄였다.

둘 다 preprint이며 본 과제의 Python 결함·성능 진단을 직접 평가하지 않았다. 따라서 graph 사용은 지지하지만 1-hop, 80 node, 24k token을 정당화하지 않는다.

## 7. Graphify와 Semantica

- **Graphify**: [`graphifyy` 0.9.48](https://pypi.org/project/graphifyy/0.9.48/), `Graphify-Labs/graphify` commit [`b2cd362`](https://github.com/Graphify-Labs/graphify/commit/b2cd36267456c166788c95be6e68574064a92a42). 2026-07-05 갱신된 commit-pinned [`BENCHMARKS.md`](https://github.com/Graphify-Labs/graphify/blob/b2cd36267456c166788c95be6e68574064a92a42/BENCHMARKS.md)는 약 1M LOC ERPNext, Claude Opus 4.8, 6개 질문에서 key-fact coverage 70.8%→82.0%를 보고한다. 독립 결함 위치화 검증이 아니므로 핵심 근거로 사용하지 않는다.
- **Semantica**: [v0.6.6, 2026-08-20](https://github.com/semantica-agi/semantica/releases/tag/v0.6.6). 범용 context/KG/provenance 도구이며 AST/call-graph 결함 위치화 근거가 없다.

둘은 동일 프로젝트 benchmark를 통과할 때만 저장·색인 adapter 후보로 검토한다.

## 8. 위험과 통제

| 위험 | 통제 |
| --- | --- |
| reflection/decorator/DI 누락 | unresolved 보존, 실행 또는 abstain |
| stale graph | source hash mismatch 무효화, 증분 재색인 |
| expansion 폭발 | typed request, 관계·횟수·token 상한 |
| vector noise | graph 경로 없는 결과는 tier 3 |
| graph가 token 증가 | lexical/vector/full-input과 Pareto 비교 |

## 9. 채택 검증

- 관련 심볼 Recall@20 ≥ 0.90
- 같은 run-level 예산에서 full-input 대비 input token 30% 감소
- Recall 비열등 한계 -2%p를 one-sided CI로 통과
- vector-only보다 cross-file Top-5 정확도 +5%p
- 1-hop/2-hop의 추가 유효 증거와 token을 별도 보고

## 10. 현재 근거

- [LARGER v1](https://arxiv.org/html/2605.16352v1)
- [Codebase-Memory v1](https://arxiv.org/abs/2603.27277v1)
- [Python 3.14.7 `ast` documentation, updated 2026-08-22](https://docs.python.org/3.14/library/ast.html)
- [CodeQL Python control-flow documentation, accessed 2026-08-23](https://codeql.github.com/docs/codeql-language-guides/analyzing-control-flow-in-python/)

공식 문서는 구현 의미만 뒷받침한다. Recall·token·성능 수치는 프로젝트가 측정한다.

