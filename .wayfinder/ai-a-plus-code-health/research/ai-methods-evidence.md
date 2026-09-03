# AI 코드 진단 최신 기법 근거 조사

- 조사 기준일: 2026-08-29
- 질문: graph-aware retrieval, execution-guided diagnosis, verifier/critic, learned tool routing, uncertainty calibration/conformal methods, test-time compute, temporal/change-risk 중 **Python 백엔드의 결함·성능 진단과 위험 우선순위화**에 재현 가능한 개선 근거가 있는가?
- 프로젝트 상태: **[FACT:PROJECT]** 이 저장소는 아직 설계 단계이며 구현·벤치마크·운영 실행 증적이 없다. 따라서 아래 외부 결과는 후보 선정 근거이지 프로젝트 성능 증거가 아니다. 프로젝트는 정적 읽기·그래프 탐색만 자동 허용하고, import·테스트·benchmark·profiler 등 실행은 정책 승인 뒤에만 허용한다([프로젝트 지도](../map.md)).
- 산출물의 목적: 특정 제품·모델·graph DB를 채택하지 않고 후속 결정 티켓이 비교 실험과 승격 기준을 정할 수 있게 한다.

## 1. 판정 표기와 증거 경계

- **[FACT]**: 논문·공식 문서가 실제로 측정하거나 명시한 내용. 모든 외부 FACT에는 원문 URL을 붙였다.
- **[FACT:PROJECT]**: 현재 티켓·지도에 명시된 프로젝트 제약 또는 상태. 외부 성능 주장과 분리한다.
- **[PROJECT-HYPOTHESIS]**: 외부 근거에서 이 프로젝트에 맞게 도출한 설계·실험 후보. 프로젝트 대조 실험 전에는 성능 사실이 아니다.
- **[UNSUPPORTED]**: 현재 근거로 주장하면 안 되거나, 다른 과제의 수치를 진단 성과로 잘못 전이한 주장.

용어를 다음처럼 엄격히 구분한다.

