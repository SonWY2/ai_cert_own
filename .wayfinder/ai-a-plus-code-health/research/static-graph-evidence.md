# 대규모 Python 정적·그래프 분석 근거

- 연구 티켓: `005` — 대규모 Python 정적·그래프 분석 근거 조사
- 조사 기준일: 2026-08-29
- 대상: 정기 기준 브랜치와 릴리스 후보를 비교하는 대규모 Python 백엔드 코드 건강검진
- 실행 경계: 이 자산 작성 중 대상 저장소 코드, 테스트, profiler, 후보 분석기는 실행하지 않았다. 현재 프로젝트에는 설계 문서만 있고 구현·실측 증적은 없다.

## 1. 요약

1. **[FACT] 하나의 정적 표현이 모든 관찰을 제공하지 않는다.** CPython AST는 구문과 위치를, `symtable`은 식별자 scope를 제공한다. CFG는 가능한 제어 경로를, 데이터 흐름은 값/taint 전파를, CPG는 이 표현들을 한 질의 표면에 결합한다. 각 상위 층은 하위 층에서 추론한 edge의 정확도를 상속하며, CPG라는 저장 형식 자체가 Python의 동적 호출을 더 정확하게 만들지는 않는다. [CPython `ast`](https://docs.python.org/3/library/ast.html), [CPython `symtable`](https://docs.python.org/3/library/symtable.html), [CodeQL Python control flow](https://codeql.github.com/docs/codeql-language-guides/analyzing-control-flow-in-python/), [CodeQL Python data flow](https://codeql.github.com/docs/codeql-language-guides/analyzing-data-flow-in-python/), [Joern CPG](https://docs.joern.io/code-property-graph/)
2. **[FACT] Python 전체에 대해 완전하고 정밀한 정적 call/data-flow graph를 약속할 근거는 없다.** `Any`, `eval`/`exec`, 계산된 `getattr`/`setattr`, custom attribute access, dynamic import, entry-point/DI 등록, monkey patch, descriptor/metaclass, native extension 때문에 정적 관찰은 필연적으로 미확정·과대근사·누락을 포함한다. 최근 Python 연구도 real-world에서 이 격차를 확인했다. [Python typing concepts](https://typing.python.org/en/latest/spec/concepts.html), [Python importlib](https://docs.python.org/3/library/importlib.html), [Python data model](https://docs.python.org/3/reference/datamodel.html#customizing-attribute-access), [ICSE 2026 Python SAST study](https://conf.researchr.org/details/icse-2026/icse-2026-research-track/30/An-Empirical-Study-on-Static-Application-Security-Testing-SAST-Tools-for-Python)
3. **[PROJECT-HYPOTHESIS] 최소 충분 기준선은 “얕지만 신뢰도와 provenance가 명시된 다층 관찰”이다.** Git diff + AST/scope + 명시적 import/definition/reference + 타입 진단 + lexical retrieval + 제한된 역방향 영향 전파를 기본으로 하고, edge마다 `resolved / modeled / heuristic / unknown`을 기록한다. CFG·interprocedural dataflow·CPG·vector/graph retrieval은 독립 기여와 비용을 대조 실험으로 입증한 뒤 승격한다.
4. **[FACT] 증분성은 도구마다 단위가 다르다.** Ruff는 unchanged-file cache, mypy daemon은 finer-grained dependency tracking, Pyright watch는 in-memory affected-portion reanalysis, 최신 CodeQL은 changed-file overlay와 base query cache를 제공한다. “증분 지원”이라는 단일 boolean 대신 parse, semantic invalidation, query evaluation, reporting, persistent cache를 각각 측정해야 한다. [Ruff](https://docs.astral.sh/ruff/), [mypy daemon](https://mypy.readthedocs.io/en/stable/mypy_daemon.html), [Pyright maintainer answer](https://github.com/microsoft/pyright/discussions/4809), [CodeQL incremental analysis](https://docs.github.com/en/code-security/how-tos/find-and-fix-code-vulnerabilities/scan-from-the-command-line/incremental-analysis)
5. **[FACT] lexical, vector, graph retrieval은 대체재가 아니라 서로 다른 recall 채널이다.** lexical은 exact identifier/config/error string에 강하고 결정적이다. vector는 의미적 표현 차이를 흡수하지만 model/index 비용과 drift가 있다. graph retrieval은 이미 신뢰할 수 있는 definition/reference/import edge가 있을 때 주변 문맥을 확장한다. CoIR에서 BM25 평균 NDCG@10은 29.79, 최고 dense 후보는 56.26이었지만 과제별 승자가 달랐고, CoIR 자체도 실제 code metadata와 다중 정답을 충분히 다루지 못한다고 명시한다. 이는 건강 진단 성능 증거가 아니라 retrieval 실험 후보의 근거다. [CoIR, ACL 2025](https://aclanthology.org/2025.acl-long.1072.pdf)
6. **[UNSUPPORTED] CPG, vector DB, 특정 type checker, 특정 AI graph method를 지금 기본 제품으로 채택하는 결론은 근거가 부족하다.** 외부 수치의 workload가 이 프로젝트의 규모·framework·typing·DI·async 분포와 다르고, patch success는 위험 진단 정확도가 아니다. 후속 결정 티켓은 아래 후보를 동일 데이터·동일 예산으로 검증해야 한다.

## 2. 주장 등급과 조사 방법

| 등급 | 의미 |
|---|---|
| **FACT** | 공식 언어/도구 문서, peer-reviewed 논문 또는 공개 artifact가 직접 지지하는 외부 사실. 외부 결과는 해당 workload에만 한정한다. |
| **PROJECT-HYPOTHESIS** | 이 시스템에 적용할 설계 가설. 구현·실측 전에는 프로젝트 성과가 아니다. |
| **UNSUPPORTED** | 공개 근거가 없거나, 다른 과제의 성과를 진단 성과로 전용했거나, 현재 자료만으로 채택할 수 없는 주장. |

조사 우선순위는 2024년 이후 논문·공식 문서였으며, AST/symbol/gradual typing/IFDS처럼 오래됐어도 여전히 기준인 공식 원리도 포함했다. vendor 문서의 속도 주장은 capability 존재 확인에만 사용하고 프로젝트 성능 예상치로 사용하지 않았다. 공개 artifact가 있어도 실행 지침·환경·ground truth가 불완전하면 재현 완료로 간주하지 않았다. 이하 표에서 외부 관찰은 `FACT`, 이 프로젝트에 권고하는 설계·후보 위치·gate는 별도 표기가 없어도 `PROJECT-HYPOTHESIS`, 근거 부족 또는 금지 결론은 `UNSUPPORTED`로 읽는다.

## 3. 관찰 층 비교

| 층 | 직접 관찰 가능한 것 | 직접 관찰하지 못하는 것 / Python 한계 | 성능·증분 특성 | 이 프로젝트에서의 위치 |
|---|---|---|---|---|
| **AST / CST** | **[FACT]** 함수·클래스·호출 표현식·decorator·import·exception/async 구문과 source range. CPython AST grammar는 Python release와 함께 바뀔 수 있다. [CPython `ast`](https://docs.python.org/3/library/ast.html) | **[FACT]** `Call.func`는 구문 노드일 뿐 runtime callee가 아니다. AST만으로 scope, type, alias, feasible path, 실행 빈도를 알 수 없다. [CPython AST grammar](https://docs.python.org/3/library/ast.html#abstract-grammar) | **[FACT]** Tree-sitter는 concrete tree의 incremental update와 syntax-error tolerance를 목표로 한다. CPython AST는 대상 Python semantics와 맞지만 release-bound다. [Tree-sitter](https://tree-sitter.github.io/tree-sitter/) | **기준선 후보.** CPython AST를 semantic truth anchor로, Tree-sitter를 오류 허용형 indexing 후보로 대조한다. 둘을 이유 없이 중복 운영하지 않는다. |
| **Symbol / scope** | **[FACT]** `symtable`은 compiler가 AST에서 bytecode 생성 직전에 계산하는 각 식별자의 scope를 노출한다. SCIP는 definition/reference 교환 형식을 제공한다. [CPython `symtable`](https://docs.python.org/3/library/symtable.html), [SCIP](https://scip-code.org/) | **[FACT]** 동일 이름의 runtime object identity, 계산된 attribute, monkey-patched member, plugin registration을 scope만으로 확정할 수 없다. [Python data model](https://docs.python.org/3/reference/datamodel.html#customizing-attribute-access) | 보통 file/module 단위로 저렴하다. **[UNSUPPORTED]** `scip-python`의 현재 대규모 Python 3.11+ 정확도·유지보수·증분 성능은 이 조사에서 확립되지 않았다. [scip-python 공개 README](https://github.com/sourcegraph/scip-python) | **기준선 후보.** local definition/reference와 explicit import edge부터 저장하고 unresolved reference를 버리지 않는다. |
| **Type / semantic model** | **[FACT]** annotation, stub, narrowing, inferred expression type로 attribute/call 후보를 줄이고 type misuse를 찾는다. Python은 gradual typing이며 `Any` 연산은 정적으로 검사할 수 없다. [Typing spec](https://typing.python.org/en/latest/spec/concepts.html) | **[FACT]** untyped/`Any` 경계, dynamic decorator/metaprogramming, runtime-generated class/member는 blind spot이다. mypy 문서도 dynamically computed dataclass decorator를 인식하지 못한다고 명시한다. [mypy additional features](https://mypy.readthedocs.io/en/stable/additional_features.html) | **[FACT]** mypy daemon은 memory graph와 fine-grained dependency tracking을, Pyright watch는 affected portions의 memory reanalysis를 사용한다. Pyright CLI에는 persistent disk cache가 없다는 maintainer 설명이 있다. [mypy daemon](https://mypy.readthedocs.io/en/stable/mypy_daemon.html), [Pyright cache discussion](https://github.com/microsoft/pyright/discussions/4809) | **기준선 후보이되 제품 미선정.** Pyright/mypy를 typing coverage strata와 정책 안전성까지 같은 fixture로 비교한다. |
| **CFG** | **[FACT]** reachability, branch/loop/exception/finally 경로, dominance, unreachable block. 한 AST node가 여러 control-flow nodes에 대응할 수 있다. [CodeQL control flow](https://codeql.github.com/docs/codeql-language-guides/analyzing-control-flow-in-python/) | 실행 확률·빈도·latency와 runtime-resolved call target은 알 수 없다. implicit exceptions, async suspension, generator, context manager lowering의 fidelity가 frontend에 좌우된다. | 함수별 CFG는 국소 재생성이 가능하지만 caller summary·exception model 변경은 fan-out을 만든다. **[PROJECT-HYPOTHESIS]** 함수 content hash와 semantic dependency fingerprint를 invalidation key로 쓴다. | **실험 후 제한 승격.** unreachable/resource/exception risk처럼 CFG가 실제 finding을 추가하는 rule에만 사용한다. |
| **Dataflow / taint / slice** | **[FACT]** local/global value flow, taint propagation, source-to-sink path, backward slice 후보. CodeQL은 local flow가 global보다 빠르고 정밀하며, global flow는 더 강력하지만 시간·메모리와 precision 비용이 크다고 설명한다. [CodeQL data flow](https://codeql.github.com/docs/codeql-language-guides/analyzing-data-flow-in-python/) | source/sink/sanitizer/library model이 없으면 누락되고, alias/call graph 오차가 전파된다. 동적 attribute/import와 native code 경계를 정적으로 완결할 수 없다. | **[FACT]** 2026 PyFlow preprint의 공개 run은 206 program versions 중 45개가 600초 timeout, 2개가 실패했다. 완료 159개의 solver median은 6.8초였으나 frontend/reporting은 제외했다. [PyFlow](https://arxiv.org/html/2608.07026v1#S5.SS2) | **격리 실험.** 핵심 risk class별 모델과 budget/partial-result 표기가 필수다. |
| **CPG / PDG** | **[FACT]** syntax, control, intra/interprocedural data dependencies를 labeled property graph로 함께 질의하고 evidence path를 표현한다. Joern Python frontend에는 venv/type propagation options가 있다. [Joern CPG](https://docs.joern.io/code-property-graph/), [Joern Python frontend](https://docs.joern.io/frontends/python/) | **[PROJECT-HYPOTHESIS]** CPG는 container이며 edge truth를 개선하지 않는다. 부정확한 call/type edge를 한 graph에 합치면 정교한 오답 경로가 만들어질 수 있다. | **[FACT]** CPG 규모·memory가 병목이라는 2024 공개 preprint가 있고, PyFlow는 expression-level lowering이 basic-block representation보다 node 수를 3–5배 늘렸다고 보고한다. 두 수치 모두 이 프로젝트 workload 증거는 아니다. [QVoG preprint](https://arxiv.org/html/2406.08098v1), [PyFlow](https://arxiv.org/html/2608.07026v1#S4.SS6) | **보류/실험 후보.** 복수 finding이 같은 graph traversal을 재사용해 순기여를 보일 때만 기본 경로로 승격한다. |
| **Change-impact graph** | explicit changed line/symbol에서 reverse import/reference/call/test ownership으로 퍼지는 잠재 영향 범위. Pants는 Git changed files와 direct/transitive dependents selection을 제공한다. [Pants changed selection](https://www.pantsbuild.org/stable/docs/using-pants/advanced-target-selection) | 실제 영향, runtime-only registration, changed dependency lockfile의 세밀한 영향은 확정하지 못한다. Pants 문서도 transitive third-party dependency를 이해하지 못하고 lockfile 변경이 과대 fan-out될 수 있음을 명시한다. [Pants caveat](https://www.pantsbuild.org/stable/docs/using-pants/advanced-target-selection#running-over-changed-files-with---changed-since) | base snapshot을 재사용하되 deletion/rename/config/analyzer-version을 transactional하게 invalidation해야 한다. | **기준선 후보.** scan exclusion이 아니라 risk ranking과 검토 범위의 한 feature로만 사용한다. |

## 4. 핵심 외부 근거 표

| 근거 | 직접 확인한 사실 | 해석 한계 / 결정 영향 |
|---|---|---|
| [CPython AST 3.14 문서](https://docs.python.org/3/library/ast.html) | **[FACT]** AST는 abstract grammar와 source locations를 제공하며 grammar는 release별 변경 가능하다. | target Python version matrix가 parser/cache key에 들어가야 한다. AST는 call target graph가 아니다. |
| [CPython `symtable`](https://docs.python.org/3/library/symtable.html) | **[FACT]** compiler의 identifier scope table을 실행 없이 조회한다. | scope는 inter-module resolution이나 runtime object identity가 아니다. |
| [Tree-sitter 공식 문서](https://tree-sitter.github.io/tree-sitter/) | **[FACT]** incremental concrete parsing과 syntax-error tolerance를 목표로 한다. | parser 성능 claim은 semantic resolution 정확도 claim이 아니다. Python grammar version fidelity를 별도 검증한다. |
| [Python typing spec](https://typing.python.org/en/latest/spec/concepts.html) | **[FACT]** Python은 gradual typing이고 `Any`는 statically unknown이므로 그 연산의 type correctness를 checker가 검사할 수 없다. | type diagnostic count를 typing coverage 없이 비교하면 잘못된 안정감이 생긴다. |
| [Ruff 공식 문서](https://docs.astral.sh/ruff/) | **[FACT]** unchanged-file caching과 광범위한 built-in rules를 문서화한다. | vendor benchmark는 채택 근거로 쓰지 않는다. Ruff는 whole-program type/dataflow graph의 증거가 아니다. |
| [mypy daemon](https://mypy.readthedocs.io/en/stable/mypy_daemon.html) | **[FACT]** in-memory state, fine-grained dependencies, changed files와 dependents recheck를 제공한다. | “10x+”는 project-independent guarantee가 아니다. daemon은 단일 request 처리이며 cache coherence/config change를 검증해야 한다. |
| [mypy plugin 문서](https://mypy.readthedocs.io/en/stable/extending_mypy.html#extending-mypy-using-plugins) | **[FACT]** config의 Python plugin 파일/module을 mypy가 import한다. | “정적 도구 실행”도 대상 저장소 제공 plugin code를 실행할 수 있다. sanitized config 또는 정책 승인 sandbox 없이는 자동 경로에 넣지 않는다. |
| [Pyright maintainer cache 설명](https://github.com/microsoft/pyright/discussions/4809) | **[FACT]** `--watch`는 affected portions를 memory에서 재분석하고 persistent disk cache는 없다고 설명한다. | 2023 maintainer 답변은 후속 release에서 재확인해야 한다. CI process 재시작 시 cold cost를 별도 측정한다. |
| [CodeQL control-flow 문서](https://codeql.github.com/docs/codeql-language-guides/analyzing-control-flow-in-python/) | **[FACT]** Python CFG, basic block, reachability/dominance query surface와 exception/finally 다중 경로 예시를 제공한다. | capability 문서이지 프로젝트 진단 precision/scale 증거는 아니다. |
| [CodeQL data-flow 문서](https://codeql.github.com/docs/codeql-language-guides/analyzing-data-flow-in-python/) | **[FACT]** local/global dataflow와 taint API를 제공하며 global은 local보다 덜 정밀하고 더 많은 시간·메모리를 요구한다. | finding 품질은 query와 API model에 좌우된다. commercial/vendor default query 성과를 자체 health diagnosis 성과로 간주하지 않는다. |
| [CodeQL incremental 공식 문서](https://docs.github.com/en/code-security/how-tos/find-and-fix-code-vulnerabilities/scan-from-the-command-line/incremental-analysis) | **[FACT]** CLI 2.21+ diff-informed, 2.23.8+ overlay가 있고 overlay는 base DB/query cache를 재사용해 changed files를 처리한다. diff-informed는 changed-line alert reporting과 CI-side SARIF filtering이다. | “up to 10x” vendor 수치는 채택 근거가 아니다. changed-line filtering은 unchanged dependent의 새 risk를 숨길 수 있으므로 우선순위용이지 completeness 경계가 아니다. overlay는 `build-mode:none` 제약과 base compatibility가 있다. |
| [Joern CPG 문서](https://docs.joern.io/code-property-graph/) | **[FACT]** directed labeled attributed multigraph에 classic representations와 overlays를 결합한다. | representation 통합과 diagnostic lift는 별개다. Python frontend fidelity와 incremental rebuild를 실측해야 한다. |
| [JARVIS call-graph preprint, v5 2024](https://arxiv.org/html/2305.05949) | **[FACT]** 135 micro programs와 6 real applications에서 application-centered, flow-sensitive call graph를 PyCG와 비교했다. PyCG whole-program runs는 8GB/24h 한도에서 timeout/OOM/recursion error를 보였고 JARVIS는 application-centered 평균 8.16초/227MB를 보고했다. | 저자 preprint 결과이며 application LOC가 0.5k–5k, library-inclusive 108k–515k였다. “whole repository health graph” 성능으로 일반화하지 않는다. entry-point 중심 scope control 후보만 지지한다. |
| [PyFlow preprint, 2026](https://arxiv.org/html/2608.07026v1) | **[FACT]** multi-level AST→CFG→SSA→PDG/CPG와 IFDS/pointer analysis, pass cache/invalidation을 공개했다. real-world SAST run은 recall 48.1%, precision 71.2%, F1 57.5%를 보고했지만 206 versions 중 45 timeout, 2 failed였다. | 매우 최신 arXiv preprint이며 저자 snapshot이다. frontend 시간을 제외한 solver timing, default baseline config, synthetic LLM-generated cases라는 제한이 있다. 격리 실험 후보이지 기준선이 아니다. |
| [ICSE 2026 Python SAST study](https://conf.researchr.org/details/icse-2026/icse-2026-research-track/30/An-Empirical-Study-on-Static-Application-Security-Testing-SAST-Tools-for-Python) | **[FACT]** 8 tools/108 real-world CVEs에서 단일 tool recall은 40% 이하, 전체 tool union도 66.7%였다고 보고한다. | security vulnerability workload이며 일반 code-health risk 전부를 대표하지 않는다. 그래도 “도구 여러 개=완전성” 가정을 기각한다. |
| [PySASTBench artifact](https://github.com/Victor725/PySASTBench) | **[FACT]** 108 CVE metadata, tool versions, Dockerfiles, Zenodo dataset 링크가 공개되어 있다. README는 source-code 사용 지침이 “released soon”이라고 적는다. | 부분 공개 재현 근거다. 후속 실행 티켓은 artifact completeness와 license를 먼저 확인한다. |
| [CoIR, ACL 2025](https://aclanthology.org/2025.acl-long.1072.pdf) | **[FACT]** 10 datasets/8 retrieval subtasks/2M+ documents에서 BM25와 9 dense models를 비교했다. BM25 평균 NDCG@10 29.79, dense 최고 평균 56.26이었으나 단일 model이 모든 task를 지배하지 않았다. embedding latency/index size trade-off도 보고했다. | 다언어 일반 code retrieval이며 repository health finding localization이 아니다. 영어-only, metadata 부족, query당 단일 ground truth라는 논문 자체 제한이 있다. vector는 격리 실험만 지지한다. |
| [RepoGraph, 2025 version](https://arxiv.org/html/2410.14684) | **[FACT]** Python line-level definition/reference/invoke/contain graph와 k-hop retrieval을 SWE-bench patch generation에 결합했다. | 평가 metric은 issue resolve/patch apply/cost이지 진단 precision/recall이 아니다. graph retrieval의 진단 기여는 **[UNSUPPORTED]**다. |
| [LLM type/call-graph study, 2025](https://arxiv.org/html/2410.00603) | **[FACT]** 공개 micro-benchmarks에서 24 LLM을 비교했고 Python call graph는 PyCG가 LLM보다 우수했으며 LLM은 completeness/soundness에 어려움이 있었다고 보고한다. artifact/Zenodo를 공개했다. | micro-benchmark 중심 preprint다. LLM type inference 가능성은 별도 실험 후보지만, LLM이 생성한 edge를 core truth로 채택할 근거는 없다. |
| [Pants changed selection 2.33](https://www.pantsbuild.org/stable/docs/using-pants/advanced-target-selection) | **[FACT]** Git base 이후 changed files와 direct/transitive dependents selection을 지원하고 third-party/lockfile caveat를 문서화한다. | Pants 제품 채택 근거가 아니라 change-impact semantics와 caveat의 공개 사례다. |
| [SQLite FTS5](https://www.sqlite.org/fts5.html) | **[FACT]** phrase/prefix/NEAR/column/boolean query, trigram tokenizer, BM25 ranking, update/delete/rebuild/integrity operations을 제공한다. | lexical index 구현 후보일 뿐 진단 정확도 증거가 아니다. tokenizer가 Python identifiers/dotted names에 맞는지 실험해야 한다. |

## 5. 동적 Python 한계와 처리 원칙

| 동적 패턴 | 사실과 실패 모드 | 설계 처리 |
|---|---|---|
| `Any` / untyped boundary | **[FACT]** `Any`는 statically unknown이며 checker는 `Any` expression의 operation correctness를 검사할 수 없다. [Typing spec](https://typing.python.org/en/latest/spec/concepts.html#static-dynamic-and-gradual-typing) | finding confidence에 typedness, `Any` ingress/egress, stub 존재를 포함한다. “type error 0”을 건강함으로 해석하지 않는다. |
| `eval` / `exec` / generated code | **[FACT]** built-ins는 string/code object를 실행하며 static source에 없는 동작을 만들 수 있다. [Python `exec`](https://docs.python.org/3/library/functions.html#exec), [LLM/static study motivating example](https://arxiv.org/html/2410.00603#S2.SS1) | 호출 위치·input provenance를 risk로 표기하고 이후 runtime behavior를 추측해 graph edge로 만들지 않는다. |
| dynamic import / import hook | **[FACT]** `importlib.import_module(name)`은 name argument로 module을 import하고 custom importer가 import process에 참여할 수 있다. [importlib](https://docs.python.org/3/library/importlib.html#importlib.import_module) | literal/finite-string name은 `modeled`, 그 외는 `dynamic-import-unknown`. `sys.meta_path`, path mutation, namespace package를 limitation flag로 남긴다. 대상 module import로 확인하지 않는다. |
| package entry points / plugin discovery | **[FACT]** distribution metadata entry points는 group/name으로 loadable components를 discover한다. [importlib.metadata entry points](https://docs.python.org/3/library/importlib.metadata.html#entry-points) | lockfile/metadata/known config를 정적으로 읽어 candidate edge를 만들 수 있지만 `registered`, `enabled`, `executed`를 구분한다. |
| reflection / calculated attribute | **[FACT]** custom `__getattribute__`/`__getattr__`, descriptors와 `getattr`/`setattr`은 일반 source member lookup을 우회·확장한다. [Python data model](https://docs.python.org/3/reference/datamodel.html#customizing-attribute-access), [built-in `getattr`](https://docs.python.org/3/library/functions.html#getattr), [built-in `setattr`](https://docs.python.org/3/library/functions.html#setattr) | literal attribute는 modeled edge, computed name은 unresolved evidence로 저장한다. name-match를 resolved call로 승격하지 않는다. |
| decorator / metaclass / framework synthesis | **[FACT]** mypy도 dynamically computed dataclass decorators를 인식하지 못한다고 문서화하며, plugin으로 framework semantics를 보충한다. [mypy dataclass caveat](https://mypy.readthedocs.io/en/stable/additional_features.html#caveats-known-issues), [mypy plugins](https://mypy.readthedocs.io/en/stable/extending_mypy.html#extending-mypy-using-plugins) | framework adapter는 versioned model pack으로 분리하고 model coverage를 출력한다. adapter 부재를 silent false negative로 두지 않는다. |
| dependency injection | **[PROJECT-HYPOTHESIS]** constructor/default callable이 source에 명시된 DI는 일부 resolve 가능하지만 config/string/provider/runtime container 등록은 framework model 없이는 불확정이다. 동적 API의 일반적 한계는 [mypy plugin rationale](https://mypy.readthedocs.io/en/stable/extending_mypy.html#extending-mypy-using-plugins)가 지지한다. | DI framework/version별 fixture로 provider→consumer edge precision/recall을 재고, 범용 이름 추측은 금지한다. |
| monkey patch | **[FACT]** Python object attribute는 runtime `setattr`로 교체될 수 있고 test tooling도 attribute/item/environment mutation을 공식 지원한다. [Python `setattr`](https://docs.python.org/3/library/functions.html#setattr), [pytest monkeypatch](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) | static edge에 `may-be-rebound`를 표시한다. 승인된 test/runtime trace가 있을 때만 observed edge를 별도 lane에 추가한다. |
| C/native extension / generated stub gap | **[FACT]** C/C++ extension module은 Python source에 없는 built-in object type과 C library/system-call 동작을 구현할 수 있고, CodeQL은 source 없는 C module을 unreachable query에서 별도 주의한다. [Extending Python with C/C++](https://docs.python.org/3/extending/extending.html), [CodeQL control flow](https://codeql.github.com/docs/codeql-language-guides/analyzing-control-flow-in-python/#example-finding-unreachable-ast-nodes) | stub/model 없는 boundary를 opaque node로 유지하고 호출이 없다고 단정하지 않는다. |

**[PROJECT-HYPOTHESIS] 핵심 원칙:** 동적 패턴은 suppress 대상이 아니라 관찰 품질 feature다. 최종 위험표에는 `dynamic_feature_flags`, `edge_confidence`, `model_coverage`, `unknown_boundary_count`를 보여 주고, 높은 불확실성을 낮은 위험으로 변환하지 않는다.

## 6. Retrieval 관찰력·성능 비교

| 방식 | 강점 | 약점과 비용 | 후보 위치 |
|---|---|---|---|
| **Lexical (exact/token/BM25/trigram)** | **[FACT]** exact identifier, dotted import, exception text, config key, API name을 결정적으로 찾고 index update/delete가 단순하다. FTS5는 prefix/NEAR/BM25/trigram을 제공한다. [SQLite FTS5](https://www.sqlite.org/fts5.html) | rename·동의어·행동 설명과 구현 이름이 다른 경우 recall이 낮다. Python tokenization(`snake_case`, dotted names, operators)을 일반 word tokenizer가 손실할 수 있다. | **최소 기준선.** raw text, symbol name, docstring/comment, config를 별도 field로 색인하고 exact match를 우선한다. |
| **Symbol/reference graph retrieval** | definition→references, import→module, caller/callee 후보, owner/test adjacency를 이용해 lexical seed 주변의 구조적 context를 찾는다. SCIP는 definition/reference interchange를 표준화한다. [SCIP](https://scip-code.org/) | graph recall은 resolver recall보다 높을 수 없다. hub node에서 k-hop 폭발, unresolved dynamic edges, stale graph가 문제다. | **기준선의 제한된 확장.** explicit/resolved edge만 default expansion; heuristic edge는 opt-in evidence로 분리한다. |
| **CFG/dataflow path retrieval** | finding의 possible path와 source/sink/sanitizer 문맥을 제공해 설명력을 높인다. [CodeQL data flow](https://codeql.github.com/docs/codeql-language-guides/analyzing-data-flow-in-python/) | query/model별 고비용, path explosion, spurious call/alias edge가 있다. possible path는 executed path가 아니다. | **risk-class별 실험.** evidence path가 human triage accuracy를 개선할 때만 유지한다. |
| **CPG traversal** | syntax/control/dataflow를 한 traversal에서 조합하고 graph provenance를 표현한다. [Joern CPG](https://docs.joern.io/code-property-graph/) | storage/memory/query complexity와 frontend coupling이 크며 Python incremental update 공개 근거가 부족하다. | **격리 실험.** relational/adjacency baseline보다 diagnostic lift가 있어야 한다. |
| **Vector retrieval** | 자연어 risk 설명과 이름이 다른 코드, 유사 구현, weak lexical overlap을 찾을 가능성이 있다. **[FACT]** CoIR dense models는 평균적으로 BM25보다 높았지만 task별 분산과 latency/index-size trade-off가 컸다. [CoIR](https://aclanthology.org/2025.acl-long.1072.pdf) | embedding model/version drift, chunk boundary, stale embedding, memory, privacy/반출, reproducibility 비용. Similarity는 dependency나 vulnerability 증명이 아니다. | **격리 실험.** 외부 model 결과를 기본 KPI에 합산하지 않고 local/offline 가능성도 같은 기준으로 비교한다. |
| **Graph-guided AI retrieval** | graph seed에서 k-hop context를 LLM에 제공할 수 있다. RepoGraph가 공개 구현 사례다. [RepoGraph](https://arxiv.org/html/2410.14684) | **[FACT]** 공개 평가는 patch resolve/application이며 health risk diagnosis가 아니다. line graph의 call/reference extraction 오류도 남는다. | **실험 전용.** localization gold label과 triage outcome으로 별도 검증한다. |
| **Hybrid fusion** | **[PROJECT-HYPOTHESIS]** exact lexical seed + trusted graph expansion + optional vector rerank가 recall과 evidence traceability를 균형화할 수 있다. CoIR의 task별 winner 차이는 복수 채널 실험 필요성을 지지한다. [CoIR](https://aclanthology.org/2025.acl-long.1072.pdf) | fusion weight가 opaque하고 비용이 늘 수 있다. 채널별 독립 기여를 모르면 weightless complexity다. | **실험 후보.** 동일 candidate budget과 deterministic tie-break로 drop-one-channel ablation을 수행한다. |

## 7. 증분 분석과 변경 영향 설계

### 7.1 증분성의 분해

**[PROJECT-HYPOTHESIS]** `incremental=true` 대신 다음 6개를 별도로 기록한다.

1. `parse_reuse`: unchanged file의 syntax tree 재사용 여부 — Tree-sitter는 edited tree update를, Ruff는 unchanged-file cache를 문서화한다. [Tree-sitter](https://tree-sitter.github.io/tree-sitter/), [Ruff](https://docs.astral.sh/ruff/)
2. `semantic_invalidation`: changed definition/signature가 dependents를 얼마나 정확히 재분석하는지 — mypy daemon은 finer-grained dependency tracking을 제공한다. [mypy daemon](https://mypy.readthedocs.io/en/stable/mypy_daemon.html)
3. `process_persistence`: memory-only인지 disk-persistent인지 — Pyright watch는 memory cache이며 persistent disk cache가 없다는 공식 maintainer 설명이 있다. [Pyright discussion](https://github.com/microsoft/pyright/discussions/4809)
4. `database_overlay`: base facts와 changed-file facts/query intermediates를 결합하는지 — CodeQL overlay가 공개 사례다. [CodeQL overlay](https://docs.github.com/en/code-security/how-tos/find-and-fix-code-vulnerabilities/scan-from-the-command-line/incremental-analysis#overlay-analysis)
5. `report_filtering`: computation을 줄인 것인지 결과만 changed lines로 제한한 것인지 — CodeQL diff-informed는 후자도 포함하며 CI-side filtering이 필요하다. [CodeQL diff-informed](https://docs.github.com/en/code-security/how-tos/find-and-fix-code-vulnerabilities/scan-from-the-command-line/incremental-analysis#diff-informed-analysis)
6. `freshness_proof`: warm result가 clean full rebuild와 동일한지 — **[PROJECT-HYPOTHESIS]** 정기 sampled clean replay hash comparison이 필수다.

### 7.2 Snapshot과 invalidation key

**[PROJECT-HYPOTHESIS]** cache key는 최소 `git tree/object ids + analyzer/version + rule/model pack hash + Python target version + source roots + dependency/stub/lock fingerprint + normalized config + policy mode`다. file rename/delete는 tombstone으로 처리하고, 삭제된 definition의 reverse edges와 findings를 한 transaction에서 제거한다. base와 RC graph를 덮어쓰지 않고 immutable snapshot/overlay로 분리한다.

### 7.3 변경 영향의 안전한 의미

- **[FACT]** Git changed files와 direct/transitive dependents 계산은 실용적인 selection primitive다. [Pants](https://www.pantsbuild.org/stable/docs/using-pants/advanced-target-selection#running-over-changed-files-with---changed-since)
- **[PROJECT-HYPOTHESIS]** impact edge는 `file→module→symbol→reference/call candidate→owned test/service` 순으로 bounded propagation하며 edge kind·depth·confidence·path를 보존한다.
- **[PROJECT-HYPOTHESIS]** changed-only scan은 금지한다. 기준 브랜치의 full inventory와 RC의 incremental update를 만든 뒤 changedness/impact를 ranking feature로 사용한다. 삭제만 있는 diff, unchanged sink로 새 flow가 생긴 경우, config/lock change가 대표 반례다. CodeQL도 deletion-only diff에 sentinel/특수 처리를 요구하며 diff-informed alert filtering을 별도 단계로 설명한다. [CodeQL incremental special cases](https://docs.github.com/en/code-security/how-tos/find-and-fix-code-vulnerabilities/scan-from-the-command-line/incremental-analysis#step-1-identify-the-diff-ranges)
- **[UNSUPPORTED]** “transitive dependent이면 실제 장애”, “graph에 없으면 영향 없음”이라는 주장은 기각한다. Pants도 third-party transitive dependency/lockfile caveat를 명시한다. [Pants caveat](https://www.pantsbuild.org/stable/docs/using-pants/advanced-target-selection#running-over-changed-files-with---changed-since)

## 8. 후보군과 결정 gate

### 8.1 최소 충분 기준선 후보(MSB)

제품을 미리 정하지 않고 capability contract로 정의한다.

| capability | 최소 계약 | 구현 후보(미선정) | 승격 전 gate |
|---|---|---|---|
| Source inventory / parse | target-version-aware syntax, encoding/error 기록, source span, no target import | CPython `ast`+`symtable`; Tree-sitter 대조 | supported Python syntax fixture parse completeness, cold/warm throughput, error recovery fidelity |
| Fast deterministic diagnostics | syntax/name/import/style/known bug pattern을 machine-readable provenance와 함께 출력, fix 비활성 | Ruff 또는 동급 공개 linter | project ruleset coverage, false-positive adjudication, cache freshness; vendor speed 수치 사용 금지 |
| Type evidence | diagnostics + `Any`/untyped/stub/model coverage + definition/type provenance | Pyright, mypy를 동일 fixture로 비교 | typedness strata별 precision/recall, dynamic framework coverage, cold/warm memory/time, config safety |
| Symbol/import graph | explicit definitions, scope, literal import, resolved references; unresolved 보존 | `ast/symtable` normalized graph; SCIP-style export/index 후보 | gold definition/reference/import edge P/R, namespace/relative import/rename/delete fixture, version support |
| Lexical retrieval | exact + fielded BM25/trigram, incremental update/delete, deterministic rank | SQLite FTS5 또는 동급 embedded index | gold evidence Recall@k/nDCG, identifier tokenizer, update latency/storage/integrity |
| Change overlay | merge-base-correct diff, immutable base/RC snapshots, bounded reverse impact paths | Git object IDs + normalized adjacency store | merge/rebase/rename/delete/config/lock fixtures, clean-vs-warm parity, impact recall/precision |
| Risk output | finding과 observation 분리, evidence URL/span/path, confidence, limitations, base/RC state | 제품 중립 schema | reviewer가 원문까지 재현 가능, unsupported edge가 certainty로 보이지 않음 |

**[PROJECT-HYPOTHESIS] MSB의 기본 graph edge:** `contains`, `defines`, `imports-literal`, `references-resolved`, `inherits-resolved`, `decorates-syntax`, `calls-direct/resolved-candidate`, `changed-from`, `depends-on-candidate`. 각 edge에 `producer`, `version`, `snapshot`, `source span`, `resolution basis`, `confidence`, `unknown reason`을 둔다. CFG/dataflow edge를 처음부터 모두 넣지 않는다.

### 8.2 격리 실험 후보

| 후보 | 조사 근거 | 왜 기본선이 아닌가 | 필요 대조 |
|---|---|---|---|
| Function-scoped CFG | CodeQL이 Python CFG/reachability를 제공한다. [문서](https://codeql.github.com/docs/codeql-language-guides/analyzing-control-flow-in-python/) | 모든 health finding에 필요하지 않고 frontend fidelity/cost가 있다. | MSB vs MSB+CFG: unreachable/resource/exception gold findings, latency/memory |
| Local/global dataflow | CodeQL은 local/global/taint API와 비용 차이를 문서화한다. [문서](https://codeql.github.com/docs/codeql-language-guides/analyzing-data-flow-in-python/) | model coverage와 global cost; PyFlow real-world timeout tail. [PyFlow](https://arxiv.org/html/2608.07026v1#S5.SS2) | risk class별 MSB vs +local vs +global; path validity, P/R, timeout/partial ratio |
| CodeQL overlay | 최신 공식 changed-file DB/query cache 재사용. [문서](https://docs.github.com/en/code-security/how-tos/find-and-fix-code-vulnerabilities/scan-from-the-command-line/incremental-analysis) | vendor claim, license/운영 제약, `build-mode:none`, project workload 미검증 | clean DB vs overlay result parity, cold/warm cost, deletion/rename/config invalidation |
| Joern Python CPG | Python frontend와 combined graph query가 존재한다. [Python](https://docs.joern.io/frontends/python/), [CPG](https://docs.joern.io/code-property-graph/) | Python semantic fidelity·incremental rebuild·memory의 project 증거 없음 | normalized adjacency/CodeQL 대비 동일 query P/R, build/update/query cost |
| JARVIS/application-centered call graph | public Python call-graph scale/precision 연구. [JARVIS](https://arxiv.org/html/2305.05949) | prototype/preprint, entry point 필요, benchmark 규모/feature 분포 불일치 | project frameworks/entry points가 포함된 gold edge set; full vs application-centered recall/cost |
| PyFlow/IFDS | 최신 open-source Python interprocedural framework. [PyFlow](https://arxiv.org/html/2608.07026v1) | preprint, 600초 timeout 45/206, current project 미검증 | selected risk classes only, hard budget/partial status, CodeQL/local baseline 비교 |
| Dense vector retrieval | CoIR에서 semantic retrieval 가능성과 비용 trade-off. [CoIR](https://aclanthology.org/2025.acl-long.1072.pdf) | 건강 진단/localization gold가 아니고 privacy/model drift 비용 | lexical vs vector vs fusion, same candidate/token/latency budget, offline reproducibility |
| Graph-guided retrieval | RepoGraph 공개 method. [RepoGraph](https://arxiv.org/html/2410.14684) | patch success만 있고 diagnostic evidence 없음 | trusted-edge graph만 사용한 finding localization Recall@k와 triage time |
| LLM type hypotheses | 2025 study에서 type inference 가능성. [study](https://arxiv.org/html/2410.00603) | probabilistic, model/version/data leakage, core type correctness 보장 없음 | static types vs +LLM hypothesis; human-verified precision/calibration, core graph에는 미승격 |

## 9. 시스템 설계에 주는 함의

### 9.1 Observation과 risk를 분리한다

**[PROJECT-HYPOTHESIS]** analyzer 출력은 곧 risk가 아니다. 저장 계층을 다음처럼 분리한다.

1. `SourceSnapshot`: immutable base/RC identity와 configuration fingerprint.
2. `Observation`: AST/symbol/type/CFG/dataflow/lexical match 등 사실, producer와 source span.
3. `Relation`: direction, kind, resolution basis, confidence, path, dynamic flags.
4. `Finding`: rule/model이 observations를 결합한 검증 가능 주장.
5. `RiskPriority`: severity × evidence confidence × changed/impact × ownership/criticality × 검증 상태. 공식은 후속 평가 티켓에서 보정한다.

Graph degree, PageRank, embedding similarity, changed depth는 단독 risk가 아니라 feature다. 한 analyzer의 alert count가 많은 것을 관찰력이 높다고 간주하지 않는다. ICSE 2026 결과는 여러 SAST를 합쳐도 real-world recall이 완전하지 않았음을 보여 준다. [ICSE study](https://conf.researchr.org/details/icse-2026/icse-2026-research-track/30/An-Empirical-Study-on-Static-Application-Security-Testing-SAST-Tools-for-Python)

### 9.2 최종 위험 우선순위표의 최소 열

**[PROJECT-HYPOTHESIS]** `risk_id`, base/RC state(new/persisting/resolved), location, risk class, severity, evidence summary, source URLs/spans, producer/version/ruleset, relation path, confidence/calibration bucket, dynamic limitation flags, model/stub coverage, change/impact path, owner/critical-path flag, static/dynamic verification status, timeout/partial/stale flags, reviewer disposition를 포함한다. `unknown`을 빈칸이나 0으로 직렬화하지 않는다.

### 9.3 정책 안전성

- **[FACT]** mypy는 config에 지정된 Python plugin module을 import한다. [mypy plugin docs](https://mypy.readthedocs.io/en/stable/extending_mypy.html#configuring-mypy-to-use-plugins)
- **[FACT]** 공개 scip-python README는 environment discovery에 `pip`를 호출하며 explicit environment file로 이를 건너뛸 수 있다고 설명한다. [scip-python](https://github.com/sourcegraph/scip-python)
- **[PROJECT-HYPOTHESIS]** 자동 정적 경로는 target import, plugin loading, build hook, package installer, network를 금지한 read-only sandbox에서 실행한다. repo config를 그대로 신뢰하지 않고 effective config와 disabled plugin/model을 evidence에 남긴다. analyzer 자체 실행은 허용된 정적 읽기이지만 대상 코드 실행 가능성이 생기는 option은 정책 승인 경로로 분리한다.

### 9.4 핵심 경로 기여 입증

**[PROJECT-HYPOTHESIS]** 동일 snapshot, 동일 gold findings, 동일 candidate/reviewer budget에서 다음 누적·drop-one 비교를 한다.

`L0 lexical/AST → L1 +symbol/import → L2 +type → L3 +change-impact → L4 +CFG/local-flow → L5 +global-flow/CPG → E1 +vector → E2 +graph-guided AI`

각 층의 독립 기여는 risk-class별 precision, recall, calibrated confidence/Brier score, evidence-span Recall@k, reviewer triage time/agreement, cold/warm p50/p95 wall time, peak RSS, index size, invalidated files/symbols, timeout/partial/stale ratio로 판단한다. patch 생성률·patch apply·test pass는 진단 성과를 대신하지 않는다.

## 10. 후속 검증 프로토콜

모든 대상 코드 실행·test·profiler·dynamic trace는 정책 승인 후 별도 실행 티켓에서 수행한다. static parser/indexer 비교는 자동 정적 경로에서 가능하지만 현재 연구 티켓에서는 실행하지 않았다.

### STG-01 — edge 정확도

- 공개 micro suites([PyCG artifact](https://github.com/vitsalis/PyCG), [SWARM-CG artifact](https://github.com/secure-software-engineering/SWARM-CG)) + 익명 실제 framework strata로 definition/reference/import/call gold edges를 수작업 이중 판정한다.
- `precision`, `recall`, unresolved rate, over-approx fan-out, dynamic-feature별 결과를 낸다.
- dynamic trace는 승인 후 보조 positive evidence로만 사용한다. 실행되지 않은 feasible edge가 있으므로 trace를 완전한 negative ground truth로 쓰지 않는다.

### STG-02 — 진단 독립 기여

- risk class마다 MSB, +type, +CFG, +local flow, +global flow, +CPG를 같은 snapshot/rules/budget로 대조한다.
- finding-level gold label과 evidence-path validity를 평가한다.
- aggregate 수치 외에 typing density, framework, DI/reflection, native boundary, repository size strata를 보고한다.

### INC-01 — 증분 정확성·성능

- edit 종류: body-only, public signature, import, decorator, model/config, lock/stub, rename, delete, file move, base rebase/merge.
- 매 단계 warm incremental output과 clean full rebuild를 canonicalize해 equality/difference를 판정한다.
- `invalidated files/symbols`, update/query time, peak RSS, cache bytes, stale/missing/extra observations를 기록한다.
- vendor의 “up to N×” 대신 동일 hardware의 cold/warm p50/p95와 worst fan-out을 사용한다.

### CIA-01 — 변경 영향

- historical PR에서 실제 수정 후 함께 바뀐 파일, reviewer-confirmed impacted components, 승인 후 failed tests/incidents를 서로 다른 label로 둔다.
- direct diff, reverse import, reverse symbol/reference, call candidate, ownership graph를 한 층씩 추가한다.
- top-k impact recall/precision, path explanation acceptance, fan-out를 측정한다. co-change는 causal impact가 아니므로 독립 label로 둔다.

### RET-01 — retrieval

- 질의: exact symbol, natural-language risk, error message, config-driven behavior, dynamic registration, similar implementation.
- lexical, graph, vector, lexical+graph, lexical+vector, three-way fusion을 동일 `k`, same downstream context/token budget로 비교한다.
- evidence-span Recall@k, MRR/nDCG, no-answer precision, update latency, index size, model cost/privacy class를 측정한다.
- CoIR 수치를 project KPI로 재사용하지 않는다. [CoIR limitation](https://aclanthology.org/2025.acl-long.1072.pdf)

### DYN-01 — 동적 기능 envelope

- fixture: literal/computed `getattr`, `setattr`, `import_module`, custom importer, entry point, DI provider, decorator/metaclass synthesis, monkey patch, `eval/exec`, C-extension stub/no-stub.
- edge를 `resolved`, `modeled`, `heuristic`, `unknown`, 승인 후 `runtime-observed`로 판정한다.
- 목표 수치 임계값은 실제 저장소 분포와 reviewer capacity가 정해진 후 평가 티켓이 결정한다. 현재 임의 threshold는 **[UNSUPPORTED]**다.

## 11. 새 아이디어

1. **Uncertainty ledger — [PROJECT-HYPOTHESIS].** snapshot마다 dynamic imports, computed attrs, `Any`, missing stubs/models, opaque native boundaries, partial/timeout을 수량화해 risk table 옆에 “관찰 불가능성”을 함께 제시한다.
2. **두 edge lane — [PROJECT-HYPOTHESIS].** `must/resolved`와 `may/modeled-or-heuristic`를 물리적으로 분리한다. 기본 ranking은 must lane을 우선하고 may lane은 recall 보강과 limitation 설명에 쓴다.
3. **Evidence-first retrieval — [PROJECT-HYPOTHESIS].** vector가 finding을 만들지 않고 lexical/symbol finding의 근거 후보만 확장하게 한다. 최종 finding에는 반드시 deterministic source span 또는 graph path가 있어야 한다.
4. **Entry-point cone budgeting — [PROJECT-HYPOTHESIS].** JARVIS의 application-centered 결과를 직접 채택하지 않고, API routes/workers/CLI/jobs별 reachable cone과 전체 inventory를 병행한다. cone 밖을 “안전”으로 표시하지 않는다. [JARVIS](https://arxiv.org/html/2305.05949)
5. **Clean-replay sentinel — [PROJECT-HYPOTHESIS].** 일정 비율의 RC를 clean rebuild해 overlay 결과 hash와 비교하고 stale-edge rate를 운영 지표로 만든다. CodeQL overlay 같은 persistent cache도 동일 검사를 통과해야 한다. [CodeQL overlay](https://docs.github.com/en/code-security/how-tos/find-and-fix-code-vulnerabilities/scan-from-the-command-line/incremental-analysis#overlay-analysis)
6. **Dynamic hotspot prioritization — [PROJECT-HYPOTHESIS].** unresolved graph 영역을 낮은 confidence로만 내리는 대신 critical path/changedness와 결합해 정책 승인형 runtime verification 후보로 올린다.
7. **Counterfactual graph ablation — [PROJECT-HYPOTHESIS].** 특정 edge family를 제거했을 때 finding/evidence/triage가 변하지 않으면 그 edge extractor를 삭제 후보로 삼아 CPG의 weightless complexity를 방지한다.

## 12. 기각 또는 보류 아이디어

| 아이디어 | 상태 | 이유 |
|---|---|---|
| “처음부터 완전한 CPG를 중앙 truth로 구축” | **보류** | **[UNSUPPORTED]** Python frontend/edge fidelity, incremental rebuild, memory, diagnostic lift가 프로젝트에서 검증되지 않았다. CPG는 representation이지 truth guarantee가 아니다. [Joern](https://docs.joern.io/code-property-graph/) |
| “vector search가 lexical을 대체” | **기각** | **[FACT]** CoIR도 task별 단일 winner가 없고 BM25가 일부 task에서 강했다. exact identifier/config provenance를 vector similarity로 대체할 수 없다. [CoIR Table 3](https://aclanthology.org/2025.acl-long.1072.pdf) |
| “LLM이 call/type graph 빈칸을 채우면 core edge로 채택” | **기각** | **[FACT]** 2025 공개 연구에서 Python call graph는 traditional PyCG가 LLM보다 우수했고 LLM은 completeness/soundness에 어려움이 있었다. [LLM call-graph study](https://arxiv.org/html/2410.00603) |
| “RC에서는 changed files만 분석” | **기각** | unchanged dependent/sink, deletion-only, config/lock change를 놓친다. diff-informed reporting과 overlay computation은 구분해야 한다. [CodeQL incremental](https://docs.github.com/en/code-security/how-tos/find-and-fix-code-vulnerabilities/scan-from-the-command-line/incremental-analysis) |
| “동적 Python 전체에 sound and precise whole-program graph 보장” | **기각** | gradual typing/`Any`, reflection/import hooks/exec와 recent real-world tool recall이 반증한다. [Typing spec](https://typing.python.org/en/latest/spec/concepts.html), [ICSE 2026](https://conf.researchr.org/details/icse-2026/icse-2026-research-track/30/An-Empirical-Study-on-Static-Application-Security-Testing-SAST-Tools-for-Python) |
| “정적 해석 중 대상 module을 import해 확정” | **기각** | 정책상 대상 실행이며 import side effect가 있다. static path는 source/metadata/stub만 읽고 runtime 확인은 승인 경로다. [import system](https://docs.python.org/3/library/importlib.html) |
| “mypy/Pylint 등 repo plugin을 그대로 자동 실행” | **기각** | mypy는 configured Python plugin을 import한다. static tool이라는 이름만으로 no-execution이 보장되지 않는다. [mypy plugins](https://mypy.readthedocs.io/en/stable/extending_mypy.html#configuring-mypy-to-use-plugins) |
| “RepoGraph/SWE-bench patch success를 진단 성과로 인정” | **기각** | 공개 metric은 patch resolve/apply/cost이며 health finding precision/recall이 아니다. [RepoGraph](https://arxiv.org/html/2410.14684#S4.SS1) |
| “PyFlow/새 type checker를 최신이므로 기본 채택” | **보류** | PyFlow는 최신 preprint이고 timeout tail이 크다. 신규 후보의 vendor benchmark는 project evidence가 아니다. [PyFlow](https://arxiv.org/html/2608.07026v1#S5.SS2) |
| “여러 scanner의 union이면 충분” | **기각** | ICSE 2026 study에서 8 tools union도 real-world 취약점의 66.7%였다. [ICSE 2026](https://conf.researchr.org/details/icse-2026/icse-2026-research-track/30/An-Empirical-Study-on-Static-Application-Security-Testing-SAST-Tools-for-Python) |

## 13. 미해결 질문

1. 실제 저장소의 Python version, LOC/file/symbol 수, monorepo/source-root topology, generated/vendor/notebook 비율은 무엇인가?
2. typing coverage(`Any`, missing import/stub, strictness), framework(FastAPI/Django/Flask 등), DI/decorator/metaclass, async/generator, multiprocess, native extension 분포는 무엇인가?
3. 기준 브랜치와 RC의 merge-base/rebase/merge queue/force-push 정책, cache retention과 clean replay 주기는 무엇인가?
4. “핵심 경로”의 공식 entry points/routes/jobs/services와 ownership/test mapping은 어디에서 정적으로 읽을 수 있는가?
5. 필요한 risk classes 중 어느 것이 AST/symbol/type만으로 충분하고 어느 것이 CFG/dataflow를 실제로 필요로 하는가?
6. type checker/linter의 repo config와 plugin을 disable하면 framework 이해도가 얼마나 손실되며, 정책 승인 sandbox에서 허용할 model/plugin은 무엇인가?
7. CodeQL/Joern/기타 engine의 license, air-gap 설치, source 반출, cache artifact 보존 정책은 수용 가능한가?
8. 익명 실제 gold labels의 수, reviewer 수와 숙련도, disagreement resolution, dynamic trace 승인 범위는 무엇인가?
9. risk table이 허용할 latency/RSS/storage, warm RC SLA, full baseline SLA, timeout/partial 결과 정책은 무엇인가?
10. vector 실험에서 허용되는 local model, embedding 반출, model pinning, 재현 기간, 동일 비용 회계는 무엇인가?
11. CPG를 쓰지 않고 normalized adjacency/relational facts로 필요한 query를 모두 충족하는지, graph DB가 실제 독립 기여를 보이는가?
12. Python 3.14+ grammar/type semantics 변화 시 parser/type/index migration과 base/RC comparability를 어떻게 보장할 것인가?

## 14. 출처 목록

### 공식 언어·프로토콜·도구 문서

- Python Software Foundation, [`ast` — Abstract syntax trees](https://docs.python.org/3/library/ast.html), Python 3.14.7 문서.
- Python Software Foundation, [`symtable` — Access to the compiler’s symbol tables](https://docs.python.org/3/library/symtable.html), Python 3.14.7 문서.
- Python typing specification, [Type system concepts](https://typing.python.org/en/latest/spec/concepts.html).
- Python Software Foundation, [`importlib`](https://docs.python.org/3/library/importlib.html), [`importlib.metadata` entry points](https://docs.python.org/3/library/importlib.metadata.html#entry-points), [data model](https://docs.python.org/3/reference/datamodel.html#customizing-attribute-access), [built-in functions](https://docs.python.org/3/library/functions.html), [Extending Python with C or C++](https://docs.python.org/3/extending/extending.html).
- Tree-sitter, [Introduction and incremental parser goals](https://tree-sitter.github.io/tree-sitter/).
- Ruff, [official documentation](https://docs.astral.sh/ruff/) and [settings](https://docs.astral.sh/ruff/settings/).
- mypy, [daemon](https://mypy.readthedocs.io/en/stable/mypy_daemon.html), [additional features](https://mypy.readthedocs.io/en/stable/additional_features.html), [plugins](https://mypy.readthedocs.io/en/stable/extending_mypy.html).
- Microsoft Pyright, [maintainer discussion on in-memory watch cache and no disk cache](https://github.com/microsoft/pyright/discussions/4809).
- GitHub CodeQL, [Python control flow](https://codeql.github.com/docs/codeql-language-guides/analyzing-control-flow-in-python/), [Python data flow](https://codeql.github.com/docs/codeql-language-guides/analyzing-data-flow-in-python/), [Python library](https://codeql.github.com/docs/codeql-language-guides/codeql-library-for-python/), [incremental CLI analysis](https://docs.github.com/en/code-security/how-tos/find-and-fix-code-vulnerabilities/scan-from-the-command-line/incremental-analysis).
- Joern, [Code Property Graph](https://docs.joern.io/code-property-graph/) and [Python frontend](https://docs.joern.io/frontends/python/).
- SCIP, [protocol and Python indexer link](https://scip-code.org/); Sourcegraph, [scip-python public repository/README](https://github.com/sourcegraph/scip-python).
- Pants 2.33, [Advanced target selection](https://www.pantsbuild.org/stable/docs/using-pants/advanced-target-selection).
- SQLite, [FTS5 extension](https://www.sqlite.org/fts5.html).

### 논문·공개 재현 자료

- Huang et al., [*JARVIS: Scalable and Precise Application-Centered Call Graph Construction for Python*](https://arxiv.org/html/2305.05949), arXiv v5, 2024; [artifact](https://github.com/liyuesolo/jarvis).
- Gu, Yan, Yao, [*PyFlow: An Inter-procedural Static Analysis Framework for Python*](https://arxiv.org/html/2608.07026v1), arXiv v1, 2026; [artifact](https://github.com/ZJU-PL/pyflow).
- Liu et al., [*An Empirical Study on Static Application Security Testing (SAST) Tools for Python*](https://conf.researchr.org/details/icse-2026/icse-2026-research-track/30/An-Empirical-Study-on-Static-Application-Security-Testing-SAST-Tools-for-Python), ICSE 2026 Distinguished Paper; [PySASTBench artifact](https://github.com/Victor725/PySASTBench).
- Li et al., [*CoIR: A Comprehensive Benchmark for Code Information Retrieval Models*](https://aclanthology.org/2025.acl-long.1072/), ACL 2025, DOI 10.18653/v1/2025.acl-long.1072; [artifact](https://github.com/CoIR-team/coir).
- Ouyang et al., [*RepoGraph: Enhancing AI Software Engineering with Repository-level Code Graph*](https://arxiv.org/html/2410.14684), arXiv v2, 2025; [artifact](https://github.com/ozyyshr/RepoGraph).
- Venkatesh et al., [*An Empirical Study of Large Language Models for Type and Call Graph Analysis in Python and JavaScript*](https://arxiv.org/html/2410.00603), arXiv v2, 2025; [SWARM-CG](https://github.com/secure-software-engineering/SWARM-CG), [TypeEvalPy](https://github.com/secure-software-engineering/TypeEvalPy), [Zenodo outputs](https://zenodo.org/records/15045642).
- Liu et al., [*Scalable Defect Detection via Traversal on Code Graph*](https://arxiv.org/html/2406.08098v1), arXiv v1, 2024. 이 자료의 prototype/vendor-comparison 수치는 프로젝트 성능 근거로 사용하지 않았다.
- Salis et al., [*PyCG: Practical Call Graph Generation in Python*](https://dl.acm.org/doi/10.1109/ICSE43902.2021.00146), ICSE 2021; [public micro-benchmark/tool artifact](https://github.com/vitsalis/PyCG). 최신 연구의 비교 기준이어서 포함했다.
