# 위험 우선순위표 시제품 v1

> 아래 값은 화면 형상을 확인하기 위한 예시이며 프로젝트 실측 결과가 아니다.

## 릴리스 후보 점검 · `impact`

`base a1b2c3d` → `target e4f5a6b` · scan `accepted`

**분석 범위:** Python 126/130 files · 해석 불가 경로 4 · 동적 검증 1/3

| 우선 | 위험 | 영향과 발생 조건 | 변화 · 근거 | 다음 행동 |
|---:|---|---|---|---|
| 1 | **F-8C21 · High · concurrency**<br>`worker.run_job` | timeout 때 child task가 남아 다음 요청의 자원을 점유 | `worsened` · `deferred`<br>정적 호출·task 근거 3개 | **8분 검증**<br>취소 focused test 실행 |
| 2 | **F-19A0 · High · performance**<br>`orders.list_orders` | 목록 크기에 따라 DB 호출이 선형 증가 | `new` · `confirmed`<br>cProfile 실행 근거 | **수정 후보화**<br>query 호출 수 확인 |
| 3 | **F-53D2 · Medium · tests**<br>`auth.refresh_token` | 만료·재시도 경로를 검증하는 test가 없음 | `unchanged` · `confirmed`<br>분기·test mapping 근거 | **12분 검증**<br>focused regression test 작성 |

`resolved`와 `rejected`는 기본 표에서 숨기고 필요할 때만 필터로 본다.

---

## 선택한 위험 · F-8C21

**원인**  
`worker.run_job`이 timeout 뒤 만든 child task를 cancel·await하지 않는다.

**관찰된 근거**

- `worker.py:run_job`에서 `create_task` 호출
- timeout 예외 경로에 cancel 또는 await 없음
- 해당 경로를 실행하는 test 없음
- runtime 확인은 아직 하지 않음

**판단할 수 없는 부분**  
외부 task manager가 종료를 보장하는지는 현재 graph에서 확인되지 않는다.

**다음 검증**  
격리 workload에서 timeout을 발생시키고 종료 뒤 남은 task 수를 확인한다. 예상 8분.

**사용자 행동**

- `verify`
- `fix`
- `accept_risk`
- `dismiss`

---

## 표시 규칙

- **한 행은 stable finding ID 하나다.** 관점별 raw finding은 같은 ID로 합친다. root-cause cluster는 만들지 않는다.
- 단일 종합 점수는 계산하지 않는다.
- 정렬 tuple은 `severity ↓ → change(worsened, new, unknown, unchanged, resolved) → evidence(confirmed, deferred, rejected) → verification time ↑ → finding ID`다.
- 행에는 다섯 정보만 보인다: 위험, 영향·조건, 변화·근거, 다음 행동, 사용자 행동.
- coverage와 실행 누락은 표 위 한 줄에만 표시한다.
- 정기 main 점검은 현재 `confirmed/deferred` 위험을 기본 표시한다.
- 릴리스 후보 점검은 `new/worsened`를 먼저 표시하고 `impact/full` 선택값을 제목에 표시한다.
- 별도 dashboard, chart, heatmap, 상세 분류 화면은 만들지 않는다.