1. **검출(detection)**: 결함 또는 성능 위험이 존재하는가.
2. **위치화(localization)**: 어느 파일·함수·라인이 관련 있는가.
3. **진단(diagnosis)**: 관찰된 증상과 코드 경로를 연결해 원인 가설을 제시하고, 증거로 지지·반증하는가.
4. **우선순위화(prioritization)**: 제한된 검토·테스트·프로파일링 예산에서 무엇을 먼저 조사해야 하는가.
5. **패치 해결(issue resolution)**: 생성한 패치를 적용하고 평가 테스트를 통과하는가. SWE-bench 공식 평가도 “패치 적용 후 repository tests 실행”으로 정의된다([공식 평가 가이드](https://www.swebench.com/SWE-bench/guides/evaluation/)). 이것만으로 1–4의 품질은 입증되지 않는다.

## 2. 요약

### 2.1 근거가 가장 직접적인 후보

- **[FACT] Graph-aware retrieval은 Python 저장소의 위치화에서 직접 증거가 있다.** ACL 2025 LocAgent는 Python AST로 directory/file/class/function 노드와 contain/import/invoke/inherit 관계를 만들고, SWE-bench Lite 274건에서 graph traversal을 제거하면 function Acc@10이 71.53%에서 66.06%로, full graph를 contain-only로 줄이면 66.42%로 하락했다. SearchEntity/BM25 제거의 하락은 더 컸으므로 graph만 단독 채택할 근거가 아니라 **lexical/sparse search + typed graph traversal**의 결합 근거다([ACL 원문](https://aclanthology.org/2025.acl-long.426/), [실험·ablation](https://arxiv.org/html/2503.09089v2#S5.SS6)).
- **[FACT] Execution-guided functional fault localization은 직접 증거가 있다.** FSE 2024 AutoFL은 실패 테스트 coverage와 covered code를 준비하고 LLM이 repository 함수를 탐색하게 했다. 798개 Java/Python 실제 버그에서 평가했으며, BugsInPy에서 Ochiai 대비 method Acc@1 상대 개선은 GPT-3.5 166.7%, GPT-4 233.3%였다. 그러나 개별 설명 중 원인을 정확히 기술한 비율은 20.0%, 부정확한 진술 포함은 26.3%, 유용 판정은 8.0%였다([FSE 원문](https://arxiv.org/html/2308.05487#S5)). 즉 위치화 개선과 설명 정확성은 별도 KPI다.
- **[FACT] Performance diagnosis에는 differential profiling + execution path가 가장 직접적인 최신 근거다.** ASE 2026 게재 예정 EffiHolmes는 5개 Python data-science 저장소의 재현 가능한 실제 성능 이슈 140건에서 default/scaled 실행쌍의 trace를 비교하고 critical call paths를 추출했다. GPT-5.1 ablation에서 path를 제거하면 function Acc@5가 81.43%에서 38.57%로 42.86%p 하락했다. 다만 정답은 원인 설명이 아니라 merged PR의 fix location이며, workload 생성·profiler 실행이 필요하다([ASE/arXiv 원문](https://arxiv.org/html/2608.03558v1#S5.SS2), [dataset](https://arxiv.org/html/2608.03558v1#S4.SS2)).
- **[FACT] Temporal/change-risk는 “어떤 변경을 먼저 볼지”에는 직접 증거가 있으나 root-cause 진단 근거는 아니다.** Journal of Systems and Software의 JIT-BiCC는 21개 Java 프로젝트 27,319 commits에서 diff/commit message의 semantic representation과 14개 change/history/experience 특성을 결합해 F1 0.478, AUC 0.887을 보였고 가장 강한 비교군 JIT-Fine은 0.431/0.881이었다. 특성에는 change diffusion/entropy, AGE, unique changes, developer/recent/subsystem experience가 포함된다([원문](https://arxiv.org/html/2410.12107v1#S5.SS1), [출판 DOI](https://doi.org/10.1016/j.jss.2024.112253)). Java 결과를 Python 또는 정기 건강검진에 그대로 전이하는 것은 **[UNSUPPORTED]**다.
- **[FACT] Conformal prediction은 JIT 결함 예측의 오경보 필터링에 직접 적용됐지만 유용한 확정 집합이 작았다.** MSR 2024 연구는 DeepJIT/CC2Vec와 QT/OpenStack에서 95% correctness를 보장할 수 있었던 예측이 각각 27%와 9%뿐이라고 보고했다. 반면 실험 조건에서 false negative/positive를 상당수 필터링했다([IEEE 원문](https://ieeexplore.ieee.org/document/10555854)). 따라서 CP는 “모든 행에 95% 신뢰도”를 붙이는 장치가 아니라 **확정 가능한 일부와 abstain/검토 대상을 나누는 장치**다.

### 2.2 아직 간접 근거뿐인 후보

- **[FACT] Critic/verifier:** CriticGPT는 LLM이 만든 짧은 Python 답변의 자연 발생 오류에서 model critique가 human critique보다 63% 선호됐고, critic 지원 human team은 더 포괄적이었다. 그러나 논문 스스로 multi-file/repository navigation을 지원하지 않고 hallucinated bug/nitpick의 절대 비율이 높다고 제한한다([원문](https://arxiv.org/html/2407.00215v1#S5)). 대규모 기존 Python repository의 진단 정확도 근거로 전이할 수 없다.
- **[FACT] Learned tool routing:** ICLR 2025 ToolGen은 일반 tool retrieval에서 3개 multi-domain 구간의 NDCG@1이 87.67/83.46/79.00으로 ToolRetriever의 72.31/64.54/52.00보다 높았고 constrained decoding은 nonexistent-tool 생성을 막았다. 그러나 code diagnosis, policy approval, profiler 선택, 위험 우선순위를 측정하지 않았다([ICLR 원문](https://arxiv.org/html/2410.03439v3#S4)).
- **[FACT] Test-time compute(TTC):** 2025 SWE-Reasoner preprint는 SWE-bench Verified에서 32B model의 내부 TTC issue resolution 37.6%, 외부 budget=8 결합 46.0%를 보고했고, 내부 ablation에서 function localization은 full 54.49% 대 LongCoT/rejection 모두 제거 47.25%였다. 그러나 외부 budget 분석은 100건 표본이었고 최고 난도에서 budget 증가가 성능을 조금 낮췄으며 execution-only verifier도 제한된 재현/coverage의 false positive 때문에 budget=8에서 하락했다([원문](https://arxiv.org/html/2503.23803v1#S3)). 이는 고정 N회 샘플링의 기본 채택이 아니라 제한된 실험 근거다.
- **[FACT] RepoGraph:** repository graph plug-in은 SWE-bench Lite의 **패치 resolve rate**를 RAG +2.66%p, Agentless +2.34%p 개선했지만 주된 endpoint는 패치 통과율이다. generated patch의 edit location coverage도 보고했지만 독립적인 진단·원인·우선순위 benchmark는 아니다([원문](https://arxiv.org/html/2410.14684v2#S4.SS2)).

### 2.3 결론

- **기본 경로 후보:** 정적 lexical/symbol retrieval + typed static graph + baseline→RC graph/diff 변화량 + 투명한 change-risk components + 기계적 evidence verifier + abstention. 정적 자동 경로에서도 모델 결론은 “검증됨”이 아니라 증거 상태에 따라 `정적 근거 확인`, `가설`, `보류`로 구분한다.
- **승인 후 기본 동적 경로 후보:** 기존 실패 재현/테스트 coverage/stack·trace를 graph에 결합한 execution-guided localization; 성능 이슈는 사전 정의된 workload pair의 differential profiling과 causal path 추적.
- **격리 실험 후보:** learned router, learned semantic change-risk model, trained critic/reward model, conformal/non-exchangeable calibration, multi-sample TTC, LLM-generated workload/test.
- **[UNSUPPORTED]** 특정 graph DB, 특정 LLM, 특정 agent framework, 특정 profiler를 지금 채택하는 결론은 없다.

## 3. 근거 표

| 기법 | 증거 직접성 | 실제 측정과 결과 | 비용·실패 조건 | 이 프로젝트로 전이 가능한 범위 | 후보 경로 | 원문 |
|---|---|---|---|---|---|---|
| Typed graph + sparse retrieval (LocAgent, ACL 2025) | **직접: Python code localization** | SWE-bench Lite 274건. full 7B setting: file Acc@5 88.32%, function Acc@10 71.53%; traversal 제거 시 86.13/66.06, contain-only 시 86.50/66.42. Loc-Bench는 bug 242, feature 150, security 29, performance 139로 560건 구성 | AST가 resolve하지 못하는 dynamic dispatch/reflection, graph stale 여부, multi-hop token 비용. 모델·tool·BM25도 함께 바뀌므로 graph 단독 효과는 ablation 범위로 한정 | 정적 graph 및 관련 code context 후보. graph와 lexical baseline을 같이 유지 | **기본 정적 후보** | [ACL](https://aclanthology.org/2025.acl-long.426/), [HTML](https://arxiv.org/html/2503.09089v2#S5.SS6) |
| RepoGraph (2024 preprint) | **간접: patch resolution** | SWE-bench Lite에서 RAG resolve +2.66%p, Agentless +2.34%p; patch-derived file/function/line edit coverage도 측정 | agent integration은 AutoCodeRover +$0.13, SWE-agent +$0.18/example; repeated graph calls가 prompt context를 폭증시킬 수 있음 | graph context가 수리 agent에 도움이 될 가능성. 진단 KPI로는 재시험 필요 | 보조 근거 | [원문](https://arxiv.org/html/2410.14684v2#S4.SS2) |
| AutoFL (FSE 2024) | **직접: functional fault localization**, 설명 평가는 별도 | 798 bugs. BugsInPy method Acc@1 상대 개선 166.7%/233.3% vs Ochiai; confidence와 Precision@1 Spearman 0.52. 개별 설명 accurate 20.0%, imprecise 26.3%, useful 8.0% | BugsInPy 5-run 평균 total 197.33s. 20 interactions는 context overflow로 성능이 절반이 됨. helper-heavy tests, broad scope, long methods, logical error가 실패 요인 | 정책 승인 뒤 failing test/coverage/trace를 쓰는 localization. 설명은 반드시 별도 verifier·human 평가 | **승인 후 동적 후보** | [원문](https://arxiv.org/html/2308.05487#S5) |
| EffiHolmes (ASE 2026, 게재 예정) | **직접: Python performance fix localization** | 재현·speedup 확인된 140 issues. GPT-5.1 full function Acc@5 81.43%; execution paths 제거 38.57%. qwen3-4b는 strongest baseline 대비 function Acc@5 +15.00%p | baseline/scaled pair 생성·최대 5 retry, full tracing, Linux 128 CPU/8 A6000 동시 실행 환경. issue-specific scale semantics가 틀릴 수 있음. top-1 이득은 일부 setting에서 작거나 0 | profiler 승인 시 differential trace → compressed critical path → upstream control candidate 방식 | **승인 후 성능 실험**, 재현 뒤 승격 | [원문](https://arxiv.org/html/2608.03558v1#S5), [DOI](https://doi.org/10.1145/3832783.3834353) |
| CriticGPT (2024 preprint) | **직접: LLM code snippet critique**, repository에는 간접 | 자연 발생 LLM errors에서 model critique가 human critique보다 63% 선호. FSBS는 28 samples/input으로 comprehensiveness–hallucination Pareto 조절 | short snippet, LLM-written code, no multi-file/navigation. hallucinated bugs/nitpicks가 human보다 높음. critic bias 가능 | 근거가 주어진 finding의 반대 검토·누락 탐색 실험. 독립 truth oracle로 사용 금지 | **격리 critic 실험** | [원문](https://arxiv.org/html/2407.00215v1#S3) |
| ToolGen (ICLR 2025) | **직접: generic tool retrieval/calling**, diagnosis에는 간접 | multi-domain NDCG@1 87.67/83.46/79.00 vs ToolRetriever 72.31/64.54/52.00. constrained decoding에서 nonexistent tool 0 | fine-tuning·tool token virtualization 필요. constraint 제거 시 atomic index도 7% non-tool token. benchmark가 policy/cost of dangerous execution을 모델링하지 않음 | 충분한 project routing logs와 outcome label을 모은 뒤 `static-only / ask approval / test / profiler / abstain` routing 실험 | **격리 learned-router 실험** | [ICLR 원문](https://arxiv.org/html/2410.03439v3#S4) |
| JIT-BiCC (JSS 2025) | **직접: change-level defect prediction**, 원인 진단에는 간접 | Java 21 projects, 27,319 commits. F1 0.478/AUC 0.887 vs best baseline 0.431/0.881. semantic + 14 expert/history features | class imbalance, project/language transfer, commit-message quality, label latency/오류. 공개 Java만 평가 | interpretable diffusion/churn/age/history signals를 별도 feature로 재현; learned semantic encoder는 Python temporal holdout 실험 전 보류 | 단순 change-risk는 **기본 후보**, learned model은 실험 | [원문](https://arxiv.org/html/2410.12107v1#S5.SS1), [DOI](https://doi.org/10.1016/j.jss.2024.112253) |
| Conformal JIT defect prediction (MSR 2024) | **직접: prediction uncertainty/filtering** | 95% correctness guarantee를 낼 수 있던 예측은 DeepJIT 27%, CC2Vec 9%. 실험상 false prediction filtering 가능 | 보장 대상이 소수일 수 있고 exchangeability/score validity가 필요. set size·abstention 비용 증가 | 충분한 시간순 label이 생긴 뒤 “확정/검토/보류” set과 selective risk 평가 | **격리 calibration 실험** | [IEEE 원문](https://ieeexplore.ieee.org/document/10555854) |
| Post-hoc JIT calibration (2025 preprint) | **직접: JIT probability calibration** | DeepJIT ECE가 OpenStack 35%→Platt 2%, QT 33%→2%; Temperature scaling은 각각 36%, 34%로 악화. 다른 model에서도 method 효과가 균일하지 않음 | calibration cohort·method 의존; future drift에서 유지된다는 보장 없음 | raw model/self-consistency score를 확률로 노출하지 말고 calibration method를 cohort별 비교 | **격리 calibration 실험** | [원문](https://arxiv.org/html/2504.12051#S4) |
| Non-exchangeable conformal risk control (ICLR 2024) | **직접: 일반 통계 방법**, code diagnosis에는 간접 | non-exchangeable data에서 monotone loss의 expected value를 제어하고 change point/time series/drift에 relevance weighting을 허용 | weight 선택이 잘못되면 bound가 느슨함; code-health task의 loss·labels는 별도 설계 필요 | branch/time drift가 확인되면 rolling calibration과 최근성 weighting 후보 | **장기 실험** | [ICLR 원문](https://proceedings.iclr.cc/paper_files/paper/2024/hash/de04896f011beff76c91e094f72727f4-Abstract-Conference.html) |
| SWE-Reasoner TTC (2025 preprint) | **patch resolution + 일부 localization**, priority에는 간접 | internal 37.6% resolved, external budget=8 결합 46.0%; internal full function localization 54.49% vs all ablated 47.25% | 8 rollouts, PRM/ORM, execution. 최고 난도에서는 추가 budget가 악화; execution-only 선택도 false positive로 불안정 | uncertainty/criticality 기반 제한적 extra sample을 격리 측정. 무조건 N배 실행 금지 | **격리 TTC 실험** | [원문](https://arxiv.org/html/2503.23803v1#S3) |
| SWE-bench official evaluation | **patch outcome 정의** | generated patch를 repository에 적용하고 tests로 issue resolved 여부 판정 | test coverage·oracle 범위에 종속; known issue만 포함 | patch result는 downstream 보조 지표로만 사용 | 진단 KPI와 분리 | [공식 가이드](https://www.swebench.com/SWE-bench/guides/evaluation/) |

## 4. 기법별 시스템 설계 함의

### 4.1 Graph-aware retrieval

**[FACT]** LocAgent의 ablation은 graph relation 중 directory `contain`만 남기는 것보다 `import/invoke/inherit`를 포함한 full graph가 function localization에 더 유리했고, 동시에 SearchEntity와 BM25 sparse index가 가장 큰 기여 요소였다([실험 표](https://arxiv.org/html/2503.09089v2#S5.SS6)).

**[PROJECT-HYPOTHESIS] 기본 정적 경로**

1. Python source를 실행하지 않고 AST/CST/symbol table로 file/module/class/function/method를 인덱싱한다. Python 표준 `ast`는 source를 AST로 파싱하는 공식 인터페이스다([Python AST 문서](https://docs.python.org/3/library/ast.html)).
2. `contains`, syntactically-resolved `imports`, `calls`, `inherits`, `references`, test-to-target, config-to-consumer 관계를 typed edge로 기록한다.
3. 각 edge에 `exact / syntactic-ambiguous / unresolved` 상태와 parser version을 붙인다. dynamic dispatch나 monkey patch를 억지로 단일 edge로 확정하지 않는다.
4. lexical/BM25, exact symbol, graph k-hop을 별도 score로 보존하고 최종 rank에서 결합한다. graph-only path는 두지 않는다.
5. 정기 기준 브랜치는 full graph snapshot, RC는 `changed node + changed edge + k-hop dependent` delta view를 우선 검색한다.
6. source citation은 file, symbol, line range, content hash로 고정해 verifier가 실제 존재와 snapshot 일치를 기계적으로 검사한다.

**대조 실험**

- `S0 lexical/symbol only` 대 `S1 + typed graph`, 같은 model·prompt·candidate budget.
- 별도 ablation: `contain-only`, `+imports`, `+calls/inherits`, `full`; dynamic unresolved edge 포함/제외.
- endpoint: file/function Recall@k와 exact-set Acc@k, MRR/AP/nDCG, root-cause explanation correctness, false-positive findings per clean snapshot, token/time/index cost.
- RC cohort는 patch location만 정답으로 쓰지 말고 독립 reviewer가 “원인 관련 위치”와 “수정 위치”를 각각 label한다.

**실패 조건**

- generated/templated code, import alias·conditional import, decorators, DI registry, runtime plugin discovery, monkey patch, `getattr`/reflection, native extension 경계에서는 정적 graph가 불완전하다.
- **[UNSUPPORTED]** graph centrality가 곧 severity 또는 fault probability라는 주장은 없다.
- **[UNSUPPORTED]** graph DB 자체가 localization을 개선한다는 근거는 없다. 핵심은 relation 품질과 retrieval protocol이다.

### 4.2 Execution-guided diagnosis

**[FACT]** AutoFL은 test interaction이 없는 `Test-GPT3.5`보다 일관되게 나았지만, 설명 정확도는 위치화보다 훨씬 낮고, helper-heavy tests·너무 넓은 coverage·긴 method·context budget이 실패 원인이었다([AutoFL 결과](https://arxiv.org/html/2308.05487#S5)).

**[PROJECT-HYPOTHESIS] 정책 승인 후 functional path**

1. 승인 객체에 commit/snapshot, 명령, test selection, timeout, resource/network/filesystem policy를 고정한다.
2. 먼저 기존 failing test, stack trace, coverage를 수집한다. AI가 새 test를 만들기 전에 기존 증거를 우선한다.
3. static graph candidate와 executed path의 교집합·차집합을 모두 모델에 제공한다.
4. finding claim을 `증상 → 실행 경로 → 의심 지점 → 예상 invariant 위반 → 반증 조건`으로 구조화한다.
5. 동일 failing test 재실행이나 patch 생성 자체를 진단 정답으로 삼지 않는다. 독립 oracle/test/reviewer가 원인 claim을 판정한다.

**대조 실험**

- `D0 static only` 대 `D1 + stack` 대 `D2 + coverage` 대 `D3 + values/trace`.
- 실행 승인 편향을 피하려고 같은 issue set에서 static result를 먼저 freeze한 뒤 동적 evidence만 추가한다.
- endpoint는 위치화뿐 아니라 cause precision/recall, misleading explanation rate, time-to-confirm, executed commands, flaky rerun rate, resource cost다.

### 4.3 Performance diagnosis

**[FACT]** EffiHolmes는 single aggregated profile의 hotspot이 fix location과 다를 수 있음을 전제로 baseline/scaled trace 차이와 call path를 사용한다. 140개 benchmark는 base commit slowdown 재현과 fix commit speedup을 실행으로 확인했다([dataset protocol](https://arxiv.org/html/2608.03558v1#S4.SS2)).

**[PROJECT-HYPOTHESIS] 정책 승인 후 performance path**

1. 임의 AI workload가 아니라 production contract 또는 maintainer 승인 workload를 우선 사용한다.
2. base와 scaled/release-candidate workload는 API sequence, data type/distribution, environment를 같게 하고 scale factor만 사전 등록한다.
3. warm-up, repetitions, isolation, CPU affinity/limits, cache state, background load를 기록한다.
4. absolute hotspot과 differential self-time을 분리하고, hotspot leaf에서 upstream control/dispatch/allocation/caching decision으로 call path를 역추적한다.
5. 후보 위치마다 `runtime delta`, `call path`, `static code edge`, `change history`, `counterexample workload`를 연결한다.
6. profiler 실행은 자동 기본 경로가 아니며 승인 artifact 없이는 수행하지 않는다.

**실패 조건**

- workload가 symptom을 재현하지 않거나 scale 외 semantics를 바꾸면 differential result가 무효다.
- JIT/warmup, async/multiprocess, I/O/network, native-extension time이 trace에 제대로 귀속되지 않으면 causal path가 끊긴다.
- profiler overhead와 observer effect가 delta보다 크면 보류한다.
- **[UNSUPPORTED]** 가장 느린 함수가 수정 지점이라는 규칙은 채택하지 않는다.

### 4.4 Verifier / critic

**[FACT]** CriticGPT의 개선은 short, LLM-generated Python answers에 대한 critique이고, 논문은 multi-file 미지원과 높은 hallucination/nitpick rate를 명시한다([limitations](https://arxiv.org/html/2407.00215v1#S5)).

**[PROJECT-HYPOTHESIS] verifier를 세 층으로 나눈다.**

1. **기계 verifier(기본):** cited file/line/hash 존재, symbol/edge 존재, static warning 원문, metric 계산, snapshot 일치, policy approval 존재를 검사한다.
2. **evidence verifier(승인 후):** test/trace/profile run ID, exit/status, repetitions, environment, measured invariant가 claim과 일치하는지 검사한다.
3. **model critic(격리):** 누락, 반례, 더 단순한 설명, evidence-claim 불일치를 제안한다. 같은 model의 자기동의를 정답으로 취급하지 않는다.

Critic의 출력은 finding을 직접 승격하지 않고 `accept / reject / revise / escalate` 제안과 근거 span만 만든다. Critic disagreement는 위험 점수가 아니라 추가 검토 trigger다.

**대조 실험**

- no critic / same-model self-critic / independently prompted critic / different-model critic / mechanical+human.
- endpoint: verified true finding recall, hallucinated finding rate, reviewer acceptance, reviewer time, unique useful objection, correlation of critic confidence with correctness.
- critic가 길어질수록 bug recall과 hallucination이 함께 늘 수 있으므로 claim 수와 review cost를 보고한다. CriticGPT의 FSBS도 이 Pareto trade-off를 명시한다([결과](https://arxiv.org/html/2407.00215v1#S3.SS4)).

### 4.5 Learned tool routing

**[FACT]** ToolGen은 학습된 generative retrieval과 constrained decoding으로 generic tool retrieval/calling을 개선했지만, retrieval training 제거 시 NDCG가 급락했고 constraint 제거 시 nonexistent-tool 생성이 다시 나타났다([ablation](https://arxiv.org/html/2410.03439v3#S4.SS4), [hallucination](https://arxiv.org/html/2410.03439v3#S5.SS4)).

**[PROJECT-HYPOTHESIS]** 초기 시스템은 learned router 대신 명시적 policy state machine을 쓴다.

- `STATIC_READ` → 자동 허용 도구만.
- `NEED_EXECUTION_EVIDENCE` → 승인 요청 또는 abstain.
- `APPROVED_TEST` / `APPROVED_PROFILE` → 승인 범위와 budget 안의 도구만.
- `INSUFFICIENT_EVIDENCE` → finding을 낮추는 대신 보류 사유를 출력.

충분한 routing log가 쌓인 뒤 learned router를 shadow mode로 실행한다. 정답은 “task completed”가 아니라 policy violation 0, correct escalation, unnecessary execution rate, diagnosis utility, cost다. model이 승인 자체를 예측·대체하지 않는다.

### 4.6 Uncertainty calibration / conformal methods

**[FACT]** raw neural score는 calibration을 보장하지 않는다. JIT calibration 연구에서 Platt scaling은 DeepJIT의 ECE를 크게 낮췄지만 Temperature scaling은 악화했고, technique별 결과도 달랐다([2025 preprint](https://arxiv.org/html/2504.12051#S4)). **[FACT]** CP의 nominal guarantee는 exchangeability 같은 가정에 의존하며, non-exchangeable CRC는 drift를 위해 relevance weighting을 제안한다([ICLR 2024](https://proceedings.iclr.cc/paper_files/paper/2024/hash/de04896f011beff76c91e094f72727f4-Abstract-Conference.html)).

**[PROJECT-HYPOTHESIS] 불확실성을 하나의 숫자로 합치지 않는다.**

- `existence uncertainty`: finding 자체가 참인가.
- `localization uncertainty`: top-k 안에 원인 관련 위치가 있는가.
- `causal uncertainty`: 설명한 path/invariant가 맞는가.
- `impact uncertainty`: severity·blast radius 추정이 맞는가.
- `evidence sufficiency`: 정적만인지, 실행으로 확인됐는지.

초기에는 `unvalidated score`와 근거 구성요소를 노출하고 확률 표현을 금지한다. 시간순 project labels가 충분해진 뒤 calibration window와 평가 window를 분리해 ECE/Brier/reliability, risk-coverage curve, selective precision/recall, abstention rate를 측정한다. branch·framework·issue type별 drift를 먼저 확인하고, ordinary CP와 rolling/non-exchangeable candidate를 비교한다.

**[UNSUPPORTED]** self-consistency 0.8을 “80% 정확”으로 표기하는 것, 외부 benchmark calibration을 현재 repository에 적용하는 것, 낮은 uncertainty를 높은 severity로 해석하는 것은 금지한다.

### 4.7 Test-time compute

**[FACT]** code TTC 연구는 more rollouts가 항상 낫지 않음을 보여준다. 최고 난도 bucket에서는 budget 증가가 정확도를 조금 낮췄고, execution-only selection은 false positive 때문에 budget=8에서 악화됐다([분석](https://arxiv.org/html/2503.23803v1#S3.SS4)).

**[PROJECT-HYPOTHESIS]** TTC는 격리된 budget frontier 실험으로만 운영한다.

- budget `1/2/4/8`에서 같은 model, same candidate context로 비교한다.
- 추가 sample은 모든 finding이 아니라 high-impact + high-uncertainty + critic disagreement cases에만 준다.
- majority vote, reward model rank, evidence-backed rank를 각각 비교한다.
- endpoint는 diagnosis utility뿐 아니라 tokens, wall time, dynamic runs, reviewer burden, marginal gain per unit cost다.
- hard-case regression과 false-positive amplification이 있으면 adaptive stop rule을 설계한다.

### 4.8 Temporal / change-risk

**[FACT]** JIT-BiCC의 14 expert features는 change diffusion, size, purpose, history, developer experience를 포함하고, semantic representation과 결합한 change-level prediction에서 강한 비교군보다 F1 10.8% 상대 개선을 보였다([feature table와 결과](https://arxiv.org/html/2410.12107v1#S3.SS2.SSS1), [결과](https://arxiv.org/html/2410.12107v1#S5.SS1)). 이 결과는 Java commits의 defect classification이며 원인 설명 품질을 측정하지 않았다.

**[PROJECT-HYPOTHESIS] 기본 투명 특성 후보**

- lines/files/directories changed, change entropy, churn/unique changes, code age, recent change burst, ownership concentration, subsystem experience, static graph blast radius, critical-path membership, baseline→RC new dependency edge.
- 각각 raw value, time window, missingness, source commit를 보존한다.
- learned semantic score와 합치기 전 단순 ranker/logistic/monotonic model을 baseline으로 둔다.
- 기준 브랜치 정기 점검과 RC 점검을 분리한다. RC는 changed code와 dependents가 중심이고, 기준 점검은 오래된 hotspot/ownership/dependency debt도 포함한다.

**시간 누수 방지**

- train/calibration은 issue 발생·수정·label 시점보다 이전 정보만 사용한다.
- random split을 기본으로 쓰지 않고 chronological forward holdout과 unseen-repository holdout을 모두 둔다.
- 동일 bug-fix chain, backport, cherry-pick, duplicate issue가 양쪽 split에 걸치지 않게 group한다.
- label이 뒤늦게 생기는 censoring을 기록한다.

**[UNSUPPORTED]** churn이 높은 코드는 결함이라는 인과 주장, 최근 변경자가 위험하다는 사람 평가, commit message semantic score가 severity라는 해석은 하지 않는다.

## 5. 패치 벤치마크와 진단·우선순위 성과의 차이

| 관찰된 성과 | 실제로 입증하는 것 | 입증하지 않는 것 | 필요한 별도 평가 |
|---|---|---|---|
| SWE-bench `% resolved` | **[FACT]** patch 적용 후 repository tests가 issue를 해결했다고 판정([공식 가이드](https://www.swebench.com/SWE-bench/guides/evaluation/)) | clean snapshot false-positive, pre-patch risk rank, root-cause explanation, severity calibration | no-issue snapshots, diagnosis labels, risk ranking, human review |
| Gold patch와 file/function overlap | developer가 수정한 위치를 top-k에 포함 | 그 위치가 원인인지 workaround인지, 수정하지 않은 causal dependency를 찾았는지 | cause location과 fix location을 독립 label |
| Generated test/patch가 통과 | 그 generated artifact가 현재 oracle을 통과 | 설명이 참인지, hidden behavior를 보존하는지, suite 밖 regression이 없는지 | independent oracle, mutation/negative controls, reviewer cause judgment |
| Critic 선호도 | 특정 critique distribution에서 상대적 helpfulness | repository finding precision, calibrated truth probability | natural multi-file defects, clean negatives, claim-level verification |
| Tool routing NDCG/pass rate | generic tool을 잘 찾고 task를 완료 | 승인 준수, 필요 없는 실행 최소화, diagnosis quality | policy-routing benchmark와 violation audit |
| JIT defect F1/AUC | change-level defective/non-defective 분류 | 어느 함수가 원인인지, 왜 위험한지, review effort 대비 이득 | localization/cause/effort-aware rank + calibration |
| Profiler hotspot | 시간이 소비된 위치 | 성능 regression을 유발한 upstream decision | differential workload, call path, counterfactual/scale evidence |

**[FACT]** SWE-bench는 known GitHub issues와 corresponding repository를 받아 patch를 생성·검증하는 benchmark다([공식 평가](https://www.swebench.com/SWE-bench/guides/evaluation/)). **[PROJECT-HYPOTHESIS]** 정기 건강검진은 대다수 snapshot이 알려진 issue를 포함하지 않을 수 있으므로 clean/unknown/ambiguous 사례가 반드시 포함돼야 한다. 그렇지 않으면 false-positive burden과 우선순위 효용을 측정할 수 없다.

**[UNSUPPORTED] 금지할 전이**

- patch resolution 46% → “진단 정확도 46%”
- Pass@k 증가 → “위험 우선순위 품질 향상”
- gold patch overlap → “원인 규명”
- generated patch test pass → “finding 검증 완료”
- critic가 동의 → “사실 확인”
- vendor leaderboard → 현재 Python backend의 A+ 성과

## 6. 기본 경로 후보와 격리 실험 후보

### 6.1 기본 정적 경로 후보

| 단계 | 후보 | 자동/승인 | 출력 상태 | 독립 기여 실험 |
|---|---|---|---|---|
| Snapshot/diff | 기준 branch와 RC의 immutable commit, changed files/symbols/edges | 자동 정적 | 입력 provenance | diff off/on |
| Candidate retrieval | lexical/exact symbol + typed graph k-hop | 자동 정적 | cited candidates | lexical vs +graph |
| Deterministic analyzers | 기존 static analyzer/type/lint/complexity/dependency 결과 ingest | 자동 정적 읽기 범위 | tool-evidenced finding | tool family별 ablation |
| Change-risk | 투명 history/diff/ownership/graph-delta components | 자동 정적 | uncalibrated priority feature | without/with temporal components |
| AI synthesis | 증거를 claim/invariant/counterevidence로 요약 | 자동 정적 | hypothesis unless mechanically supported | no-LLM vs LLM summary |
| Mechanical verifier | line/hash/edge/tool-output/source consistency | 자동 정적 | verified-static / rejected / stale | verifier off/on |
| Rank | impact basis × evidence state × project criticality; raw components 유지 | 자동 정적 | **비확률** rank | simple rule vs learned ranker(후자는 실험) |

**[PROJECT-HYPOTHESIS]** 기본 경로의 AI는 source를 새로 실행하거나 patch를 만들지 않는다. static evidence로 원인까지 확정할 수 없는 항목은 `NEEDS_APPROVED_EXECUTION`으로 남긴다.

### 6.2 정책 승인 후 동적 경로 후보

| 사용 사례 | 최소 실행 | 추가 증거 | 승격 조건 |
|---|---|---|---|
| Functional failure | 지정 failing test/reproducer | stack, coverage, selected values/trace | 같은 snapshot·승인 범위, 독립 oracle, 재현성 |
| Regression | base와 RC의 동일 approved scenario | differential coverage/trace | environment parity, repeatability, confound 기록 |
| Performance | approved baseline/scaled workload | repeated timings, differential trace, critical path | workload semantic validity, profiler overhead check, effect reproducibility |
| Concurrency/async | bounded isolated scenario | task/thread/process trace | scheduler noise와 nondeterminism 보고 |

### 6.3 추가 제안용 격리 실험

1. Graph-guided agentic multi-hop exploration.
2. AutoFL식 multi-run execution-guided aggregation.
3. EffiHolmes식 differential trace path compression.
4. same-model/different-model trained critic 및 reward model.
5. learned policy-aware tool router.
6. Platt/isotonic/temperature/conformal/non-exchangeable calibration.
7. difficulty/uncertainty-adaptive TTC.
8. semantic change encoder와 temporal learned ranker.
9. LLM-generated reproducer/workload—반드시 independent semantic validation 포함.

격리 실험의 결과는 승격 전 기본 위험표, 핵심 KPI, A+ 성과에 합산하지 않는다([프로젝트 지도](../map.md)).

## 7. 후속 결정 티켓이 사용할 검증 설계

### 7.1 동일한 진단 계약

모든 후보는 patch 생성 없이 다음 계약으로 비교한다.

```text
Input:
  immutable snapshot(s), scan mode, policy state, allowed evidence, budget
Output per finding:
  category, location set, cause claim, evidence links, counterevidence,
  impact basis, uncertainty dimensions, verifier state, next action, cost
```

모델마다 자유 형식 결과를 다른 judge LLM으로만 평가하지 않는다. location, source/evidence ID, claim unit, abstain을 구조화한다.

### 7.2 평가 cohort

- 공개/합성: clean negatives, seeded but realistic functional defects, performance regressions, graph-distance strata.
- 시간순 실제: issue/fix가 scan 시점 뒤에 확인된 사례, base→RC regressions, no-finding snapshots.
- 익명 실제: project/framework/size/async/DI/native boundary strata와 reviewer consent/redaction.
- difficult negatives: high churn but clean, hotspot but intentional, central graph node but stable, flaky test, noisy profiler.

### 7.3 endpoint

**검출/위치화**

- finding precision/recall, false positives per KLoC 또는 scan, file/function Acc@k, MRR, AP/nDCG.
- clean-snapshot specificity와 “no finding” accuracy.

**진단**

- 독립 reviewer의 cause correctness, evidence entailment, invariant correctness, misleading explanation rate.
- symptom/hotspot만 맞춘 경우와 upstream cause를 맞춘 경우를 분리.

**우선순위**

- review budget별 Recall@budget, effort-aware AUCEC/inspection cost, top-k critical miss, time-to-first-confirmed-risk.
- severity와 probability를 분리하고 critical false negative를 별도 보고.

**불확실성**

- ECE, Brier, reliability, risk-coverage/selective accuracy, abstention rate, conformal coverage와 set size.
- calibration cohort 외 framework/기간에서 drift 성능.

**운영 비용·안전**

- tokens, wall/CPU/GPU time, index storage/update, dynamic commands, retries, reviewer minutes.
- policy violations, unauthorized execution 0 여부, stale citation, nondeterminism/flakiness.

### 7.4 최소 대조 순서

1. deterministic static analyzers only.
2. `+ lexical/symbol retrieval`.
3. `+ typed graph`.
4. `+ temporal/change-risk`.
5. `+ AI synthesis`, evidence 동일.
6. `+ mechanical verifier`.
7. 승인 cohort에서만 `+ execution evidence`.
8. 별도 실험으로 `+ critic`, `+ calibration`, `+ adaptive TTC`, `+ learned router`.

각 단계는 동일 cohort, snapshot, model where applicable, candidate/output budget을 사용한다. 한 번에 여러 구성요소를 추가해 전체 개선만 보고하지 않는다.

### 7.5 승격 원칙

숫자 threshold는 아직 project data와 reviewer cost가 없어 정하지 않는다.

- 사전 등록한 primary diagnosis/priority endpoint에서 baseline 대비 개선.
- critical miss, misleading explanation, policy violation은 non-inferior 또는 개선.
- clean snapshot false positives와 reviewer burden을 함께 통과.
- base scan과 RC scan 모두에서 재현; framework/time holdout에서 붕괴하지 않음.
- 비용과 marginal utility를 보고하고, 동적 경로는 승인 성공률·거절 시 graceful abstention까지 검증.
- 외부 benchmark 수치가 아니라 project contrast의 confidence interval과 raw counts로 결정.

## 8. 위험 우선순위표에 주는 명세 함의

**[PROJECT-HYPOTHESIS]** 최종 표는 다음 필드를 보존해야 “검증된 위험”과 “AI 가설”이 섞이지 않는다.

| 필드 | 의미 |
|---|---|
| `finding_id`, `scan_id`, `snapshot` | immutable provenance |
| `mode` | baseline / RC |
| `rank`, `category` | 출력 순서와 risk family |
| `locations[]` | file/symbol/line/hash, fix location과 cause location 역할 구분 |
| `claim` | 하나의 반증 가능한 원인 주장 |
| `evidence[]` | static tool, source span, graph path, test/trace/profile run ID |
| `counterevidence[]` | claim을 약화하는 관찰 |
| `impact_basis` | severity 근거; probability와 분리 |
| `existence/localization/causal/impact_uncertainty` | 다차원 불확실성; calibration 전 확률 금지 |
| `calibration_cohort/version` | calibrated score가 있을 때만 |
| `verifier_state` | hypothesis / verified-static / verified-dynamic / rejected / stale |
| `policy_state` | static-only / approval-needed / approved scope / denied |
| `missing_evidence` | 확정을 막는 정보 |
| `recommended_next_action` | read/review/ask approval/run bounded evidence |
| `model/tool/prompt/index versions` | 재현성 |
| `cost` | token/time/commands/reviewer effort |

`verified-dynamic`도 “관찰된 scenario에서 claim이 지지됨”을 뜻할 뿐 모든 production input에 대한 보장은 아니다.

## 9. 새 아이디어

### 9.1 Delta-graph counterfactual retrieval

**[PROJECT-HYPOTHESIS]** RC의 changed edge를 제거한 base graph와 RC graph를 같은 query로 탐색한다. RC에서만 새로 생기는 shortest path, fan-in/fan-out, critical boundary crossing을 finding evidence로 사용한다. 단순 centrality가 아니라 **변경으로 생긴 관계 차이**를 원인 후보로 삼고 graph contribution을 `full graph vs delta graph vs no graph`로 검증한다.

### 9.2 Evidence cut-set verifier

**[PROJECT-HYPOTHESIS]** cause claim을 지지하는 evidence가 하나의 producer/model에만 의존하면 “circular”로 표시한다. source/static tool, history, runtime trace, independent oracle 중 서로 독립적인 축이 몇 개인지 `evidence cut-set`으로 기록한다. 같은 LLM이 test·patch·critic을 모두 만들어 서로 통과시키는 경우는 한 축으로 센다.

### 9.3 Hotspot-to-control causal path

**[PROJECT-HYPOTHESIS]** performance finding에서 leaf hotspot을 그대로 rank하지 않고 `entry → control/allocation/cache decision → repeated/expensive path → hotspot`으로 분해한다. EffiHolmes의 execution-path ablation이 강한 직접 동기지만, 이 causal schema 자체는 프로젝트에서 검증해야 한다([EffiHolmes ablation](https://arxiv.org/html/2608.03558v1#S5.SS2)).

### 9.4 Two-key escalation

**[PROJECT-HYPOTHESIS]** 동적 승인은 model uncertainty 하나로 요청하지 않고 `(잠재 impact, evidence deficit)` 두 key가 모두 일정 조건을 만족할 때 요청한다. high uncertainty/low impact는 abstain, high impact/static evidence sufficient는 human review, high impact/evidence deficit는 bounded execution 요청으로 분기한다.

### 9.5 Temporal conformal with diagnosis TTL

**[PROJECT-HYPOTHESIS]** calibration validity뿐 아니라 finding 자체에 TTL을 둔다. graph/index/model/framework/branch drift가 일정 event를 넘으면 score를 폐기하고 재검증한다. ordinary CP와 recent-weighted non-exchangeable CRC의 coverage/set-size를 forward windows에서 비교한다. Non-exchangeable CRC는 change point와 time-series drift를 위한 weighting을 공식 제안한다([ICLR 2024](https://proceedings.iclr.cc/paper_files/paper/2024/hash/de04896f011beff76c91e094f72727f4-Abstract-Conference.html)).

### 9.6 Budget frontier router

**[PROJECT-HYPOTHESIS]** learned router의 action을 특정 tool name이 아니라 `static expand`, `ask approval`, `approved test`, `approved profile`, `critic`, `abstain`의 정책 action으로 제한한다. shadow logs에서 각 action의 marginal verified-diagnosis gain과 비용을 학습한다. constrained decoding이 nonexistent tools를 차단한 ToolGen 결과는 action grammar의 근거지만 code-policy utility는 새로 검증해야 한다([ToolGen](https://arxiv.org/html/2410.03439v3#S5.SS4)).

### 9.7 Negative-evidence-first critic

**[PROJECT-HYPOTHESIS]** critic에게 “더 많은 문제를 찾아라”가 아니라 top finding을 무효화할 가장 강한 반례 하나를 요구한다. CriticGPT에서 critique 길이·포괄성과 hallucination이 같이 증가한 trade-off를 피하려는 설계다([CriticGPT](https://arxiv.org/html/2407.00215v1#S3.SS4)).

## 10. 기각 또는 보류 아이디어

### 즉시 기각

- **[UNSUPPORTED]** SWE-bench/patch leaderboard 상위 제품을 기본 진단 엔진으로 바로 채택.
- **[UNSUPPORTED]** generated patch가 tests를 통과하면 finding·원인·severity까지 검증됐다고 표시.
- **[UNSUPPORTED]** 동일 model의 self-critique/majority vote를 독립 verifier로 간주.
- **[UNSUPPORTED]** raw logit, verbal confidence, self-consistency를 calibrated probability로 표시.
- **[UNSUPPORTED]** graph centrality, churn, ownership, profiler self-time 중 하나를 severity로 직접 변환.
- **[FACT:PROJECT]** 사용자 승인 없는 import/test/benchmark/profiler 실행은 프로젝트 범위 밖이다([프로젝트 지도](../map.md)).

### 증거가 생길 때까지 보류

- **Learned tool router:** generic tool evidence만 있고 policy-aware diagnosis label이 없음.
- **Trained repository critic/reward model:** 자연 multi-file diagnosis 데이터와 clean negatives가 없음.
- **Fixed high TTC budget:** hard-case regression과 비용 증가가 관찰됨([SWE-Reasoner](https://arxiv.org/html/2503.23803v1#S3.SS4)).
- **Conformal guarantee 표시:** project exchangeability/drift, score, loss, calibration set이 정해지지 않음.
- **JIT-BiCC semantic encoder:** Java 공개 데이터 결과이며 Python/project forward validation이 없음.
- **AI-generated scaled workload:** semantic equivalence와 production relevance를 독립 확인할 방법이 아직 없음.
- **특정 graph database/vector database:** 저장·질의 구현 선택은 relation/retrieval contribution을 입증한 뒤의 결정이다.

## 11. 미해결 질문

1. 대상 저장소의 Python version, framework, typing, DI, async, multiprocessing, native-extension 비율은 무엇인가?
2. 정기 baseline과 RC의 실제 Git topology, merge-base, backport/cherry-pick 정책은 무엇인가?
3. core/critical path와 severity·blast-radius의 독립 ground truth는 누가 정하는가?
4. clean negative, ambiguous finding, performance regression, security/feature change를 각각 몇 건 확보할 수 있는가?
5. cause location, fix location, symptom location을 독립 판정할 reviewer와 adjudication protocol은 무엇인가?
6. 실행 승인 단위, 허용 command/environment/network/filesystem, timeout/resource budget은 무엇인가?
7. profiler workload의 semantic validity와 production representativeness를 누가 승인하는가?
8. async/multiprocess/native time을 어떤 tracer/profiler가 손실 없이 관찰하는가?
9. temporal labels의 관찰 지연과 아직 발견되지 않은 결함을 어떻게 censoring 처리하는가?
10. 허용 가능한 clean-scan false-positive burden, reviewer minutes, critical false-negative cost는 얼마인가?
11. calibration을 위한 최소 label 수와 framework/issue별 cohort 분할 가능성은 무엇인가?
12. 최종 심사에서 raw source, run artifact, frozen container, redacted evidence 중 무엇을 제출할 수 있는가?

## 12. 출처

### 직접 진단·위치화

1. Chen et al., **LocAgent: Graph-Guided LLM Agents for Code Localization**, ACL 2025. <https://aclanthology.org/2025.acl-long.426/>; 상세 HTML <https://arxiv.org/html/2503.09089v2>
2. Kang et al., **A Quantitative and Qualitative Evaluation of LLM-Based Explainable Fault Localization (AutoFL)**, FSE 2024. <https://arxiv.org/html/2308.05487>
3. Yang et al., **EffiHolmes: Differential Profiling-Guided Repository Level Time Inefficiency Fix Localization**, ASE 2026 게재 예정. <https://arxiv.org/html/2608.03558v1>; DOI <https://doi.org/10.1145/3832783.3834353>
4. Ouyang et al., **RepoGraph: Enhancing AI Software Engineering with Repository-level Code Graph**, 2024 preprint. <https://arxiv.org/html/2410.14684v2>

### Critic, routing, TTC

5. McAleese et al., **LLM Critics Help Catch LLM Bugs (CriticGPT)**, 2024 preprint. <https://arxiv.org/html/2407.00215v1>
6. Wang et al., **ToolGen: Unified Tool Retrieval and Calling via Generation**, ICLR 2025. <https://arxiv.org/html/2410.03439v3>; ICLR record <https://proceedings.iclr.cc/paper_files/paper/2025/hash/b646bdebeb87dfafe2c6f77a63b5564e1-Abstract-Conference.html>
7. Ma et al., **Thinking Longer, Not Larger: Enhancing Software Engineering Agents via Scaling Test-Time Compute**, 2025 preprint. <https://arxiv.org/html/2503.23803v1>
8. Snell et al., **Scaling LLM Test-Time Compute Optimally Can Be More Effective than Scaling Model Parameters**, ICLR 2025. <https://proceedings.iclr.cc/paper_files/paper/2025/hash/1b623663fd9b874366f3ce019fdfdd44-Abstract-Conference.html>

### Change-risk와 불확실성

9. Jiang et al., **Just-In-Time Software Defect Prediction via Bi-modal Change Representation Learning**, Journal of Systems and Software. <https://arxiv.org/html/2410.12107v1>; DOI <https://doi.org/10.1016/j.jss.2024.112253>
10. Shahini, Metzger, Pohl, **An Empirical Study on Just-in-time Conformal Defect Prediction**, MSR 2024. <https://ieeexplore.ieee.org/document/10555854>; DOI <https://doi.org/10.1145/3643991.3644928>
11. Shahini, Bartel, Pohl, **On the calibration of Just-in-time Defect Prediction**, 2025 preprint. <https://arxiv.org/html/2504.12051>
12. Farinhas et al., **Non-Exchangeable Conformal Risk Control**, ICLR 2024. <https://proceedings.iclr.cc/paper_files/paper/2024/hash/de04896f011beff76c91e094f72727f4-Abstract-Conference.html>
13. Angelopoulos et al., **Conformal Risk Control**, ICLR 2024. <https://proceedings.iclr.cc/paper_files/paper/2024/hash/f3549ef9b5ff520a7e41ff3cc306ab2b-Abstract-Conference.html>

### Benchmark·공식 원리

14. SWE-bench, **Official Evaluation Guide**. <https://www.swebench.com/SWE-bench/guides/evaluation/>
15. Python Software Foundation, **`ast` — Abstract Syntax Trees**. <https://docs.python.org/3/library/ast.html>

## 13. 최종 판정

- **[FACT]** 2024년 이후 공개 근거 중 이 시스템의 진단에 가장 가까운 것은 (a) LocAgent의 graph+sparse code localization, (b) AutoFL의 failing-test/coverage-guided functional localization, (c) EffiHolmes의 differential profiling execution-path localization, (d) JIT change-risk와 conformal filtering이다. 각각 location, explanation, performance fix location, change-level risk라는 서로 다른 endpoint를 측정한다.
- **[PROJECT-HYPOTHESIS]** 따라서 기본 자동 경로는 static hybrid retrieval·typed graph·transparent change features·mechanical evidence verification으로 작게 구성하고, 실행 증거는 승인 후 별도 lane으로 결합하는 것이 가장 검증 가능하다.
- **[PROJECT-HYPOTHESIS]** critic, learned routing, calibration, TTC는 독립 contribution과 failure cost를 project cohort에서 입증한 뒤에만 승격한다.
- **[UNSUPPORTED]** 외부 patch benchmark, vendor leaderboard, generated patch/test success를 현재 프로젝트의 진단·위험 우선순위 성과로 주장할 수 없다.
- 후속 결정은 제품 선택이 아니라 위 대조 실험의 cohort, ground truth, endpoint, 정책 승인 계약, 승격 threshold를 확정해야 한다.
