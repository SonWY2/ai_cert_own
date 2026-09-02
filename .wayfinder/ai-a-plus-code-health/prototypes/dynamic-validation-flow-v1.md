# 승인형 동적 검증 흐름 시제품 v1

> 아래 명령과 값은 사용자 흐름을 확인하기 위한 예시이며 실제 실행 결과가 아니다.

## 도구 선택

| 가설 | DAG 경로 |
|---|---|
| 정확성 | 관련 기존 test 또는 focused pytest → 판정 |
| 동시성·async | focused pytest + asyncio 관찰 → hang이면 py-spy → 판정 |
| 성능 | profiler 없는 workload 반복 → 저하 재현 시 cProfile → Python/native/system 구분이 필요하면 Scalene → 판정 |
| 실행할 수 없음 | `no-run` → `deferred` |

승인된 DAG 안에서 조건을 충족하면 다음 node를 자동 실행한다. profiler는 동시에 실행하지 않는다.

## 사용자 흐름

```text
위험 행에서 verify 선택
        │
        ▼
전체 DAG가 담긴 RunManifest 한 장 표시
        │
   ┌────┴────┐
   │         │
 승인       거절
   │         └─ finding은 deferred 유지
   ▼
조건에 따라 DAG 자동 실행
   │
   ├─ 근거 충분 → confirmed / rejected
   ├─ 다음 조건 불충족 → deferred
   └─ 예산·timeout → deferred
```

## RunManifest 예시

```text
위험          F-8C21 · timeout 뒤 child task 잔존
snapshot      e4f5a6b
workload      tests/test_worker.py::test_timeout_cancels_children
DAG           pytest+asyncio → hang일 때 py-spy → 판정
명령          각 node의 exact command
환경          image sha256:... · Python 3.14
전체 한도     120초 · CPU 2 · memory 2 GiB
network       off
쓰기 경로     /work/evidence/F-8C21/
판정 기준     종료 뒤 pending task = 0이면 기각, 1 이상이면 확인
```

버튼은 `승인`과 `거절` 두 개만 둔다.

승인은 이 snapshot과 manifest hash의 DAG 실행 한 번에만 유효하다. DAG에 이미 적힌 다음 도구는 재승인 없이 실행한다. DAG 밖 도구가 필요하거나 workload·한도가 바뀌면 새 manifest를 보여준다.

## 실행 결과 예시

```text
상태          deferred
이유          timeout은 재현됐지만 승인된 DAG 안에서 task stack을 얻지 못함
실행 경로     pytest+asyncio → py-spy
보존 증거     node별 command · exit code · stdout hash · environment hash
중단 이유     전체 timeout 도달
```

## 제외

- 여러 profiler 동시 실행
- RunManifest에 없는 도구 자동 실행
- 명령별 여러 승인 화면
- profiler 결과를 benchmark 수치로 사용
- host·production process attach
- 자동 코드 수정 또는 release 차단
