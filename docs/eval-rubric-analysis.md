# AI Professional Lv3 심사 기준 분석 및 A+ 달성 전략

- 과제: AI 기반 코드 품질·성능 리스크 진단 에이전트
- 기준 문서: [`project-context/ai-professional-evaluation-criteria.md`](project-context/ai-professional-evaluation-criteria.md)
- 기획 문서: [`project-context/ai-professional-project-proposal.md`](project-context/ai-professional-project-proposal.md)
- 문서 상태: 2026-08-23 다각도 감사 반영

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

현재 프로젝트 실측값은 없다. 아래는 측정할 실패 유형이다.

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

## 5. A+ 사전 통과 기준

아래는 프로젝트 목표이며 외부 연구 결과가 아니다.

| 영역 | 사전 목표 |
| --- | --- |
| 진단 시간 | 전체 reviewer 의사결정 시간 중앙값 50% 이상 단축 |
| 리스크 식별 | 전체 Recall ≥ 0.85, Critical/High Recall ≥ 0.90, Precision ≥ 0.75 |
| 실행 확인 | 실행 가능한 High/Critical 발견의 runtime confirmation rate ≥ 0.70 |
| profiler | gold beneficial 사례 coverage ≥ 0.80, router Recall ≥ 0.85, Precision ≥ 0.80 |
| 재작업 | 같은 원인군의 후속 수정 30% 이상 감소 |
| 리뷰 생산성 | reviewer 시간 40% 단축 또는 수용 발견/시간 50% 증가 |
| 환각 제어 | 최종 무근거 발견률 ≤ 5%, 근거 없는 `runtime_confirmed` 0건 |
| 문맥 효율 | 같은 run-level 예산에서 input token 30% 절감, Recall 손실 ≤ 2%p |

효과 크기·표본 수·비열등 검정은 pilot 뒤 power analysis로 고정한다. 신뢰구간이 기준을 지지하지 않으면 “우월성 입증”이 아니라 “가능성 확인”으로 보고한다.

## 6. 시스템 완성도 A+ 운영 증거

일반 인프라 상세 설계는 범위 밖이지만 A+의 “실제 서비스로 사업화 가능한 수준”을 주장하려면 다음 최소 증거가 필요하다.

- 저장소 접근 인증·권한과 tenant/프로젝트 격리
- source/profile/log 보존 기간과 삭제·redaction 정책
- 모든 실행 명령·승인·결과의 감사 기록
- 진단 API/worker의 SLO, timeout, 재시도, 복구 시험
- 모델·도구 장애 시 기능 저하 방식과 rollback
- 운영 소유자, 지원 범위, 배포 경계

이 증거가 없으면 시스템 완성도 주장은 A급 “사내 자산” 수준으로 제한한다.

## 7. 탈락 방지

| 제한 | 방어 설계 | 확인 자료 |
| --- | --- | --- |
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

