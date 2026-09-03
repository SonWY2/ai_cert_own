# 코드 진단 평가 자료와 검증 방법 근거

> 조사 기준일: 2026-08-29  
> 범위: Python 백엔드 코드 건강검진의 **진단·위험 순위·사람 의사결정 지원** 평가. 자동 수리나 패치 생성 성능은 평가 목표가 아니다.  
> 실행 상태: 문헌·공식 메타데이터·저장소 문서만 조사했다. 프로젝트 코드, 테스트, benchmark, profiler는 실행하지 않았고 이 문서는 프로젝트 성능 증적이 아니다.

## 요약

### 주장 표기

- **FACT**: 링크한 원문·공식 문서가 직접 뒷받침하는 사실이다.
- **PROJECT-HYPOTHESIS**: 이 프로젝트에 적용할 설계 제안 또는 아직 실험하지 않은 기대다. 후속 결정과 실행 검증이 필요하다.
- **UNSUPPORTED**: 현재 근거가 없거나 이번 조사로 확인하지 못한 주장이다. 채택·A+·출시 판단에 사용할 수 없다.

### 결론

1. **FACT** — 공개 Python 결함 자료는 재현 가능한 알려진 양성 사례를 제공하지만, 대개 “수정된 한 결함”만 알려 줄 뿐 저장소의 전체 결함 목록, 운영 영향도, Critical/High 등급, 진단 위험 순위의 완전한 정답을 제공하지 않는다. 2026년 종합 조사도 결함 자료의 scope·construction·availability·usability를 별도 축으로 다루며 151개 자료를 식별했다. [원문](https://arxiv.org/html/2504.17977)
2. **PROJECT-HYPOTHESIS** — 최종 검증은 하나의 혼합 점수보다 `(공개 실제 사례 / 합성 mutation / 비공개 익명 실제 사례) × (correctness / performance / concurrency) × (정적 전용 / 승인된 동적)` 층별 결과를 먼저 내야 한다. 공개 사례는 재현성과 회귀, 합성은 통제된 감도, 비공개 실제 사례는 오염 저항성과 운영 타당성을 담당한다. 혼합 가중치는 실제 점검 모집단의 빈도를 측정한 뒤 사전 등록하며 임의의 균등 가중치를 쓰지 않는다.
3. **FACT** — 공개 benchmark의 새 버전만으로 오염이 해소되지는 않는다. 공개 코드의 교차 dataset 중복은 평가 누수를 일으킬 수 있고, freshness를 목적으로 한 SWE-bench-Live도 이제 공개된 자료다. [코드 중복 연구](https://arxiv.org/html/2401.07930) · [SWE-bench-Live](https://arxiv.org/html/2505.23419v2)
4. **PROJECT-HYPOTHESIS** — acceptance test는 모델·튜닝 담당자가 볼 수 없는 비공개 익명/전향 사례를 중심으로 하고, 공개 benchmark는 “open-book 회귀판”으로 별도 표시해야 한다. 모델의 학습자료가 공개되지 않으면 “오염 없음”을 증명할 수 없으므로 `unknown`으로 기록한다.
5. **FACT** — 시간 일관성 있는 repository 평가의 최신 제안은 시점 $T_0$의 snapshot과 그 이후 $(T_0,T_1]$의 task를 분리하고, 동일 agent·prompt·환경에서 한 요인만 바꾸는 matched A/B를 제안한다. 같은 연구는 prompt 상세도가 결과를 크게 바꾸는 교란변수임을 보였다. 다만 해당 논문 결과는 두 저장소의 baseline file-localization이고 이 프로젝트의 진단 성과 증거는 아니다. [원문](https://arxiv.org/html/2603.26137)
6. **PROJECT-HYPOTHESIS** — 위험 순위의 최소 지표 묶음은 `Critical/High 누락 수와 recall`, `Precision@K`, `bpref 또는 판단완료 범위의 nDCG@K`, `저장소-family 단위 신뢰구간`, `비용·지연`, `사람의 제한시간 내 올바른 결정률과 time-to-correct-decision`이다. 평균 하나로 Critical 누락을 상쇄하지 않는다.
7. **FACT** — 불완전 relevance judgment에서는 미판정 항목을 오답으로 간주하는 일반 지표가 왜곡될 수 있다. TREC의 pooled judgment 연구는 불완전 판단에 맞춘 bpref를 제안하고, pool에 참여하지 않은 새 시스템 평가에서도 안정성을 조사했다. [NIST 원문](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=150469)
8. **PROJECT-HYPOTHESIS** — 패치 생성 성공, 테스트 통과, vendor rule 위반 수는 진단 정확도와 동일하지 않다. 이 프로젝트의 판정 단위는 `위험 원인 + 영향을 받는 동작/경로 + 근거 위치 + 영향/우선순위`이며, 패치는 알려진 결함을 찾기 위한 anchor일 뿐 정답 문구가 아니다.
9. **FACT** — agent/LLM 비교는 호출·token·재시도 예산을 통제해야 한다. 반복 호출만으로 accuracy가 오를 수 있고 비용 차이가 매우 커질 수 있다는 2024년 연구가 있다. [원문](https://arxiv.org/html/2407.01502)
10. **PROJECT-HYPOTHESIS** — 핵심 경로 승격은 동일 case에 대한 paired same-budget ablation으로만 인정한다. 제거 arm과 full arm의 모델, prompt, snapshot, 실행권한, seed 묶음, 입력 증거, 최대 token/call/wall-time, hardware를 고정하고 실제 사용량도 함께 공개한다. 최신 기능은 별도 실험 lane에 두며 그 결과를 기본 KPI에 합산하지 않는다.
11. **UNSUPPORTED** — “현재 설계가 공개 benchmark에서 높은 정확도를 낸다”, “Python concurrency를 충분히 대표하는 공개 executable gold corpus가 있다”, “Critical/High를 한 건도 놓치지 않는다”, “사람의 판단 시간을 줄인다”는 실행·자료 증거를 이번 조사에서 확인하지 못했다.

## 근거 표

| 구분 | 직접 근거 | 이 프로젝트에 주는 의미 | 경계·과장 금지 |
|---|---|---|---|
| **FACT** | 2026년 survey는 151개 software-defect dataset을 scope, construction, availability/usability, 실제 사용 측면에서 조사한다. [원문](https://arxiv.org/html/2504.17977) | 이름이 “bug dataset”이라는 사실만으로 진단 gold가 되지 않는다. executable snapshot, defect isolation, label provenance를 따로 심사한다. | survey의 포괄성이 우리 Python/운영 모집단 대표성을 보장하지 않는다. |
| **FACT** | HaPy-Bug은 793개 Python bug-fix commit(2006–2022), 2,742 files, 67,963 lines를 포함하고 세 전문가가 line label을 부여했다. 논문은 전체 Fleiss’ $\kappa=0.83$을 보고한다. [논문](https://arxiv.org/html/2504.04810v1) | 수정 commit의 tangled change를 걸러 localization anchor를 만드는 데 유용하다. | fix line은 전체 위험 inventory, root cause, severity, 발견 우선순위의 완전한 gold가 아니다. 논문 수치를 프로젝트 성능으로 인용하지 않는다. |
| **FACT** | HaPy-Bug Figshare record는 CC BY 4.0, 공개, 약 899 MB archive로 표시된다. [공식 API](https://api.figshare.com/v2/articles/24448663) | license가 명시된 재현 가능한 후보이다. | CC BY 메타데이터가 archive 안의 제3자 repository code license까지 재허가한다고 가정하지 말고 파일별 provenance를 법무 검토한다. |
| **FACT** | BugsInPy 논문은 17개 실제 Python project의 493개 실제 bug와 reproducible failing/passing test 지원을 기술한다. [논문](https://arxiv.org/html/2401.15481) | correctness known-positive와 승인 후 동적 재현 후보이다. | 공개·오래된 사례라 contamination 가능성이 높고 severity/ranking gold가 없다. 현재 GitHub root에는 명시적 LICENSE file이 보이지 않는다. [공식 저장소](https://github.com/soarsmu/BugsInPy) |
| **FACT** | PyBugHive 현재 문서는 11개 project의 149개 수동 검증 bug, report·patch·test, offline environment를 기술한다. [공식 사이트](https://pybughive.github.io/) · [공식 저장소](https://github.com/pybughive/pybughive) | correctness 재현과 의존성 고정 실험 후보이다. | 저장소 최상위에 LICENSE가 없고, offline dump Zenodo metadata에도 license가 명시되지 않았다. 버전별 case 수가 달라 manifest에 dataset version/DOI를 고정해야 한다. [Zenodo API](https://zenodo.org/api/records/8339477) |
| **FACT** | SWE-bench dataset card는 12개 Python repository에서 2,294 issue–PR pair와 base commit, patch, test patch, FAIL_TO_PASS/PASS_TO_PASS를 제공한다고 설명한다. [공식 dataset card](https://huggingface.co/datasets/princeton-nlp/SWE-bench/raw/main/README.md) | issue와 snapshot을 잇는 provenance 형식의 참고 후보이다. | 목표는 issue **resolution**이다. patch/test 통과는 이 시스템의 위험 진단·severity·ranking 성능이 아니다. card에 dataset license 선언이 없고 upstream repo license가 서로 다르다. |
| **FACT** | SWE-bench-Live v2는 2024년 이후 생성된 issue에서 온 1,319 tasks, 93 repositories를 공개한다고 보고한다. [원문](https://arxiv.org/html/2505.23419v2) | 수시 refresh와 created/merged date 기록의 실제 자료원이다. | 이제 공개됐으므로 영구 blind holdout이 아니다. 오래된 repository code나 benchmark-aware tuning의 오염까지 제거했다는 뜻도 아니다. |
| **FACT** | 2026년 time-consistent benchmark는 $T_0$ 이전 지식과 이후 PR task를 분리하고 matched A/B를 형식화했으며, prompt granularity 자체가 file-localization 결과를 크게 바꾼다고 보고한다. [원문](https://arxiv.org/html/2603.26137) | snapshot 경계, future artifact 금지, prompt 고정, paired comparison을 그대로 검증 규칙 후보로 삼는다. | preprint의 baseline-only/patch-localization 결과를 진단 성과로 전용하지 않는다. 한 repository의 과거 code가 이미 모델 학습에 있었을 가능성은 남는다. |
| **FACT** | inter-dataset code duplication 연구는 서로 다른 code dataset에 중복 sample이 있으며 fine-tuning/evaluation leakage가 validity를 위협한다고 분석한다. [원문](https://arxiv.org/html/2401.07930) | exact hash만이 아니라 clone·fork·template·shared-history 단위 dedup과 group split이 필요하다. | 사용 가능한 pretraining corpus가 없는 closed model의 오염 부재를 자동 증명할 수는 없다. |
| **FACT** | 실세계 performance issue data package는 Java/Python/C++ tab, issue ID, root-cause와 resolution annotation 설명을 제공한다. [Zenodo record](https://zenodo.org/records/6383167) | Python performance case를 수동 재구성하고 taxonomy/sampling frame을 만드는 후보이다. | issue spreadsheet 자체는 executable benchmark가 아니며 공개 API metadata에 license field가 없다. 원 project license, 재현성, Python subset, severity를 case별 재검증해야 한다. [Zenodo API](https://zenodo.org/api/records/6383167) |
| **FACT** | pyperformance는 real-world whole-application 중심의 Python performance benchmark suite이고 top-level license는 MIT이다. [공식 저장소](https://github.com/python/pyperformance) | 승인된 동적 lane에서 정상 workload에 통제된 regression을 삽입하고 pyperf 비교 규칙을 적용하는 후보이다. | 결함 corpus도 severity gold도 아니다. suite benchmark/dependency별 license와 적용 가능성을 별도 감사한다. system tuning, stability check가 필요하다. [pyperf 방법 문서](https://pyperf.readthedocs.io/en/latest/system.html) |
| **FACT** | CTagger 공개 artifact는 concurrency 관련 여부가 표시된 10,920 bug report를 제공하며 Zenodo license는 CC BY 4.0이다. [artifact](https://github.com/sh-shao/CTagger) · [Zenodo API](https://zenodo.org/api/records/17490237) | concurrency 보고서 검색어·taxonomy·hard negative 후보를 찾는 보조 자료이다. | Python executable code defect corpus가 아니고 report classifier 성능은 code diagnosis 성능이 아니다. gold case로 직접 계산하지 않는다. |
| **FACT** | mutation testing은 equivalent mutant 문제를 갖는다. 2024 연구도 수동 mutant에서 equivalence 판단과 test-based kill 절차를 별도 문제로 다룬다. [원문](https://arxiv.org/html/2404.09241) | 살아남은 mutant를 자동으로 실제 결함이라고 세지 말고, behavior 차이와 plausibility를 판정한 case만 gold로 승격한다. | Java 교육 corpus의 비율을 Python에 전이하지 않는다. synthetic score를 실제 결함 score로 합치지 않는다. |
| **FACT** | mutmut은 Python mutation-testing 도구이며 BSD-3-Clause로 표시된다. [공식 저장소](https://github.com/boxed/mutmut) | operator 구현 후보와 비교 baseline일 뿐 특정 제품을 미리 채택할 근거는 아니다. | 일반 mutation operator가 backend concurrency/performance/transaction 위험의 실제 분포를 대표하지 않는다. |
| **FACT** | NIST TREC 연구는 pooled relevance judgment가 불완전할 때 기존 지표의 취약성을 분석하고 bpref를 제안한다. [원문](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=150469) | 모든 잠재 위험을 열거할 수 없는 real repository에서 unjudged를 곧바로 false positive로 세지 않는다. | bpref도 complete Critical/High inventory를 만들어 주지 않는다. 안전 누락 지표는 완전 inventory가 있는 bounded case에서만 계산한다. |
| **FACT** | FIRST CVSS v4.0은 security vulnerability에 Critical 9.0–10.0, High 7.0–8.9 등 optional qualitative band와 Base/Threat/Environmental metric을 정의한다. [공식 규격](https://www.first.org/cvss/v4-0/specification-document) | security case의 심각도 입력 후보이며 vector와 환경 가정을 보존한다. | CVSS를 correctness/performance/concurrency 전체에 억지로 적용하거나 detector confidence로 사용하지 않는다. |
| **FACT** | ACM SIGSOFT empirical standards는 human participant 연구의 recruitment, informed consent, privacy, data protection, sharing permission을 필수 항목으로 둔다. secondary human data에도 legitimate availability와 provenance 확인을 요구한다. [공식 supplement](https://www2.sigsoft.org/EmpiricalStandards/docs/supplements) | 익명 실제 incident와 human study는 “다운로드 가능”만으로 충분하지 않다. 동의/사용권한/재식별 위험/보관 정책을 기록한다. | 익명화가 재식별 불가능을 자동 보장하지 않는다. 조직+역할+희귀 incident 조합도 위험하다. |
| **FACT** | NIST/SEMATECH handbook은 Latin-square가 treatment 외 두 blocking variable을 다루는 설계임을 설명한다. [공식 handbook](https://www.itl.nist.gov/div898/handbook/pri/section3/pri3321.htm) | 사람 실험의 도구 순서와 case set 순서를 counterbalance하는 후보이다. | Latin square만으로 숙련도, 학습, case 난이도, carry-over가 사라지지 않는다. |
| **FACT** | AI Agents That Matter는 단순 반복 호출이 accuracy를 올릴 수 있어 cost-controlled evaluation이 필요하고, accuracy–cost Pareto와 holdout을 권고한다. [원문](https://arxiv.org/html/2407.01502) | token/call/time 비용을 고정하지 않은 component ablation은 독립 기여 증거가 아니다. | 그 논문의 code-generation 수치는 우리 진단 성능 수치가 아니다. |
| **FACT** | Python Software Quality Dataset은 SonarQube issues/metrics, SZZ, GitHub issue/PR 등을 포함하며 Figshare는 CC BY 4.0과 약 7.4 GB를 표시한다. [공식 API](https://api.figshare.com/v2/articles/25008653) | 규모·baseline output·drift 연구 후보이다. | SonarQube/SZZ 산출물을 독립 검증된 진단 gold로 취급하면 circular evaluation이다. acceptance gold로 보류한다. |

## 재현 가능한 평가 자료 구성

### 1. 세 층의 역할을 분리한다

| 층 | **PROJECT-HYPOTHESIS** 역할 | 포함 조건 | 금지되는 해석 |
|---|---|---|---|
| 공개 실제 결함 | 공개 재현, 회귀, 도구 간 비교, known-positive target recovery | immutable version/DOI, base/fix commit, license/provenance, setup recipe, 독립 재판정 | 공개 점수를 blind/OOD 성능이라고 부르기; patch success를 diagnosis success로 부르기 |
| 합성 mutation | 희귀 defect category의 통제된 감도, 경계조건, multi-fault 상호작용 | AST-aware 변이, operator ID, 원본과 변이 diff, 사람 plausibility 판정, 승인 후 behavior 차이 증명 | mutant kill/발견률을 실제 결함 발생분포나 운영 정확도로 합치기 |
| 익명 실제 사례 | 운영 severity/ranking, contamination-resistant acceptance, human utility | 적법한 custodian 권한, sampling frame, redaction log, sealed snapshot, 독립 gold, access log | 성공 사례만 편의 추출; “익명”이라는 이유로 consent/license/privacy 검토 생략 |

**PROJECT-HYPOTHESIS** — 세 층의 결과는 먼저 각각 공개하고, defect type과 scan mode까지 층화한다. 하나의 headline을 요구할 때만 target deployment 모집단에서 관측한 strata 비율과 case-selection probability로 사전 등록한 가중치를 사용한다. synthetic/public 점수가 private-real 부진을 상쇄하지 못하도록 private-real과 Critical/High gate는 별도 필수 조건으로 둔다.

### 2. case manifest의 구현 가능한 최소 필드

**PROJECT-HYPOTHESIS** — 모든 case를 immutable manifest row로 만들고, 평가 전에 manifest와 gold의 cryptographic hash를 봉인한다.

```text
case_id, corpus_name, corpus_version, source_kind(public_real|synthetic|private_real)
repo_id, repo_family_id, base_commit, fix_commit_or_null
code_first_public_at, issue_created_at, fix_merged_at, snapshot_cutoff_at
python_version, framework_tags, defect_domain(correctness|performance|concurrency)
defect_subtype, affected_paths, allowed_static_inputs
dynamic_recipe_id_or_null, execution_policy(static_only|approved_dynamic)
license_id, upstream_license_ids, provenance_url, redistribution_scope
contamination_status(known_exposed|searched_no_match|private_unexposed|unknown)
redaction_profile, template_id_or_null, operator_id_or_null
gold_version, gold_completeness(target_only|topk_judged|bounded_complete)
```

- **FACT** — public availability와 legitimate availability는 다르며 secondary human data의 provenance·permission·privacy를 확인해야 한다. [ACM 공식 지침](https://www2.sigsoft.org/EmpiricalStandards/docs/supplements)
- **PROJECT-HYPOTHESIS** — code 공개일, issue 공개일, fix 공개일을 하나로 뭉개지 않는다. 모델이 오래된 base code를 보았지만 새 issue/fix는 못 보았을 수 있기 때문이다.
- **PROJECT-HYPOTHESIS** — license가 없으면 “all rights reserved/법무 확인 필요” 상태로 두고 재배포 corpus에 넣지 않는다. GitHub에서 읽을 수 있다는 사실은 재사용 license가 아니다.

### 3. repository-family leakage와 중복 통제

**PROJECT-HYPOTHESIS** — `repo_family_id`는 단순 repository 이름이 아니라 아래 중 하나라도 충족하면 같은 family로 union한다.

1. Git fork network 또는 공통 Git ancestry가 확인됨.
2. upstream/downstream package lineage, rename, mirror 관계임.
3. vendored/generated code, tutorial/template scaffold를 공유함.
4. exact file/blob hash, token winnowing/MinHash, AST subtree clone이 임계치 이상 겹침.
5. 동일 issue의 backport/cherry-pick/port이거나 같은 fix가 여러 dataset에 중복됨.

이 통제의 외부 근거는 inter-dataset duplicate가 code-model 평가 validity를 위협한다는 2024 연구다. [원문](https://arxiv.org/html/2401.07930)

- **PROJECT-HYPOTHESIS** — exact duplicate를 먼저 제거하고 near-duplicate pair는 사람이 lineage를 판정한다. case split은 row가 아니라 family group으로 수행한다.
- **PROJECT-HYPOTHESIS** — 같은 family의 과거와 미래를 쓰는 **temporal-drift lane**과 family 자체를 holdout하는 **family-OOD lane**을 분리한다. 두 결과를 “OOD” 하나로 합치지 않는다.
- **UNSUPPORTED** — closed model의 학습 corpus가 비공개이면 near-duplicate search에서 match가 없다는 사실만으로 contamination-free라고 선언할 수 없다.

### 4. temporal/OOD split과 오염 상태

**PROJECT-HYPOTHESIS** — 다음 네 evaluation lane을 고정한다.

| lane | train/dev와의 관계 | 목적 | headline 사용 |
|---|---|---|---|
| Public regression | 공개, 오염 가능/known exposed | 재현·회귀·failure analysis | 참고만 |
| Temporal drift | 같은 family, $T_0$ 이후 task/fix; knowledge는 $T_0$ 이전만 | repository evolution 적응 | 별도 표시 |
| Family OOD | family-disjoint, operator/template-disjoint | 일반화 | 후보 비교 핵심 |
| Private prospective | 분석 시작 뒤 봉인된 미공개/제한공개 실제 사례 | contamination-resistant acceptance·human utility | 최종 gate |

- **FACT** — $T_0$ snapshot 이후 artifact를 knowledge construction에서 금지하고 동일 조건 matched comparison을 하는 구체적 방법이 2026 preprint에 제시돼 있다. [원문](https://arxiv.org/html/2603.26137)
- **PROJECT-HYPOTHESIS** — cutoff 주변에는 purge gap을 두고, PR diff/review comment/new test/future docs/cache/index를 모두 금지한다. prompt 생성자가 gold diff를 보았다면 prompt leakage review를 별도로 통과시킨다.
- **PROJECT-HYPOTHESIS** — 각 model/tool에 model ID, provider revision, claimed knowledge cutoff, evaluation date, fine-tune/retrieval corpus disclosure, 공개 case exact/near match 결과를 기록한다. 미공개 항목은 `unknown`이지 `clean`이 아니다.
- **PROJECT-HYPOTHESIS** — hidden case, label, reviewer note를 일반 prompt log·telemetry·vendor retention 경로에 보내지 않는다. 허용된 endpoint와 retention setting을 manifest에 남긴다.
- **FACT** — SWE-bench-Live의 freshness는 유용한 실제 선례지만 공개 후에는 지속적인 blind holdout이 아니다. [원문](https://arxiv.org/html/2505.23419v2)

### 5. template 단서와 synthetic mutation

**PROJECT-HYPOTHESIS** — synthetic suite는 production-like held-out Python backend snapshot에서 만들고 operator family도 train/dev/test 사이에 일부 holdout한다. 초기 operator 후보는 다음과 같지만 실제 defect taxonomy와 소스 envelope가 확정되기 전에는 채택하지 않는다.

- correctness: 비교 경계 변경, truthiness/None 혼동, 잘못된 exception 범위, rollback/cleanup 누락, cache invalidation 삭제, pagination/limit off-by-one.
- async/concurrency: `await` 삭제, task 취소/정리 누락, lock 범위 축소, shared state의 check-then-act 분리, timeout propagation 삭제.
- performance: hot loop 안의 반복 I/O/query, 불필요한 materialization/copy, cache bypass, bounded batch 제거.

각 mutant는 다음 gate를 모두 통과해야 한다.

1. **정적 생성 gate**: AST가 유효하고 한 operator의 의도된 변경만 포함한다.
2. **단서 gate**: 파일명, 주석, 변수명, diff 크기, 고정 literal 등 template-only predictor로 쉽게 분류되지 않는다.
3. **plausibility gate**: 두 독립 Python reviewer가 실제 change review에서 생길 법한 결함으로 판단한다.
4. **behavior gate**: 정책 승인 뒤 원본은 pass하고 mutant는 의도한 관찰가능 동작/성능/concurrency oracle을 위반한다. flaky하거나 equivalent/unknown이면 제외한다.
5. **split gate**: 같은 base function, template, generated variant가 서로 다른 split으로 가지 않는다.

- **FACT** — equivalent mutant는 여전히 별도 판정이 필요한 문제다. [2024 원문](https://arxiv.org/html/2404.09241)
- **PROJECT-HYPOTHESIS** — 승인 전에는 1–3만 수행할 수 있고 case 상태를 `pending_behavior_validation`으로 둔다. 그런 case는 gold나 KPI 분모에 넣지 않는다.
- **PROJECT-HYPOTHESIS** — one-fault case는 감도, multi-fault case는 finding suppression과 ranking interaction을 측정하며 점수를 분리한다.
- **PROJECT-HYPOTHESIS** — source-preserving rename/reformat/control-flow equivalent variant를 짝지어 prediction 일관성을 측정한다. 이 metamorphic variant는 진짜 결함 gold를 대체하지 않고 template shortcut 진단에만 쓴다.

## 정답(gold), 심각도, 순위 label

### 1. 한 patch를 완전한 gold로 보지 않는다

**FACT** — HaPy-Bug은 bug-fix commit에서 실제 fix line 외 documentation/test/refactoring이 섞인 tangled change를 보여 주며, dataset selection 기준에 따라 label 분포가 달라진다. [원문](https://arxiv.org/html/2504.04810v1)

**PROJECT-HYPOTHESIS** — gold의 단위는 exact text나 patch가 아니라 `hazard_id`이다. 다음을 함께 저장한다.

```text
hazard_id
validity: confirmed | likely | not_a_defect | indeterminate
root_cause_concept
observable_failure_or_risk
acceptable_location_set
acceptable_evidence_set
severity: critical | high | medium | low
severity_basis: impact, exposure, likelihood, affected_asset/SLO
confidence_in_gold
verification_state: incident_observed | dynamically_reproduced | statically_proven | expert_supported
ranking_relevance: 0..3
source_anchor: issue/incident/test/profile/fix links
```

- 여러 위치·표현이 같은 hazard를 설명하면 한 finding으로 match한다.
- output이 patch와 같은 line을 지목해도 원인·영향이 틀리면 match가 아니다.
- patch와 다른 위치를 지목해도 같은 root cause와 영향 경로를 충분한 근거로 설명하면 blind adjudication 대상이다.
- 판정자는 system 이름, arm, 순위, patch generation 성공 여부를 보지 않는다.

### 2. severity, confidence, priority를 분리한다

- **FACT** — CVSS v4.0 band는 security vulnerability를 위한 optional qualitative rating이다. [공식 규격](https://www.first.org/cvss/v4-0/specification-document)
- **PROJECT-HYPOTHESIS** — security case만 CVSS vector를 보조 입력으로 쓴다. 일반 correctness/performance/concurrency는 실제 사용자/데이터/가용성 영향, 도달 가능성·노출, 발생 가능성, 회복 가능성, SLO/금전 영향으로 rubric을 만든다.
- **PROJECT-HYPOTHESIS** — `severity`는 발생했을 때의 위험, `evidence confidence`는 진단이 맞을 확률/근거 강도, `action priority`는 현재 조직에서 검토할 순서다. detector raw score와 셋을 같은 필드로 쓰지 않는다.
- **PROJECT-HYPOTHESIS** — Critical/High label은 독립 reviewer 2명 이상이 blind로 부여하고 불일치는 제3 adjudicator가 해결한다. 원 label, 근거, disagreement, 최종 label을 모두 보존하고 agreement를 보고한다.
- **UNSUPPORTED** — 일반 Python code-health의 Critical/High 경계값은 아직 프로젝트 SLO·data classification·blast radius가 없으므로 수치로 확정할 수 없다.

### 3. incomplete gold를 두 평가 문제로 나눈다

#### A. known-target recovery

**PROJECT-HYPOTHESIS** — BugsInPy/PyBugHive/HaPy-Bug처럼 하나의 알려진 결함이 있는 case에서는 `target hazard를 top-K 안에서 찾았는가`, first-hit rank, 진단 일치도를 계산한다. 다른 output은 독립 판정 전까지 false positive로 세지 않는다. 이 score를 “repository 전체 recall”이라고 부르지 않는다.

#### B. open-world risk ranking

**PROJECT-HYPOTHESIS** — 모든 후보 system, baseline static tool, reviewer search에서 나온 finding의 union을 pool로 만들고 중복 hazard를 합친 뒤 blind adjudication한다. 각 평가 arm의 top-K는 반드시 전부 판정한다. 새 arm이 추가되면 그 top-K를 먼저 판정하고 frozen judgment version을 올린다.

- 판단된 top-K에서는 `Precision@K`를 계산할 수 있다.
- complete bounded inventory가 없는 repo에서는 전체 recall을 계산하지 않는다.
- 불완전 pooled rank에는 `bpref`를 primary로 쓰고 judged pool의 nDCG@K는 descriptive로 표시한다. NIST의 근거는 [여기](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=150469)다.
- Critical/High recall과 miss count는 reviewer가 bounded slice 전체를 감사했거나 synthetic/incident inventory가 완전한 `bounded_complete` case에서만 계산한다.
- `indeterminate`를 억지로 정답/오답에 넣지 않고 수와 비율, 민감도 범위를 별도 보고한다.

**PROJECT-HYPOTHESIS** — reviewer에게 system이 생성한 patch를 보여 주지 않는다. 패치의 그럴듯함이 진단 판정을 오염시킬 수 있기 때문이다.

## 지표와 통계 판정

### 필수 scorecard

**PROJECT-HYPOTHESIS** — 각 stratum, repository family, scan mode별로 아래를 함께 낸다.

| 영역 | 지표 | 해석 규칙 |
|---|---|---|
| 안전 누락 | `Critical miss count`, `High miss count`, `Recall_C`, `Recall_H`, `Recall_C∪H` | `bounded_complete`만. 0 miss여도 신뢰구간 상한을 함께 제시하며 “위험 0”으로 쓰지 않음 |
| 상단 정확도 | `Precision@5/10/20`, invalid finding count | top-K 전수 판정 뒤 계산 |
| 순위 | `bpref`, `nDCG@K`, first relevant rank, first Critical/High rank | incomplete pool은 bpref primary; nDCG는 judged 범위 명시 |
| 진단 품질 | root-cause/impact/location/evidence 각각의 match rate | patch/text exact match 금지, blind rubric 사용 |
| calibration | confidence band별 empirical validity, Brier/ECE 후보 | 충분한 sample 뒤 적용; severity calibration과 혼동 금지 |
| 효율 | wall time, input/output tokens, model/tool calls, peak memory, dollar cost snapshot | accuracy와 Pareto로 같이 보고 가격 기준일 보존 |
| 안정성 | seed 간 variance, metamorphic consistency, run failure/timeout | retry 성공만 선택 보고 금지 |
| 사람 효용 | 제한시간 내 올바른 action률, time-to-correct, Critical/High escalation recall, workload | 속도와 정확도를 반드시 함께 보고 |

nDCG를 쓸 때 ranking relevance $rel\in\{0,1,2,3\}$의 의미를 사전 등록하고

$$DCG@K=\sum_{i=1}^{K}\frac{2^{rel_i}-1}{\log_2(i+1)},\qquad nDCG@K=DCG@K/IDCG@K$$

로 계산한다. **PROJECT-HYPOTHESIS** — severity를 그대로 relevance로 복사하지 않고 실제 action priority rubric으로 판정한다. 그렇지 않으면 잘못된 확신의 Critical finding이 순위 점수를 과도하게 지배한다.

### 집계·불확실성

- **PROJECT-HYPOTHESIS** — case를 IID로 두지 않는다. repository family를 resampling unit으로 한 cluster bootstrap 95% CI와 family별 raw 결과를 함께 낸다.
- **PROJECT-HYPOTHESIS** — stochastic system은 동일한 사전 등록 seed set으로 paired run하고 seed를 독립 case처럼 표본수를 부풀리지 않는다.
- **PROJECT-HYPOTHESIS** — macro-by-family와 micro 결과를 모두 내되 release gate는 대형 repo가 지배하지 않는 macro와 Critical/High miss를 우선한다.
- **PROJECT-HYPOTHESIS** — component가 여러 개면 효과크기와 CI를 우선하고 다중 비교 보정 계획을 사전 등록한다. $p$-value 하나로 승격하지 않는다.
- **PROJECT-HYPOTHESIS** — exact 최소 효과, non-inferiority margin, Critical/High 허용 누락 수는 운영 비용·review capacity·SLO가 정해진 후 pilot과 함께 결정한다. 지금 임의 수치를 만들지 않는다.

## same-budget ablation과 핵심 경로 기여 검증

### 고정해야 할 것

**PROJECT-HYPOTHESIS** — full system과 `full − component X`를 같은 case에서 paired 비교한다. 다음 필드는 arm 사이 동일해야 한다.

- repository snapshot, allowed files/history/docs, prompt와 output schema.
- model/provider revision, temperature/seed set, context window.
- 최대 input/output token, model/tool call, retry, wall-clock, hardware quota.
- static-only 또는 approved-dynamic 권한; test/profile 결과를 한 arm만 보는 비교 금지.
- 캐시의 warm/cold 상태와 사전 index build accounting.
- 판정 gold version과 reviewer pool.

`same-budget`은 최대치를 같게 한다는 뜻이며 제거 arm에 무의미한 padding 호출을 강제하지 않는다. 실제 소비 token/call/time/cost도 공개하고 accuracy–cost Pareto를 함께 본다. 반복 호출이 accuracy를 올릴 수 있어 cost control이 필요하다는 근거는 [AI Agents That Matter](https://arxiv.org/html/2407.01502)다.

### 비교 arm

1. `current-practice baseline`: 현재 사람이 받는 원자료/기존 static output.
2. `static core`: 승인 없는 자동 정적 읽기만.
3. `static core − X`: 주장하는 각 핵심 component의 제거 arm.
4. `approved dynamic`: 동일 static 입력에 정책 승인된 test/profiler evidence만 추가.
5. `experimental`: 최신 기능. production ordering과 기본 KPI에서 물리적으로 분리.

**PROJECT-HYPOTHESIS** — X의 핵심 기여를 인정하려면 사전 등록한 primary metric에서 paired 개선 CI가 최소효과를 넘고, Critical/High recall의 one-sided non-inferiority와 비용 cap을 동시에 통과해야 한다. 한 public corpus, 한 seed, patch pass, vendor claim, aggregate 평균만으로 승격하지 않는다.

**PROJECT-HYPOTHESIS** — 정기 기준 브랜치와 release-candidate 점검은 같은 gold schema를 쓰되 별도 profile로 보고한다. 기준 브랜치는 전체 추세·새 위험 유입, RC는 changed-path와 Critical/High 누락 gate를 강조한다. 두 profile의 실제 weighting/threshold는 repository 규모와 release 정책이 정해질 때 결정한다.

## 사람 의사결정 시간 연구

### 연구 질문과 endpoint

**PROJECT-HYPOTHESIS** — 질문은 “도구가 빨랐는가”가 아니라 “reviewer가 같은 제한시간 안에 더 정확히 위험을 처리했는가”이다.

- Primary 1: Critical/High case에서 `escalate / investigate / defer / dismiss` 중 올바른 action을 내릴 때까지의 시간.
- Primary 2: time cap 내 올바른 action 비율과 Critical/High escalation recall.
- Secondary: false escalation, first-Critical 확인 시간, confidence calibration, abandonment, NASA-TLX 같은 workload 후보.
- time cap에서 미해결이면 빠른 오답으로 바꾸지 않고 right-censored/미해결로 기록한다.

### 설계

1. 참여자의 Python/backend 경력과 대상 framework 익숙함을 층화한다.
2. 별도 training case로 UI를 익히고 본 case를 미리 노출하지 않는다.
3. `current-practice`와 `risk-priority-table`의 randomized within-subject crossover를 사용하되 같은 결함을 두 번 보여 주지 않는다.
4. 난이도·domain이 맞는 case set을 만들고 treatment 순서와 set 순서를 Latin-square/blocked randomization으로 counterbalance한다. Latin-square의 공식 근거는 [NIST handbook](https://www.itl.nist.gov/div898/handbook/pri/section3/pri3321.htm)이다.
5. repository docs, 검색, 실행권한, time cap을 condition 간 동일하게 한다. risk table이 더 많은 evidence를 받는다면 그 차이를 별도 treatment로 둔다.
6. UI는 숨길 수 없지만 outcome adjudicator와 analyst는 condition/system identity를 blind 처리한다.
7. participant와 case를 random effect로 다루는 분석 후보를 사전 등록하고 pilot variance로 sample size/power를 계산한다. 임의 참여자 수를 지금 확정하지 않는다.
8. correctness와 time을 공동 보고한다. median time만 좋아지고 정확도가 나빠지면 성공이 아니다.

### 윤리·익명성

- **FACT** — recruitment, compensation/coercion, informed consent, privacy, data protection, future sharing permission은 human study의 필수 보고 항목이다. [ACM 공식 지침](https://www2.sigsoft.org/EmpiricalStandards/docs/supplements)
- **PROJECT-HYPOTHESIS** — 실무자의 개인 성과평가 자료로 재사용하지 않으며 participant ID와 조직 incident ID의 mapping은 연구 결과와 분리 보관한다.
- **PROJECT-HYPOTHESIS** — private case는 조직/고객/서비스/희귀 stack 조합으로 재식별될 수 있으므로 field-level redaction과 공격적 재식별 review를 한다. 두 treatment에 동일한 redaction을 적용한다.
- **UNSUPPORTED** — 참여자 수, 숙련도 분포, IRB/사내 윤리심사 경로, 보상, 연구기간은 아직 정해지지 않았다.

## 시스템 설계에 주는 함의

1. **PROJECT-HYPOTHESIS — output schema가 평가 가능해야 한다.** 각 finding에 stable ID, hazard/root-cause, impact, locations, evidence provenance, severity, confidence, action priority, static/dynamic verification state, suppress/duplicate relationship을 내보낸다. 자유문장 하나만 내면 hazard dedup과 rank adjudication을 재현할 수 없다.
2. **PROJECT-HYPOTHESIS — 검증 상태를 UI와 score에서 분리한다.** 정책 승인 전 performance/concurrency 의심은 `static-supported`이지 `dynamically-confirmed`가 아니다. 승인 거부도 실패가 아니라 `not_authorized` outcome으로 기록한다.
3. **PROJECT-HYPOTHESIS — 두 scoreboard를 둔다.** 모든 repository에 가능한 static-only와 승인된 case만의 static+dynamic을 나눈다. 서로 다른 권한의 성능을 같은 leaderboard에서 비교하지 않는다.
4. **PROJECT-HYPOTHESIS — evidence ledger가 필요하다.** source blob/commit, analyzer/model version, prompt hash, policy decision, run seed, tool call/token/time, gold version, adjudication version을 append-only로 남긴다.
5. **PROJECT-HYPOTHESIS — ranking과 detector confidence를 decouple한다.** 낮은 confidence라도 blast radius가 큰 위험은 검토 후보일 수 있고, 높은 confidence의 style issue가 Critical보다 위로 가서는 안 된다.
6. **PROJECT-HYPOTHESIS — incomplete gold를 제품 학습 신호로 자동 환류하지 않는다.** `unjudged`를 negative로 학습하면 새 유형을 억압한다. human-confirmed outcome만 provenance와 함께 사용한다.
7. **PROJECT-HYPOTHESIS — public benchmark adapter는 acceptance corpus와 분리한다.** 공개 case ID/patch가 prompt에 들어가는 regression mode와 blind repository scan mode를 동일 점수로 섞지 않는다.
8. **PROJECT-HYPOTHESIS — experimental feature는 별도 namespace/index/output channel을 쓴다.** core ranking을 바꾸거나 기본 KPI 분모·분자에 들어가기 전에 same-budget ablation과 private prospective gate를 통과한다.
9. **FACT — vendor/static labels는 독립 gold가 아니다.** Python Software Quality Dataset처럼 SonarQube/SZZ 산출물을 모은 자료는 scale 분석에는 유용하지만 해당 도구 계열을 평가하는 정답으로 쓰면 순환적이다. [공식 metadata](https://api.figshare.com/v2/articles/25008653)
10. **PROJECT-HYPOTHESIS — license/provenance gate가 ingestion 앞에 온다.** 명시 license, upstream code license, redistribution 범위, 개인정보/incident 권한이 없으면 metadata-only pointer로 남기고 corpus를 복제하지 않는다.

## 새 아이디어

1. **PROJECT-HYPOTHESIS — 오염 canary pair**: private real case마다 구조적으로 동등한 rename/reorder variant를 하나 만들고 두 prediction의 hazard/rank 일관성을 비교한다. 원본 성능을 대체하지 않고 memorization/template 단서 경보로 쓴다.
2. **PROJECT-HYPOTHESIS — difficulty가 아닌 evidence budget curve**: 각 case에 static source만, static+history, static+approved tests/profile 순으로 evidence를 추가해 어느 증거가 Critical/High recall과 decision time을 바꾸는지 같은 budget에서 측정한다.
3. **PROJECT-HYPOTHESIS — disagreement-aware gold**: adjudication 전 reviewer label 분포와 `indeterminate`를 보존해 명백한 결함과 본질적으로 논쟁적인 maintainability finding을 분리한다. consensus가 낮은 case만으로 모델을 벌하지 않는다.
4. **PROJECT-HYPOTHESIS — prospective shadow intake**: 향후 실제 review/incident에서 발견된 사례를 결론을 숨긴 채 주기적으로 봉인하고 다음 evaluation window에만 공개한다. 결과를 본 뒤 case를 선택하는 cherry-picking을 막는다.
5. **PROJECT-HYPOTHESIS — rank regret**: system 순위와 인간의 최종 action-priority 순위 차이에서, 특히 Critical/High를 아래로 보낸 손실에 가중치를 주는 보조 지표를 연구한다. 정의·가중치는 아직 미확정이므로 기본 KPI가 아니다.
6. **PROJECT-HYPOTHESIS — reviewer-time Pareto**: model 비용뿐 아니라 top-K를 판정하는 인간 minutes를 cost 축에 포함한다. finding을 많이 내서 recall을 높이는 방식이 실제 triage capacity를 소모하는지 드러낸다.
7. **PROJECT-HYPOTHESIS — operator-family holdout**: synthetic test에서 코드 family뿐 아니라 mutation operator/template family도 holdout해 익숙한 변이 문법 탐지를 일반 결함 이해로 오인하지 않는다.

## 기각/보류 아이디어

| 상태 | 아이디어 | 이유 |
|---|---|---|
| 기각 | SWE-bench patch pass를 진단 정확도의 primary KPI로 사용 | issue resolution/repair이지 위험 발견·severity·ranking이 아니다. [dataset card](https://huggingface.co/datasets/princeton-nlp/SWE-bench/raw/main/README.md) |
| 기각 | SonarQube/SZZ/vendor label을 그대로 gold로 사용 | 평가 대상과 gold가 같은 규칙/휴리스틱 계보를 공유하는 circularity가 생긴다. [자료 설명](https://api.figshare.com/v2/articles/25008653) |
| 기각 | unjudged finding을 모두 false positive로 처리 | incomplete gold에서 새롭고 유효한 finding을 벌한다. [NIST TREC](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=150469) |
| 기각 | row-random split | fork, shared history, template, duplicate fix가 양쪽에 퍼져 repository-family leakage가 생긴다. [중복 연구](https://arxiv.org/html/2401.07930) |
| 기각 | 합성 mutation 점수를 실제 incident 점수와 단일 평균 | equivalent/unrealistic mutant와 실제 발생분포 차이를 숨긴다. [equivalent mutant 연구](https://arxiv.org/html/2404.09241) |
| 기각 | 동적 evidence arm과 static-only arm을 같은 권한인 것처럼 비교 | component 효과와 실행권한/추가 evidence 효과가 confound된다. |
| 기각 | 평균 nDCG 하나로 release gate | Critical/High 누락을 다수의 낮은 위험 정렬 성공으로 상쇄할 수 있다. |
| 기각 | 제거 component의 절약 예산을 더 많은 retry에 재할당하고 “동일 ablation”이라 부르기 | component와 inference budget 두 요인이 함께 바뀐다. cost control 필요성은 [이 연구](https://arxiv.org/html/2407.01502)가 뒷받침한다. |
| 보류 | CTagger corpus를 Python concurrency gold로 직접 사용 | report classification corpus이며 Python executable code diagnosis gold가 아니다. [artifact](https://github.com/sh-shao/CTagger) |
| 보류 | 실세계 performance spreadsheet를 즉시 executable benchmark로 사용 | Python subset reconstruction, source license, environment, oracle, 현재 재현성을 case별 확인해야 한다. [Zenodo](https://zenodo.org/records/6383167) |
| 보류 | mutmut 제품 채택 | BSD-3-Clause Python 후보지만 실제 operator coverage, Python version, backend taxonomy 적합성을 비교하지 않았다. [공식 저장소](https://github.com/boxed/mutmut) |
| 보류 | rank-regret를 primary KPI로 승격 | business cost weight와 reviewer agreement 자료가 아직 없다. |

## 미해결 질문

1. **UNSUPPORTED** — 대상 repository의 실제 framework, async/multiprocess/native-extension, 규모, CI 재현성, 성능 SLO 분포는 무엇인가?
2. **UNSUPPORTED** — Critical/High의 조직별 impact·likelihood·blast-radius rubric과 허용 miss/non-inferiority margin은 무엇인가?
3. **UNSUPPORTED** — 익명 실제 사례를 몇 건, 어떤 sampling frame으로 확보할 수 있으며 custodian consent, redaction fidelity, 재식별 review, 심사 반출 범위는 무엇인가?
4. **UNSUPPORTED** — 독립 gold annotator와 human-study participant의 수·숙련도·시간, 제3 adjudicator, 윤리심사 경로는 무엇인가?
5. **UNSUPPORTED** — Python-specific, executable, 재배포 license가 명확한 concurrency case corpus가 추가로 존재하는가? 이번 조사에서는 확정하지 못했다.
6. **UNSUPPORTED** — performance corpus의 Python issue가 현재 interpreter/dependency에서 재현되는 비율과 안정적인 oracle은 무엇인가?
7. **UNSUPPORTED** — 모델/provider가 private case를 보존·학습하지 않는다는 계약·기술 통제가 가능한가? 불가능하면 on-prem/retention-disabled 경로가 필요한가?
8. **UNSUPPORTED** — 정기 기준 브랜치와 RC의 실제 Git topology, changed-path 정의, force-push/rebase, baseline artifact 보존 방식은 무엇인가?
9. **UNSUPPORTED** — reviewer가 실제로 한 회차에 검토 가능한 K와 time cap은 얼마인가? Precision@K의 K는 이 capacity study 뒤 확정해야 한다.
10. **UNSUPPORTED** — 심사자가 live demo, sealed replay, 제한 열람 private evidence 중 무엇을 인정하는가?

## 출처

### 최신/핵심 원문과 공식 자료

1. Zhu et al., **From Bugs to Benchmarks: A Comprehensive Survey of Software Defect Datasets**, arXiv v3, 2026-02-10. <https://arxiv.org/html/2504.17977>
2. Przymus et al., **HaPy-Bug – Human Annotated Python Bug Resolution Dataset**, 2025. <https://arxiv.org/html/2504.04810v1>
3. HaPy-Bug Figshare official metadata/license. <https://api.figshare.com/v2/articles/24448663>
4. Antal et al., **BugsInPy**, 2024 arXiv version. <https://arxiv.org/html/2401.15481>
5. BugsInPy official repository. <https://github.com/soarsmu/BugsInPy>
6. PyBugHive official site and repository. <https://pybughive.github.io/> · <https://github.com/pybughive/pybughive>
7. SWE-bench official dataset card. <https://huggingface.co/datasets/princeton-nlp/SWE-bench/raw/main/README.md>
8. Zhang et al., **SWE-bench Goes Live!**, 2025. <https://arxiv.org/html/2505.23419v2>
9. Sun et al., **A Time-Consistent Benchmark for Repository-Level Software Engineering Evaluation**, 2026 preprint. <https://arxiv.org/html/2603.26137>
10. Hernández López et al., **On Inter-dataset Code Duplication and Data Leakage in Large Language Models**, 2024. <https://arxiv.org/html/2401.07930>
11. Liu et al., **A Large-Scale Empirical Study of Real-Life Performance Issues in Open Source Projects**, replication package. <https://zenodo.org/records/6383167>
12. Python pyperformance official repository. <https://github.com/python/pyperformance>
13. pyperf system-stability guidance. <https://pyperf.readthedocs.io/en/latest/system.html>
14. Shao et al., **Identifying Concurrency Bug Reports via Linguistic Patterns**, 2026. <https://arxiv.org/html/2601.16338v1>
15. CTagger artifact and official dataset metadata. <https://github.com/sh-shao/CTagger> · <https://zenodo.org/api/records/17490237>
16. Straubinger et al., **An Empirical Evaluation of Manually Created Equivalent Mutants**, 2024. <https://arxiv.org/html/2404.09241>
17. mutmut official repository/license. <https://github.com/boxed/mutmut>
18. Buckley & Voorhees, **Retrieval Evaluation with Incomplete Information**, NIST/TREC. <https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=150469>
19. Kapoor et al., **AI Agents That Matter**, 2024. <https://arxiv.org/html/2407.01502>
20. ACM SIGSOFT **Empirical Standards** and ethics supplements. <https://www2.sigsoft.org/EmpiricalStandards/> · <https://www2.sigsoft.org/EmpiricalStandards/docs/supplements>
21. NIST/SEMATECH e-Handbook, **Latin square and related designs**. <https://www.itl.nist.gov/div898/handbook/pri/section3/pri3321.htm>
22. FIRST, **CVSS v4.0 Specification Document**. <https://www.first.org/cvss/v4-0/specification-document>
23. Python Software Quality Dataset official Figshare metadata. <https://api.figshare.com/v2/articles/25008653>

### 오래됐지만 여전히 쓰이는 공식 원리

24. NIST SP 800-30 Rev.1, **Guide for Conducting Risk Assessments** (risk assessment가 의사결정에 필요한 정보를 제공한다는 공식 기준; 최신 dataset 권고가 아니라 risk 원리로만 사용). <https://csrc.nist.gov/pubs/sp/800/30/r1/final>

## 최종 판단

- **FACT** — 재현 가능한 공개 Python correctness 후보와 수동 line annotation 후보는 존재한다. performance issue 자료와 workload suite도 존재하지만 서로 다른 목적과 완성도를 가진다. [HaPy-Bug](https://arxiv.org/html/2504.04810v1) · [BugsInPy](https://arxiv.org/html/2401.15481) · [performance package](https://zenodo.org/records/6383167) · [pyperformance](https://github.com/python/pyperformance)
- **PROJECT-HYPOTHESIS** — 후속 결정 티켓은 특정 dataset/tool을 단독 채택하지 말고, 위의 세 층 corpus, family+temporal split, incomplete-gold protocol, Critical/High gate, same-budget paired ablation, randomized human study를 하나의 검증 계약으로 확정해야 한다.
- **UNSUPPORTED** — 현재 repository 문서만으로 어느 제품·모델·graph·agent가 진단 성능, Critical/High recall, 사람 결정 시간에서 우월하다고 결론 낼 수 없다. 이 문서의 후보와 방법은 실행 계획의 입력이지 실행 증적이 아니다.
