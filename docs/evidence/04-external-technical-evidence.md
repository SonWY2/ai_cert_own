# 최신 외부 기술 근거

- 기준일: 2026-08-23
- 기본 창: 2026-02-23 이후 6개월
- 최대 창: 2025-08-23 이후 1년, 6개월 자료가 없을 때만 사용
- 상태: 현재 기술 선택용 출처 전면 감사 완료

## 1. 근거 분류

| 표기 | 의미 |
| --- | --- |
| `FACT` | 출처가 해당 조건에서 직접 보고한 내용 |
| `DESIGN INFERENCE` | 본 과제에 적용하려는 설계 해석 |
| `TARGET` | 본 과제 사전 목표 |
| `PROJECT RESULT` | 본 과제 실행으로 얻은 값 |

현재 문서에는 `PROJECT RESULT`가 없다. Preprint와 vendor self-report는 독립 재현 전 일반화하지 않는다.

## 2. Code Graph와 bounded retrieval

### 2.1 LARGER

- 출처: [LARGER v1](https://arxiv.org/html/2605.16352v1), 2026-05-08, `preprint`
- `FACT`
  - lexical 결과를 graph anchor로 맞추고 confidence-filtered local neighborhood를 노출한다.
  - MuLocBench fixed 설정에서 Acc@5/Recall@5 55.7/68.6, Codex 50.0/65.1을 보고한다.
  - 평균 token 353K 대 Codex 521.8K, 시간 99.9초 대 139.9초를 보고한다.
  - graph expansion 제거 시 MuLocBench Acc@5가 55.7에서 48.2로 하락한다.
- `DESIGN INFERENCE`
  - lexical anchor를 먼저 사용하고 graph 확장은 bounded하게 수행한다.
- 한계
  - preprint, 일부 기준선 backbone 차이, 일부 telemetry 누락.
  - 본 과제 Python 결함·성능 진단의 1-hop/2-hop 최적값은 입증하지 않는다.

### 2.2 Codebase-Memory

- 출처: [Codebase-Memory v1](https://arxiv.org/abs/2603.27277v1), 2026-03-28, `preprint`
- `FACT`
  - Tree-Sitter graph를 66개 언어에 구성하고 31개 real repository에서 평가한다.
  - answer quality 0.83 대 file explorer 0.92, 약 10배 적은 token, 2.1배 적은 tool call을 보고한다.
  - graph-native query에서는 19/31 언어에서 explorer와 같거나 우수했다.
- `DESIGN INFERENCE`
  - graph는 full source 대체가 아니라 구조 질의와 token 절감 계층이다.
- 한계
  - 언어당 한 저장소, static graph, Apple M3 환경, systematic vector baseline 부족.

### 2.3 현재 제품 후보

- **Graphify**: [`graphifyy` 0.9.48](https://pypi.org/project/graphifyy/0.9.48/), commit [`b2cd362`](https://github.com/Graphify-Labs/graphify/commit/b2cd36267456c166788c95be6e68574064a92a42), package/commit 2026-08-20.
  - `FACT`: commit-pinned [`BENCHMARKS.md`](https://github.com/Graphify-Labs/graphify/blob/b2cd36267456c166788c95be6e68574064a92a42/BENCHMARKS.md)는 2026-07-05 갱신됐으며, 약 1M LOC ERPNext, Claude Opus 4.8, 6개 질문에서 key-fact coverage 70.8%→82.0%, 약 140K token/query를 보고한다.
  - 한계: vendor self-report이며 독립 결함 위치화 benchmark가 아니다.
- **Semantica**: [v0.6.6](https://github.com/semantica-agi/semantica/releases/tag/v0.6.6), 2026-08-20.
  - `FACT`: 범용 context/KG/provenance/GraphRAG 도구다.
  - 한계: AST/call-graph 결함 위치화 근거가 없다.

둘은 핵심 기술 근거가 아니라 동일 프로젝트 benchmark의 adapter 후보만 된다.

## 3. Profiler와 성능 검증

### 3.1 Python 3.14 cProfile

- 출처: [Python 3.14.7 profiler docs](https://docs.python.org/3.14/library/profile.html), updated 2026-08-22, `official docs`
- `FACT`
  - deterministic profiling과 `ncalls/tottime/cumtime`을 정의한다.
  - profiler가 benchmark 용도가 아니며 Python/C 비교를 왜곡할 수 있다고 명시한다.
- `DESIGN INFERENCE`
  - local 함수·focused test의 호출 수·누적 시간에 사용한다.

### 3.2 py-spy 0.4.2

- 출처: [v0.4.2 release](https://github.com/benfred/py-spy/releases/tag/v0.4.2), 2026-04-24, `official release`
- `FACT`
  - Python 3.14, Linux aarch64 native extension을 지원한다.
  - 공식 README/source는 기본 100 Hz, ptrace/SYS_PTRACE 제약, nonblocking partial stack 위험, `--native`와 nonblocking 비호환을 설명한다.
- `DESIGN INFERENCE`
  - live CPU/hang에 opt-in 사용한다.
- 한계
  - 현재 프로젝트 workload overhead는 미측정이다.

### 3.3 Scalene 2.3.0

- 출처: [v2.3.0 release](https://github.com/plasma-umass/scalene/releases/tag/v2.3.0), 2026-05-12, `official release`
- `FACT`
  - Python/native stitched call graphs, call timeline, memory flame graph, per-thread memory attribution, free-threaded Python 지원을 추가했다.
- `DESIGN INFERENCE`
  - Python/native 또는 memory/copy 원인 분리가 필요한 심화 단계에 사용한다.
- 한계
  - 현재 release의 프로젝트 workload overhead·정확도 수치는 없다. 과거 benchmark 수치를 현재 SLA로 사용하지 않는다.

### 3.4 SWE-Perf v2

- 출처: [SWE-Perf v2 HTML](https://arxiv.org/html/2507.12415v2), revision 2026-07-01, `preprint`
- `FACT`
  - 140개 real-repository performance instance를 제공한다.
  - warm-up 3회, 20회 반복, IQR filtering, Mann-Whitney와 effect threshold를 사용한다.
- `DESIGN INFERENCE`
  - profiler 밖 반복 benchmark와 correctness 선행 절차의 시작점으로 사용한다.
- 한계
  - profiler trigger quality를 평가하지 않는다.

### 3.5 PERFOPT-Bench

- 출처: [PERFOPT-Bench v1 HTML](https://arxiv.org/html/2607.07744v1) / [arXiv API](https://arxiv.org/abs/2607.07744v1), 2026-07-08, `preprint`
- `FACT`
  - 두 공식 rendering 모두 self-contained C benchmark에서 hidden correctness, verified speedup, trajectory audit를 결합한다.
  - raw speedup의 shortcut exploitation 위험을 보고한다.
- 메타데이터 주의
  - API abstract와 HTML의 task 수가 충돌한다. 본 설계는 task 수를 인용하거나 성능 근거로 사용하지 않는다.
- `DESIGN INFERENCE`
  - correctness·speedup·trace 결합을 Python 평가의 방법론 후보로만 사용한다.
- 한계
  - C benchmark이며 Python profiler 직접 근거가 아니다. Python workload에서 재현 전 일반화하지 않는다.

## 4. 선택적 도구 호출과 calibration

### 4.1 To Call or Not to Call v3

- 출처: [v3](https://arxiv.org/abs/2605.00737v3), latest revision 2026-08-06, `preprint`
- `FACT`
  - 6개 open model과 1개 proprietary model, 2개 tool, 6개 task를 평가한다.
  - need, utility, affordability를 분리하고 self-decision의 misalignment를 보고한다.
- `DESIGN INFERENCE`
  - profiler/no-profiler paired utility와 always/never/self/rule/oracle 비교를 사용한다.
- 한계
  - web search/calculator 계열이며 profiler가 아니다. 논문 score를 profiler 성능으로 전용하지 않는다.

### 4.2 UCCI

- 출처: [UCCI v1](https://arxiv.org/abs/2605.18796v1), 2026-05-11, `preprint`
- `FACT`
  - 75K production NER query, 4B/12B model, H100 환경에서 isotonic calibration을 사용한다.
  - micro-F1 0.91에서 cost 31% 감소, ECE 0.12→0.03을 보고한다.
- `DESIGN INFERENCE`
  - held-out calibration, explicit assumptions, cost-constrained threshold를 learned router 후보에 적용한다.
- 한계
  - two-model cascade이며 profiler invocation이 아니다. 31%를 본 과제 목표로 사용하지 않는다.

### 4.3 CostBench

- 출처: [CostBench v3](https://arxiv.org/abs/2511.02734v3), revision 2026-06-29, `preprint`
- `FACT`
  - dynamic cost와 multi-turn tool planning을 평가한다.
- `DESIGN INFERENCE`
  - latency/tool cost 변화와 trajectory-level budget 적응을 별도 시험한다.
- 한계
  - travel/synthetic tool domain이며 profiler 직접 근거가 아니다.

## 5. Agent 평가와 protocol validity

### 5.1 REAP

- 출처: [REAP v4](https://arxiv.org/abs/2604.01527v4), revision 2026-07-28, `ASE 2026 Industry Showcase`
- `FACT`
  - production-derived task, executable fail-to-pass test, test-relevance validation, multi-run stability를 결합한다.
  - 5개 model solve rate 42.9~58.2%를 보고한다.
- 적용
  - 실행 가능성, test relevance, flaky case 제거.
- 한계
  - 한 industrial monorepo/assistant, proprietary corpus.

### 5.2 SWE-EVO

- 출처: [SWE-EVO v5](https://arxiv.org/abs/2512.18470v5), revision 2026-04-04, `preprint`
- `FACT`
  - 7개 Python project, 48 long-horizon task, 평균 21개 파일·874 tests.
  - GPT-5.4+OpenHands 25%를 보고한다.
- 적용
  - multi-file 장기 reasoning과 partial progress를 별도 평가.
- 한계
  - 48 tasks, release-note 기반, Python 중심.

### 5.3 HackDetect

- 출처: [HackDetect v1](https://arxiv.org/abs/2607.22368v1), 2026-07-24, `preprint`
- `FACT`
  - 15 benchmark의 2,385 trace를 exposure→exploit→mislead로 감사한다.
  - 일부 benchmark에서 0.45~1.00 score inflation을 보고한다.
- 적용
  - gold/test/scorer exposure와 trace shortcut audit.
- 한계
  - post-hoc audit이며 본 과제 score validity는 직접 측정해야 한다.

## 6. 적응형 진단·반증·검증

### 6.1 SWE-Router

- 출처: [SWE-Router v1](https://arxiv.org/html/2607.00053v1), 2026-06-30, `preprint`
- `FACT`
  - coding agent의 partial trajectory를 본 뒤 약한/강한 model을 routing하는 방식을 평가한다.
- `DESIGN INFERENCE`
  - 초기 정적 신호뿐 아니라 graph 탐색·분석 결과를 본 뒤 관점 선택을 갱신할 수 있다.
- 한계
  - model routing이며 구조·정확성·성능·동시성·테스트 관점 생략을 직접 평가하지 않는다.

### 6.2 AgentAbstain

- 출처: [AgentAbstain v1](https://arxiv.org/html/2607.10059v1), 2026-07-11, `preprint`
- `FACT`
  - 최고 agent도 act/abstain paired accuracy 59.5%를 보고한다.
- `DESIGN INFERENCE`
  - Planner의 free-form confidence로 관점 skip을 결정하지 않고 typed reason, deterministic mandatory route, shadow calibration을 사용한다.
- 한계
  - tool action abstention이며 perspective routing 직접 근거가 아니다.

### 6.3 Adversarial Review

- 출처: [Adversarial Review v1](https://arxiv.org/html/2608.18167v1), 2026-08-16, `preprint`
- `FACT`
  - naive reviewer-critic은 SWE-PRBench F1 0.457이었고 evidence/concern을 구분한 text-constrained 구성은 0.533을 보고한다.
- `DESIGN INFERENCE`
  - 반복 debate 대신 High/Critical 충돌에만 근거 인용형 critic을 한 번 실행한다.
- 한계
  - 현행 Evidence Gate 대비 고유 counterevidence 이득은 프로젝트에서 별도 측정해야 한다.

### 6.4 LLM-generated counterexample

- 출처: [Improving Dynamic Specification Inference with LLM-Generated Counterexamples v1](https://arxiv.org/html/2604.10761v1), 2026-04-12, `preprint`
- `FACT`
  - Java method-level specification inference에서 invalid assertion 최대 11.68% 제거와 precision 최대 7% 개선을 보고한다.
- `DESIGN INFERENCE`
  - 독립 oracle과 claim quantifier가 있는 Finding에만 ephemeral falsification probe를 제한적으로 시험한다.
- 한계
  - Python repository 진단·race·성능 가설로 직접 일반화하지 않는다. Probe 미재현은 existential·확률적 가설의 반박이 아니다.

## 7. 최신 근거가 직접 입증하지 않는 것

- 본 과제의 1-hop, 80 node, 24k evidence budget
- 5관점 DAG의 우월성
- profiler deterministic router의 Precision/Recall
- 60개 pilot과 3 trial의 통계 충분성
- py-spy/Scalene의 프로젝트 overhead
- A+ KPI 달성
- fixed-five 대비 적응형 perspective routing의 Recall·token 개선
- `정확성+구조` 보호 관점의 최적성
- semantic critic의 Evidence Gate 대비 고유 이득
- ephemeral probe의 Python 진단 confirmation coverage와 oracle validity

이 항목은 모두 `DESIGN INFERENCE` 또는 `TARGET`이며 project ablation/final holdout으로만 승격한다.

## 8. 현재 기술 결정

- **설계 반영**: Python 3.14 deterministic graph, lexical anchor, bounded expansion, canonical Finding, `DiagnosisPlan v2`, fixed-five/shadow 안전 기준, `HypothesisContract v1`, immutable ExecutionPolicy, RuntimeEvidence, deterministic profiler router.
- **pilot 후 승격**: routed perspective execution, evidence-cited critic, ephemeral counterexample probe.
- **조건부**: vector anchor, learned router, 2-hop, Scalene memory mode, telemetry 기반 trace/log reasoning.
- **배제**: 자유형 specialist/swarm, 반복 debate, persistent free-form memory, full-repo 강제 입력, all-query GraphRAG, always profiler 운영, LLM-only graph, vendor 수치의 성능 증명 사용.

