# AI Professional Lv3 심사 기준 분석 및 A+ 달성 전략

- 과제: AI 기반 코드 품질·성능 리스크 진단 에이전트
- 기준 문서: [`project-context/ai-professional-evaluation-criteria.md`](project-context/ai-professional-evaluation-criteria.md)
- 기획 문서: [`project-context/ai-professional-project-proposal.md`](project-context/ai-professional-project-proposal.md)
- 문서 상태: 강한 `gpt-6-sol` 대 작은 `gpt-6-luna`의 최종 동결 비교와 동일 작은 모델 6군을 구분한다. 공개 Starlette 수정 전/후의 새 프롬프트 승인 진단에서 알려진 EOF 원인의 수정 전 강한 모델 임시 접수 1건은 정확한 읽기 루프를 가리켰고, 작은 모델은 같은 원인의 중복 후보 2건을 다른 줄에 접수했으며 한 관점이 실패했다([원자료·판정 한계](evidence/04-public-as-is-to-be-comparison.md#수정된-프롬프트-소유자-승인-후-네-건-실제-진단)). 공개 개발 사례이므로 실행 확인·독립 정답·최종 품질/비용 비교는 없다.

## 1. 결론

A+의 근거는 “LLM이 코드를 잘 읽는다”가 아니다. 다음 계층의 독립 기여를 같은 예산의 비교 실험으로 입증해야 한다.

1. **결정론적 구조 계층**: Python 3.14 AST, 심볼, CFG, 호출·의존 그래프로 저장소 사실을 추출한다.
2. **선택적 실행 계층**: 승인된 focused test와 profiler로 정적 가설을 확인·기각한다.
3. **AI 추론 계층**: 다관점 에이전트가 구조·실행 증거 사이의 위험 인과를 제안하고 반대 검토를 수행한다.
4. **평가 계층**: 실행 결과, 전체 trace, 비용, 실패 경로를 저장해 각 최적화의 효과를 분리한다.

“거의 최적”은 무제한 기술 전체에 대한 주장이 아니다. 사전 등록한 후보 집합과 안전·비용·Recall 제약 안에서 측정된 Pareto frontier에 오른 구성에만 사용한다.

## 2. 문제 정의

### 2.1 해결 대상

- 여러 파일에 걸친 책임·의존성 문제
- 예외 경로와 상태 전이에서 발생하는 버그
- 반복 I/O, 호출 증폭, CPU·메모리 병목
- `async`/스레드/프로세스 경계의 동시성 위험
- 위험 경로를 방어하지 못하는 테스트 공백

### 2.2 범위 밖

- 모든 언어를 지원하는 범용 분석 플랫폼
- 운영 프로세스에 승인 없이 붙는 profiler
- 자동 코드 수정·배포
- LLM 판단만으로 성능 병목을 확정하는 기능
- 일반 인프라 상세 설계

### 2.3 핵심 제약과 대응

| 제약 | 실패 위험 | 설계 대응 |
| --- | --- | --- |
| 저장소가 모델 문맥보다 큼 | 호출자·테스트 누락 | lexical anchor + bounded Code Graph 확장 |
| 정적 코드로 런타임 비용 확정 불가 | 성능 환각 | focused test/profiler로 가설 상태 전환 |
| profiler의 시간·권한·상태 비용 | 과다 실행 | 결정론적 초기 router + opt-in + 실행 정책 |
| LLM 비결정성 | 재현성 저하 | 구조화된 Finding, 증거 gate, 반복 trial |
| 멀티 에이전트의 추가 계산량 | 비용으로 얻은 품질 향상 | 모든 LLM 호출을 포함한 run-level 예산 |
| 정적 해석의 동적 호출 누락 | 잘못된 그래프 경로 | unresolved 보존, 실행 증거 또는 abstain |

## 3. 기준선 실패 지점

현재 비교군 간 일반적인 품질·효과는 최종 자료에서 측정되지 않았다. Prefect 공개 결함 1건의 두 개발 경로 모두 결함 0/1이고, 이후 정적 후보는 아직 실제 모델 권고로 이어졌는지 확인하지 못했다. 아래는 추가로 측정할 실패 유형이다.

| 기준선 | 장점 | 실패 지점 | 정량 확인 |
| --- | --- | --- | --- |
| 수작업 리뷰 | 업무 의도 파악 | 탐색 시간·리뷰어 편차 | 전체 의사결정 시간, 일치도 |
| Ruff/Flake8/SonarQube 계열 | 빠른 규칙 검사 | workload와 프로젝트 의도 미관찰 | 규칙 밖 결함 Recall |
| 단일 LLM + 전체 파일 | 자유로운 설명 | 문맥 희석·무근거 인과 | evidence Recall, grounding, tokens |
| BM25/벡터 검색 | 이름·의미 검색 | 구조적으로 연결된 명칭 불일치 코드 누락 | localization Recall@K |
| profiler 항상 실행 | 런타임 증거 상한 | 지연·권한·무효 실행 | 유효 발견당 시간·비용 |
| LLM 자율 도구 호출 | 유연성 | 과다·과소 실행 | trigger P/R, utility, unsafe-run |

## 4. 심사 기준 1:1 공략표

| 평가 항목 | 배점 | A+에 필요한 주장 | 필수 증적 | 실패 판정 |
| --- | ---: | --- | --- | --- |
| 문제 정의 | 10% | 등록 후보 중 제약을 만족하는 Pareto 구성을 선택 | ADR 행렬, 기준선 비교 | 후보·경계·판정 규칙 없음 |
| 성과 지표 | 10% | 6개 KPI의 분모·수집·통계·목표 명확 | KPI 원자료와 신뢰구간 | 목표만 있고 측정식 없음 |
| 제안서 달성 수준 | 10% | fixed-five 기준선·DiagnosisPlan·HypothesisContract·실행 검증·opt-in profiler end-to-end | 정상·fallback·shadow·실행 trace | 기능 일부 미구현 |
| 시스템 완성도 | 10% | 서비스화 가능성을 운영 증거로 입증 | 권한·보존·감사·SLO·복구·소유권 | 데모 또는 내부 재사용만 제시 |
| 기술 이해도 | 20% | 원리·한계·설정·trade-off를 설명 | ADR, 설정 실험 | 제품명·홍보 수치 나열 |
| AI기술 선택 적절성 | 20% | 단순 LLM 대비 AI 계층의 독립 기여 확인 | 같은 예산 ablation | 추가 token 효과와 구조 효과 혼동 |
| 최적화 | 20% | 검색·도구·DAG·gate 전반의 효과가 큼 | 품질/비용 Pareto | 최종 점수만 비교 |

**현재 제출 근거와 미충족 조건:** 아래의 문서·코드는 존재 증거이며, 결과를 실측한 증거로 바꾸지 않는다.

| 공식 세부항목 | 현재 확인 가능한 근거 | A+ 주장 전 미충족 |
| --- | --- | --- |
| 문제 정의 10% | [대안 비교](ai-selection-matrix/01-multi-perspective-diagnosis-adr.md), [지원 범위](../.wayfinder/ai-a-plus-code-health/field-input-manifest.yaml) | 동일 조건 Pareto 결과, 회사 사업·실제 업무 사례 연결 |
| 성과 지표 10% | [분모·목표 계약](evidence/01-kpi-measurement-framework.md), [시험용 입력 검사](../src/modules/evaluation/USAGE.md) | 독립 봉인 80사례 원자료와 실제 결과·불확실성 |
| 제안서 달성 10% | [무인 지표 수정 초안](project-context/ai-professional-project-proposal.md)과 [부분 구현·실행 경계](evidence/03-ai-pipeline-technical-design.md) | 수정본의 심사 접수·수용, 미구현 기능과 승인형 실제 실행 |
| 시스템 완성도 10% | [승인형 실행기의 현재 경계](../src/modules/runtime_exec/USAGE.md) | 서비스 권한·보존·감사·SLO·복구·운영 소유자 검증 |
| 기술 이해도 20% | [그래프](ai-selection-matrix/02-code-context-retrieval-adr.md)·[profiler](ai-selection-matrix/03-profiler-in-the-loop-adr.md) 원리와 제약 | 고정 설정의 실제 실패·왜곡·성능 측정 |
| AI기술 선택 20% | [6군 대조 계획](evidence/02-benchmark-and-ablation-plan.md) | 동일 예산 6군 실행과 관점별 독립 기여 |
| 최적화 20% | [Git 소스 조각 바이트 관찰](evidence/03-ai-pipeline-technical-design.md) | 문맥·토큰·비용·품질을 함께 측정한 개선 효과 |

**추가 실행 점검:** [개발 검증 기록](evidence/03-ai-pipeline-technical-design.md)의 Git·승인 경계와 Starlette 실제 모델 원자료는 개발 증거다. v27 추가 역할의 코드 회귀는 Python 3.12 176개 통과, 3.14 175개 통과·1개 건너뜀이며 실제 모델 품질 실증은 아니다. 후속 [원자료 재검증](evidence/04-public-as-is-to-be-comparison.md#v27-실제-증거-재검증과-추가-역할-비교-승인-준비)에서 Starlette 응답 12개 해시는 일치했으나, 과거 Prefect 실행의 `/tmp` 설정·원자료가 없어 현재 재검증은 불가했다. 모델 원문·임시 접수·독립 확인을 구분하며 재현 불가능한 과거 기록을 현재 제출 가능한 실행 증거로 세지 않는다. 같은 예산 최종 6군, 80개 독립 정답·판정, 실제 API 청구액, 회사 업무·수정 제안서 수용·최종 실행 환경·운영 근거가 없어 A+은 미입증이다.

## 5. 프로젝트 사전 검증 목표(공식 A+ 기준 아님)

아래 목표는 [현행 v30 평가 계약](../.wayfinder/ai-a-plus-code-health/field-input-manifest.yaml)의 무인 평가 기준이며 심사표의 합산 등급 기준이 아니다. 모두 최종 프로젝트 결과로 미측정이다.

| 영역 | 프로젝트 목표 |
| --- | --- |
| 문제 발견률(최우선) | 봉인된 같은 80사례의 모든 결함에서 강한 모델 1회 진단 대비 작은 모델 전체 시스템 Recall 차이의 가족별 bootstrap 95% CI 하한 > 0; 중요 Recall ≥ 0.90, Precision ≥ 0.75, 부당 기각 0건 |
| 20분 내 유효 권고율(기존 6군 기여 관문) | 같은 작은 모델의 일반 LLM(A) 대비 전체 시스템(F) ≥ +30%p, 가족별 bootstrap 95% CI 하한 > 0, F의 Critical/High 부당 기각 0건 |
| 리스크 식별(방어 지표) | 전체 Recall ≥ 0.85, Critical/High Recall ≥ 0.90, Precision ≥ 0.75 |
| 실행 확인 | 사전 선정한 실행 적격 중요 위험의 runtime confirmation rate ≥ 0.70 |
| profiler | 유익하다고 사전 봉인된 사례 coverage ≥ 0.80 |
| 근거 안전 | 최종 무근거 발견률 ≤ 5%, 근거 없는 실행 확인·안전하지 않은 실행 0건 |
| 호출 비용·기계 생산성 | 전체 모델 호출의 실제 API 청구 금액·확인된 결함당 비용과 지연·토큰·도구 시간을 두 방식에서 공개; 비용 우월성은 관찰 전 주장하지 않음 |

이전 제출본의 사람 진단 시간 50% 단축·재작업 30% 감소·리뷰 생산성 목표는 미측정이고 자동 지표로 달성하지 않았다. 사용자가 수정은 허용했으나 [제안서 수정 초안](project-context/ai-professional-project-proposal.md)의 심사 접수·수용은 확인되지 않았다. 회사 업무·사업 사례도 제공할 수 없어 제안서 달성·사업 연결 제한 사항이 남는다. 문맥 바이트 감소는 토큰/비용 절감 증거가 아니며, 우월성은 동일 예산 실제 비교 전까지 주장하지 않는다.

## 6. 시스템 완성도 A+ 운영 증거

일반 인프라 상세 설계는 범위 밖이지만 A+의 “실제 서비스로 사업화 가능한 수준”을 주장하려면 다음 최소 증거가 필요하다.

- 저장소 접근 인증·권한과 tenant/프로젝트 격리
- source/profile/log 보존 기간과 삭제·redaction 정책
- 모든 실행 명령·승인·결과의 감사 기록
- 진단 API/worker의 SLO, timeout, 재시도, 복구 시험
- 모델·도구 장애 시 기능 저하 방식과 rollback
- 운영 소유자, 지원 범위, 배포 경계

이 운영 증거가 없으면 사업화 가능한 A+ 시스템이라고 주장할 수 없다. A급 사내 자산 판정도 실제 내부 활용 증거가 있어야 한다.

## 7. 탈락 방지

| 제한 | 방어 설계 | 확인 자료 |
| --- | --- | --- |
| 업무·회사 사업과 동떨어진 주제 | 실제 업무 흐름·회사 사업에서 쓰는 승인된 사례와 책임자 확인 | 현재 부서·성명·실제 업무 사례 연결 미확보 |
| 단순 LLM 호출 | AST/CFG/Code Graph + runtime feedback | graph/evidence trace |
| 프롬프트만 최적화 | retrieval/router/DAG/gate ablation | 구성 제거 실험 |
| 노코드 조합 | extractor/resolver/pruner/router/normalizer 구현 | source와 실행 증거 |
| 단일 오픈소스 복제 | 과제 고유 schema·policy·gold set | ADR와 benchmark |

## 8. 최신 근거 사용 정책

- 현재 기술 선택 근거는 원칙적으로 2026-02-23 이후 1차 자료를 사용한다.
- 6개월 내 근거가 없을 때만 2025-08-23 이후 자료를 이유와 함께 사용한다.
- 현재 공식 문서·릴리스는 운용 기능 근거로 사용할 수 있다.
- 오래된 논문은 현재 성능·설정 선택에 사용하지 않는다.
- preprint·vendor 수치는 독립 재현 전 프로젝트 성능으로 일반화하지 않는다.
- 내부 번역 자막은 최신 동향을 찾는 2차 영감 자료이며 기술 증명 자료가 아니다.

## 9. 현재 핵심 출처

- [LARGER v1, 2026-05-08](https://arxiv.org/html/2605.16352v1) — lexical anchor와 confidence-filtered graph 확장.
- [Codebase-Memory v1, 2026-03-28](https://arxiv.org/abs/2603.27277v1) — 구조 검색의 token/quality trade-off.
- [To Call or Not to Call v3, 2026-08-06](https://arxiv.org/abs/2605.00737v3) — 필요성·효용·비용의 분리; profiler가 아닌 일반 도구 연구.
- [UCCI v1, 2026-05-11](https://arxiv.org/abs/2605.18796v1) — held-out calibration과 비용 제약; profiler 전이 성능은 미입증.
- [SWE-Perf v2, 2026-07-01 revision](https://arxiv.org/html/2507.12415v2) — 실제 저장소 성능 최적화 평가.
- [REAP v4, 2026-07-28 revision](https://arxiv.org/abs/2604.01527v4), [SWE-EVO v5, 2026-04-04 revision](https://arxiv.org/abs/2512.18470v5), [HackDetect v1, 2026-07-24](https://arxiv.org/abs/2607.22368v1) — 실행 기반·장기·protocol-validity 평가.

## 10. 실제 증거 감사 판정

공식 7개 항목·가중치는 위 원문을 유지한다. 별도 읽기 전용 검토자 두 명이 공식 기준/제안서와 비교 실험의 반증을 각각 검토하고, 주 작업자가 실제 원자료를 대조했다. 이 검토자는 공식 심사위원이나 독립 gold 판정자가 아니며, 내부 제안 등급은 채택하지 않았다. 공식 합산식·종합 A+ cutoff가 없어 종합 점수를 계산하지 않는다.

| 공식 항목 | 현재 방어할 수 있는 증거 범위 | A+ 주장에 부족한 핵심 |
| --- | --- | --- |
| 문제 정의 10% | 문제·제약·대안의 설계 설명 | 실제 업무 연결과 대안이 적합하다는 실증 |
| 성과 지표 10% | 분모·목표·측정 방법의 설계 | 업무 효용·목표 도전성의 근거와 성과 주장용 실제 측정 |
| 제안서 달성 10% | 부분 구현·개발 동작 | 수정 제안서 공식 수용과 모든 약속의 달성 증적 |
| 시스템 완성도 10% | 승인형 개발 CLI·오류/보고 경로 | 증적 보존·복구, 안전한 운영·배포·책임자 근거 |
| 기술 이해도 20% | 정적 그래프·출처·실패·설정 한계의 코드/분석 | 선택한 실제 적용 조건에서의 재현·설정 실험 |
| AI기술 선택 적절성 20% | 일부 실제 모델 가설과 실패 관측 | 비AI/단순AI/강한 단일 대비 독립 기여·정확도 |
| 최적화 20% | 문맥·토큰 사용량과 구현 개선 | 동일 조건의 품질·전체 비용·지연 개선 효과 |

**공식 기준과 프로젝트 조건의 구분:** 80사례·USD 청구·특정 호스트·수치 임계값은 프로젝트가 선택한 입증 계약이며 공식 심사표의 일률적 A+ cutoff가 아니다. 특히 성과 지표 항목은 정의·측정 방법·도전성 평가이므로, 실행 자료 부재만으로 해당 항목의 공식 등급을 단정하지 않는다. 반대로 설계가 충실하다는 이유로 제안서 달성·최적화 효과를 인정하지 않는다.

**제한 사항:** 회사 업무·사업과의 연결은 아직 미해결이다. 자체 AST/그래프·승인·근거 검증·CLI는 단순 API 호출/노코드/단일 OSS 그대로 제출이라는 우려에 대한 구현 근거지만, 여섯 번째 프롬프트 역할 추가 자체를 심화 AI 기술의 독립 효과로 주장하지 않는다.

**최종 구분:** 현재는 부분 구현과 공개 개발 증거의 상태다. 구조는 조건부 실증에 쓸 수 있으나 누락된 실제 자료를 대신하지 않는다. 현재 A+ 달성이나 보장은 주장할 수 없다.
