# 공개 사례 as-is / to-be 비교: 실행 기록과 판정

**판정(2026-09-26): 이번 공개 결함에서 두 진단 모두 알려진 원인·수정 권고를 보고하지 못했다. A+ 성능 우월성 미입증.** 원본 함수의 수정 전·후를 Docker로 검증한 다음, 동일한 수정 전 Git의 일반 단일 프롬프트와 실행 연계 다관점 AI 진단을 각각 승인받아 실제 호출했다. 모델이 승인한 후보와 Docker의 관측 결과를 구분한다. 실행 실패가 AI의 발견을 뜻하지 않는다.

## 비교 대상과 정답 유출 경계

| 사례 | 고정 입력·원출처 | 이번에 직접 확인한 범위 | 평가 용도 |
| --- | --- | --- | --- |
| Prefect 비동기 재시도 오류 | [결함 보고 #23207](https://github.com/PrefectHQ/prefect/issues/23207), [수정 PR #23208](https://github.com/PrefectHQ/prefect/pull/23208); 수정 전 `148e99781fb05df258d3efddb5ef4fee0b61c9f2`, 수정 후 `cf45751fd8e82ca784821fdc2cee5f2cdc6b0746` | 수정 전 실제 파일 `src/prefect/_internal/retries.py:15-19,55-69`에서 지연 0을 `clamped_poisson_interval`에 전달하고 `src/prefect/utilities/math.py:21-23,43-61`에서 평균 지연으로 나누는 경로 확인. Git 스캔 1,912개 Python 파일. Apache-2.0 [원본 LICENSE](https://github.com/PrefectHQ/prefect/blob/148e99781fb05df258d3efddb5ef4fee0b61c9f2/LICENSE) | 개발용 공개 결함. 보고·수정 내용이 공개됐고 AI가 작성한 보고이므로 숨긴 정답·독립 판정이 아님 |
| FastAPI Users 정상 범위 후보 | [v15.0.5](https://github.com/fastapi-users/fastapi-users/tree/9ef8cd82619856772ac06a178b114eb47c79586c), SHA `9ef8cd82619856772ac06a178b114eb47c79586c`; [MIT LICENSE](https://github.com/fastapi-users/fastapi-users/blob/9ef8cd82619856772ac06a178b114eb47c79586c/LICENSE) | 태그의 Git HEAD 대조, 실제 정적 스캔 88개 Python 파일 | 결함이 없다고 검증된 음성 사례가 아님. 정답 없는 출처 대조군 후보만 가능 |

Prefect의 원 보고는 `base_delay=0`에서 첫 예외가 `ZeroDivisionError`로 바뀌고 재시도하지 않는다고 기록한다. 수정 PR은 `clamped_poisson_interval(average_interval <= 0)`에 `0.0`을 반환하는 회귀 검사도 제시한다. 이 저장소에서는 아래의 좁은 원본 함수 실행으로 수정 전 오류와 수정 후 검사 통과를 관측했다. **비동기 재시도 전체의 실행은 관측하지 않았다.**

**주입 없이 수정 전·후 출처를 준비:** 같은 Prefect 저장소의 수정 후 Git SHA `cf45751fd8e82ca784821fdc2cee5f2cdc6b0746`를 별도로 depth=1로 가져와 `scan_sources.py`를 실제 실행했다. 수정 후 `src/prefect/utilities/math.py:57-58`은 평균 지연이 0 이하일 때 `0.0`을 반환한다. 고정 수정본 출처 ID `d51d9262d77adff8a510a498eb2e5fc0fa4090fabbd9c625b2775268df48dec3`, Python 1,912개, 파서 3.12.4. 상류 수정본의 `tests/_internal/test_retries.py::TestRetryAsyncFn::test_zero_delay_retries_immediately`와 `tests/utilities/test_math.py::test_clamped_poisson_interval_returns_zero_for_nonpositive_average`를 확인했다. 자체 실행은 아래의 좁은 원본 함수·독립 행동 검사에 한정된다.

## 직접 실행한 명령과 원자료

```sh
git clone --depth 1 --branch v15.0.5 https://github.com/fastapi-users/fastapi-users.git /tmp/wreckfish-public-fastapi-users-compare-20260926
git -C /tmp/wreckfish-public-fastapi-users-compare-20260926 rev-parse HEAD
python3 -B src/scan_sources.py /tmp/wreckfish-public-fastapi-users-compare-20260926 9ef8cd82619856772ac06a178b114eb47c79586c /tmp/wreckfish-public-fastapi-users-compare-20260926-source
# Prefect: origin에서 위 수정 전 SHA를 depth=1, filter=blob:none으로 fetch/checkout
python3 -B src/scan_sources.py /tmp/wreckfish-public-prefect-retry-before-20260926 148e99781fb05df258d3efddb5ef4fee0b61c9f2 /tmp/wreckfish-public-prefect-retry-before-20260926-source
python3 -B src/scan_sources.py /tmp/wreckfish-public-prefect-retry-before-20260926 148e99781fb05df258d3efddb5ef4fee0b61c9f2 /tmp/wreckfish-public-prefect-retry-before-20260926-selected --symbol clamped_poisson_interval
python3 -B src/scan_sources.py /tmp/wreckfish-public-prefect-retry-fixed-20260926 cf45751fd8e82ca784821fdc2cee5f2cdc6b0746 /tmp/wreckfish-public-prefect-retry-fixed-20260926-source
```

| 출처 기록 | stage | 출처 ID | 관측 범위 |
| --- | --- | --- | --- |
| FastAPI Users | `source_scanned` | `760e1535202fffae09d7209c1f6e9f9a53b51d6f14e67c4c4b3fd7be347ca9ca` | Python 88개, 파서 3.12.4 |
| Prefect 수정 전 | `source_scanned` | `9c8760370d6f5fba4e30a404ce3612445f3eef1daf05307386ce1ce6a841d1cf` | Python 1,912개, 파서 3.12.4; 심볼 검색에서 관련 호출 간선을 반환. 스캔 중 타 통합 파일의 `SyntaxWarning`은 진단 후보 아님 |
| Prefect 수정 후 | `source_scanned` | `d51d9262d77adff8a510a498eb2e5fc0fa4090fabbd9c625b2775268df48dec3` | Python 1,912개, 파서 3.12.4; 수정 후 코드의 분기 확인, 실행 결과 아님 |

출처 기록은 각 `/tmp/wreckfish-public-*-20260926-source/runs/<출처 ID>/run.json`에 보관. `/tmp` 보관이므로 장기 보존·최종 심사 원자료로 주장하지 않는다.

## 기존 동결 계약에 따른 비교 해석

- **일반 as-is:** `A_plain_llm` = 같은 `gpt-6-luna`에 사용자 지정 원문/차이와 일반적인 코드 검토 요청을 한 번 입력. 구조화 관점, Code Graph, 실행 피드백은 주지 않음. 같은 작은 모델의 전체 시스템 `F_runtime_feedback`과 동일 사례·Git SHA·과제·평가 범위·정답 비공개·총 토큰/도구 시간/20분 상한에서 짝비교한다. `A→B→C→D→E→F` 인접 비교로만 각 구성요소의 기여를 추정한다.
- **강한 as-is:** `S_strong_single` = `gpt-6-sol` 한 번에 지정 범위의 원문을 넣어 검토. 모든 운영 호출이 `gpt-6-luna`인 F와 동일 사례·범위·출력 형식·총 예산에서 결함 단위 식별률과 실제 청구 비용을 비교한다. 도구/문맥 차이는 **시스템 효과**이지 모델 자체의 우열이 아님.
- **현재 `--single-baseline`은 일반 as-is가 아님.** 실제 `src/modules/diagnosis/model.py`의 동일한 다섯 관점 지시문·증거 형식을 단일/5회 경로에서 모두 쓰고, 심볼 경로는 검색 문맥까지 받는다. 이 결과를 `A_plain_llm`로 다시 이름 붙이지 않는다. `check_code.py`의 실제 F 경로도 동결된 가설별 선택 실행·독립 판정까지 연결되지 않았다.
- 공개 Prefect 결함은 개발용 재현 가능성 확인에만 사용. 공개 정답 누출을 막을 독립 봉인 80사례(숨김 합성 40 + 시간 분리 공개 40), 다른 계열의 눈가림 판정, 실행 oracle이 없는 동안 공개 사례 성적을 최종 우월성에 합산하지 않는다.

## 비교 결과 및 차단 조건

| 지표 | 이번 관측값 | 판정 |
| --- | --- | --- |
| 공개 한 결함의 발견 여부 | 일반: 후보 1건(다른 가설), 알려진 `average_interval <= 0` 결함 **0/1**. AI: 최종 후보 0건, 알려진 결함 **0/1**; 5관점 중 3개 실패·1개 보류 | 개발용 공개 사례 1건에서 양쪽 모두 놓침. AI 경로 분석 불완전; 독립 Recall·Precision·승패 측정 불가 |
| 실제 실행 결과·프로파일러에 근거한 권고 | 원본 수학 함수의 동일 행동 검사: 이전판 `ZeroDivisionError`, 수정판 통과. 이번 AI군 Docker도 같은 오류·종료 1, AI 권고 0건 | **개발용 한 경로 확인**; 비동기 재시도 전체·프로파일러·AI 권고 검증은 미실시 |
| 호출별 실제 USD 청구·결함당 비용 | 일반 모델 2,201토큰, AI 모델 23,165토큰(실패 호출 포함); 제공자 청구 영수증 없음 | 이 개발 사례의 AI 토큰 10.52배. 실제 USD 비용·비용 우월성 측정 불가 |
| 이전 승인된 개발 모델 호출 | 강한 1회 `ValueError` 실패 2,943토큰; 작은 정적 5회 완료 13,213토큰·알려진 변이 후보 0 | [이전 개발 실측](../../.wayfinder/ai-a-plus-code-health/tickets/029.md#승인된-실제-호출과-판정2026-09-26)의 실패 포함 기록; 현재 프롬프트·공개 사례·F와 달라 이번 비교 분모에서 제외 |

앞선 Docker 수정 전·후 RunManifest 영수증과 이번 모델 비교의 두 RunManifest 영수증은 모두 **각 1회 사용 후 소진**됐다. 추가 소스 전송·모델·실행 범위에는 새 정확한 RunManifest와 새 소유자 승인이 필요하다. 루프백 프록시도 호출 뒤 종료했다. 최종 평가에는 별도 독립 사례·자원 한도를 강제하는 Docker 호스트·청구 원본 등이 필요하다. 이 결과만으로 공식 [심사 기준](../project-context/ai-professional-evaluation-criteria.md)의 기술 선택·최적화 A+와 사업 수준 완성도를 입증할 수 없다.

**초기 Docker 조사(당시 v25):** `docker context ls`에서 `rootless-wreckfish`(Unix 소켓 `/run/user/1000/docker.sock`)가 선택돼 있었다. 앞선 격리 확인에서 이 daemon은 `CgroupDriver=none`이었고 지정 CPU·메모리 상한이 강제되지 않았다([기술 증적](03-ai-pipeline-technical-design.md)). rootful `dockerd`가 시스템 경로에 없고 `/var/run/docker.sock`도 없으며 `sudo -n true`는 암호를 요구했다. 당시 v25는 대상 실행을 거절했다. **이 제한을 개발용에 한해 완화한 이후 상태는 다음 절에 기록한다.**

## v26 개발용 Docker 실행과 좁은 실제 결함 검사

소유자는 자원 제한을 요구하지 않고 현재 Docker에서 개발 검증하도록 결정했다. `validate_runtime_host()`는 cgroup 미지원이면 **실행 전 경고하고 통과**한다. 대상 없는 실제 확인에서 `docker_preflight_passed`, 고정 Python 3.14 이미지에 `--read-only --network=none --cap-drop=ALL --pids-limit --memory --cpus`를 붙인 컨테이너에서 `trusted_docker_probe_ok`를 관측했다. 이 옵션으로 지정한 CPU·메모리·PID 한도는 이 호스트에서 **강제된 증거가 아니다**. 수정한 경로의 전체 unittest 158개 통과.

원본 Prefect 전체 Git에는 `compat-tests` submodule이 있어 실행기가 전체 동결 tree를 복원할 때 거절한다. 안전 경계를 낮추지 않기 위해 **upstream `src/prefect/utilities/math.py` 원본 Git blob, 동일한 테스트 전용 파일, LICENSE만** 포함한 좁은 재현 Git을 별도로 봉인했다. 수정 전 원본 blob `9daca1c7418621af517929873422a7a27855d7b6`, 수정 후 `cb76224679fa53c184924c17eeea6a834c96724d`. 테스트는 상류가 확인한 입력 `0`, `0.0`, `-1`에서 반환값 `0.0`을 요구한다. 생성된 Git은 upstream commit 자체가 아니며 Prefect 전체 애플리케이션 동작·비동기 재시도 완료 횟수까지 검증하지 않는다. **결함 코드는 변경·주입하지 않았다.**

| 조건 | 이전판 | 수정판 |
| --- | --- | --- |
| 재현 Git SHA | `f53bdda07f419ac559035f9836fa6af54304d17c` | `c90f07b3e765b61aaeee41d4f475c312d3b8cef4` |
| 실제 정적 출처 묶음 ID | `71e0e24d98e3ad149ceaf58e39d67aed1b561a379f88eb58b5cf88005cc4c0da` | `61aab9187457b2d9ef747f69a0c22f4a2c9203589081ff4824fc4c1cd301f9d2` |
| 사용된 RunManifest 해시 | `3b8b9ccded31feb4236744e3f2b2ba236d51995a771f8d0094ce9f0d9a340c66` | `0142a823daa2cdfd4e77036a9215b92acfd7f43e41408b86bdfbada7b1f74536` |

양쪽 manifest는 로컬에 캐시된 Python 이미지 `sha256:51dafde81dbdb6ebde285137a295cf18a47ca95234fe388a343719cb97305b3d`, 네트워크·모델 호출 **없음**, 대상 `python tests/test_wreckfish_public_retry_oracle.py`, 읽기 전용 Git 마운트, 호스트 180초 중단을 동일하게 선언한다. 두 `RunManifest`와 원본 Git 출처·테스트 경로의 사전 검증을 실제 통과했다. CPU·메모리·PID 요청값은 이 호스트에서 강제되지 않음을 승인 화면과 실행 경고에 표시한다.

소유자가 아래 명령에서 각각 설정 해시를 직접 확인·입력해 두 영수증을 발급했다. 영수증 디렉터리 `/tmp/wreckfish-prefect-retry-approvals-20260926`은 0700이고, 두 영수증은 각 1회 실행 후 소진됐다.

```sh
python3 src/approve_run.py /tmp/wreckfish-prefect-retry-narrow-before /tmp/wreckfish-prefect-before-oracle-manifest.json /tmp/wreckfish-prefect-retry-approvals-20260926/before.json
python3 src/approve_run.py /tmp/wreckfish-prefect-retry-narrow-fixed /tmp/wreckfish-prefect-fixed-oracle-manifest.json /tmp/wreckfish-prefect-retry-approvals-20260926/fixed.json
```

두 영수증의 정확한 SHA 일치를 사전 검증한 다음 `src/run_approved.py`로 **이전판 → 수정판 순서**로 실행하고, 각 결과를 `src/run_approved.py --verify`로 Git·설정·로그 해시까지 다시 대조했다. 두 컨테이너는 같은 image digest·argv·한도 요청·네트워크/권한 정책을 썼다.

```sh
python3 -B src/run_approved.py /tmp/wreckfish-prefect-retry-narrow-before-source/runs/71e0e24d98e3ad149ceaf58e39d67aed1b561a379f88eb58b5cf88005cc4c0da /tmp/wreckfish-prefect-before-oracle-manifest.json /tmp/wreckfish-prefect-retry-approvals-20260926/before.json /tmp/wreckfish-prefect-retry-before-runtime-20260926
python3 -B src/run_approved.py /tmp/wreckfish-prefect-retry-narrow-fixed-source/runs/61aab9187457b2d9ef747f69a0c22f4a2c9203589081ff4824fc4c1cd301f9d2 /tmp/wreckfish-prefect-fixed-oracle-manifest.json /tmp/wreckfish-prefect-retry-approvals-20260926/fixed.json /tmp/wreckfish-prefect-retry-fixed-runtime-20260926
python3 -B src/run_approved.py --verify /tmp/wreckfish-prefect-retry-narrow-before-source/runs/71e0e24d98e3ad149ceaf58e39d67aed1b561a379f88eb58b5cf88005cc4c0da /tmp/wreckfish-prefect-before-oracle-manifest.json /tmp/wreckfish-prefect-retry-before-runtime-20260926
python3 -B src/run_approved.py --verify /tmp/wreckfish-prefect-retry-narrow-fixed-source/runs/61aab9187457b2d9ef747f69a0c22f4a2c9203589081ff4824fc4c1cd301f9d2 /tmp/wreckfish-prefect-fixed-oracle-manifest.json /tmp/wreckfish-prefect-retry-fixed-runtime-20260926
```

위 실행 명령은 **실제 수행 내역**이다. 첫 두 영수증은 소진됐으므로 그대로 재실행할 수 없다. `--verify`만 재실행할 수 있다.

| 관측 항목 | 이전판 | 수정판 |
| --- | --- | --- |
| Docker node 상태/종료 코드 | `failed`, `nonzero_exit`, **1** | `completed`, **0** |
| 원본 로그 | `/tmp/wreckfish-prefect-retry-before-runtime-20260926/oracle-0.stderr` — `math.py:22`의 `1 / average_interval`에서 `ZeroDivisionError: division by zero` | `/tmp/wreckfish-prefect-retry-fixed-runtime-20260926/oracle-0.stdout` — `upstream_retry_zero_delay_oracle_passed` |
| 컨테이너 node 실행시간 | 0.698초 | 0.465초 |
| stderr / stdout SHA-256 | `2bf27b42fe932524d07b2c28528e805a2e1848aab995b4cb5dd6d6cddf23c76b` / 빈 파일 | 빈 파일 / `990005754ab307dec19fdd34c58a42a7f61b08b082c045cd9d88658ff780064b` |
| 검증된 원자료 | `/tmp/wreckfish-prefect-retry-before-runtime-20260926/execution.json` | `/tmp/wreckfish-prefect-retry-fixed-runtime-20260926/execution.json` |

이 결과는 수정 전/후의 **실행 동작 차이 한 건**이다. 컨테이너 실행 흔적의 `runtime_attested=false`와 `caller_declared_unattested`는 그대로 유지한다. 이전판 실행 실패를 `workflowz`가 AI로 결함을 발견한 성과로 세지 않는다. 상류에 공개된 결함·좁은 함수 검증·비강제 cgroup 환경이므로 독립 숨김 평가, CPU·메모리 격리 입증, 최종 as-is/to-be 성능·USD 비교의 분모에는 넣지 않는다.

## 일반 단일 프롬프트 대 현재 AI 진단: 개발용 짝비교

- **입력:** 양쪽 모두 수정 전 좁은 Git `f53bdda07f419ac559035f9836fa6af54304d17c`의 `clamped_poisson_interval`을 검토. 모델은 `gpt-6-luna`, 총 40,000토큰·1,200초 상한이 동일. 행동 검사 **소스 파일**은 어느 진단에도 전송하지 않고, 실행 관측 요약은 AI군에만 제공한다.
- **일반 단일 프롬프트:** 새 `--plain-baseline --symbol clamped_poisson_interval`은 `src/prefect/utilities/math.py`의 **원문 전체 한 파일**·파일 출처 ID·일반적인 버그 검토 요청만 한 번 전송한다. Code Graph 간선, 다섯 관점 지시, 실행 로그를 전송하지 않는다. 출력은 두 군의 위치·원인·다음 행동을 같은 필드로 검사하기 위해 JSON으로 제한한다.
- **현재 AI 경로:** 같은 심볼을 Code Graph로 찾은 7개 노드의 원문 조각(8,826바이트)과 간선을 다섯 관점에 제공한다. 별도 승인된 Docker 노드는 같은 Git의 행동 검사를 실행하고 검증된 실패 로그를 모델 문맥에 넣는다. CLI 종료 코드 3만으로 Docker 명령 실패와 모델 관점 실패를 구분할 수 없으므로 `perspectives`와 `runtime_trace`를 각각 확인한다. **이는 사전 선언한 실행 + 모델 진단**이며 가설별 선택 실행·독립 봉인을 마친 최종 `F_runtime_feedback`이 아니다.
- **사례 판정:** 원인 `average_interval <= 0`에서 `exponential_cdf`의 역수 계산으로 `ZeroDivisionError`, 사용자가 겪는 실패, 0 이하일 때 `0.0`을 반환하도록 고친 후 `0`, `0.0`, `-1`을 확인하는 권고를 구분해 기록한다. 근거 없는 다른 결함은 별도 미확인 후보로 남긴다. 공개 사례 한 건은 독립 숨김 정답·A+ 통계 우월성의 근거가 아니다.

승인 전 두 설정과 출처 묶음·Docker 명령은 `manifest_hash`, `verify_git_source`, `validate_runtime_plan`, `validate_source_workloads`로 검사했다. `openai-oauth@2.0.0`의 루프백 모델 목록에서 `gpt-6-luna`를 확인했다. 아래 표와 명령은 **승인 전에 고정한 계약**이다. 호출별 USD 청구 자료는 없다.

| 군 | 승인 대상 설정 | 고정 설정 해시 | 신규 소유자 승인 |
| --- | --- | --- | --- |
| 일반 단일 프롬프트 | `/tmp/wreckfish-prefect-ai-plain-manifest-20260926.json` | `2e6e74edeb521494f76383bdb06140c8ee10fb15b997d3fd2a853d85a79ba3ec` | 직접 승인·1회 소진 |
| 실행 연계 다관점 | `/tmp/wreckfish-prefect-ai-system-manifest-20260926.json` | `3232485f8a7608803a704455f69623e2431923a173cf1b4fa76845b9723601b7` | 직접 승인·1회 소진 |

출처 묶음은 `/tmp/wreckfish-prefect-retry-narrow-before-source/runs/71e0e24d98e3ad149ceaf58e39d67aed1b561a379f88eb58b5cf88005cc4c0da`. 소유자는 저장소 루트의 **본인 대화형 단말**에서 아래 두 명령을 각각 실행하며 설정 전체와 해시를 직접 확인·입력했다. 이전 Docker 전용 승인과 다른 영수증이다.

```sh
python3 src/approve_run.py /tmp/wreckfish-prefect-retry-narrow-before /tmp/wreckfish-prefect-ai-plain-manifest-20260926.json /tmp/wreckfish-prefect-retry-approvals-20260926/plain-ai.json
python3 src/approve_run.py /tmp/wreckfish-prefect-retry-narrow-before /tmp/wreckfish-prefect-ai-system-manifest-20260926.json /tmp/wreckfish-prefect-retry-approvals-20260926/system-ai.json
```

승인 전 `diagnose_approved.py` 실제 CLI는 두 설정 모두 영수증 없음으로 종료 코드 2였다. 이번에는 영수증을 대조한 뒤 프록시를 루프백으로 켜고 다음 두 명령을 **각 1회 실행**, CLI 결과 JSON과 종료 상태를 저장했다. 두 명령을 그대로 다시 실행하면 소진된 영수증 때문에 거절된다. 실행군 Docker의 CPU·메모리 요청값은 현재 rootless 호스트에서 **강제된 증거가 아님**.

```sh
set -o pipefail && python3 -B src/diagnose_approved.py /tmp/wreckfish-prefect-retry-narrow-before-source/runs/71e0e24d98e3ad149ceaf58e39d67aed1b561a379f88eb58b5cf88005cc4c0da /tmp/wreckfish-prefect-ai-plain-manifest-20260926.json /tmp/wreckfish-prefect-retry-approvals-20260926/plain-ai.json --symbol clamped_poisson_interval --plain-baseline | tee /tmp/wreckfish-prefect-ai-plain-result-20260926.json
set -o pipefail && python3 -B src/diagnose_approved.py /tmp/wreckfish-prefect-retry-narrow-before-source/runs/71e0e24d98e3ad149ceaf58e39d67aed1b561a379f88eb58b5cf88005cc4c0da /tmp/wreckfish-prefect-ai-system-manifest-20260926.json /tmp/wreckfish-prefect-retry-approvals-20260926/system-ai.json --symbol clamped_poisson_interval --runtime-output /tmp/wreckfish-prefect-ai-system-runtime-20260926 | tee /tmp/wreckfish-prefect-ai-system-result-20260926.json
```

### 승인 후 실제 관측과 원자료

| 관측 | 일반 단일 프롬프트 | 실행 연계 다관점 |
| --- | --- | --- |
| 사용 모델·출처 | `gpt-6-luna`, 동일 Git `f53bdda07f419ac559035f9836fa6af54304d17c` | 동일 |
| 전달한 코드 | `math.py` 원문 2,954바이트, 그래프·테스트·실행 로그 없음 | 같은 파일의 그래프 조각 7개/8,826바이트·간선 + 검증된 Docker stderr |
| 실제 모델 호출·사용 토큰 | 1회 완료, **2,201** | 4회 호출, **23,165**(실패 3회 비용 포함); 5번째 관점 예산 보류 |
| 관점별 결과 | `all`: 완료, 후보 1건 | `structure`: 실패 `candidate_ungrounded` 5,941토큰; `correctness`: 같은 실패 5,989토큰; `performance`: 완료 5,328토큰; `concurrency`: 같은 실패 5,907토큰; `tests`: 보류 `budget_exhausted` 0토큰 |
| 모델 요청 시간 합계 / CLI 전체 시간 | 33.095초 / 33.33초 | 42.562초 / 43.62초(같은 호스트의 Docker 실행 0.656초 포함) |
| 알려진 공개 결함을 지적한 최종 후보 | **0/1**. 별도의 `lower_clamp_multiple` 공식 가설 1건은 `math.py:32`의 문서 문자열 줄을 위치로 제시해 수정할 코드 위치가 아니며, 수학적 참·거짓도 검증하지 않음 | **0/1**. 최종 채택 후보 0건 |
| CLI 종료 | 0: 모델 요청과 후보 형식 검사 완료 | 3: 모델 관점 실패·보류 및 Docker 명령 비정상 종료. 3을 단순한 모델 발견이나 결함 확증으로 세지 않음 |

AI 경로에서 검증된 Docker 로그는 `math.py:22`의 `1 / average_interval`에서 `ZeroDivisionError`를 보였다. 이 로그는 모델 입력에 전달됐지만, **AI가 검사를 통해 발견·수정 권고를 낸 것은 아님**. `candidate_ungrounded`는 후보의 관점 분류·경로·출처 ID 중 입력 문맥과 불일치했다는 코드이며, 응답 원문을 보관하지 않아 어느 필드가 틀렸는지는 알 수 없다. 오류 코드를 성공 후보로 재분류하거나 새 승인 없이 재호출하지 않았다. 총 토큰 상한 40,000이 같아도 호출마다 반복한 그래프 문맥 때문에 5번째 관점은 남은 예산 안에 요청을 담지 못했다. 이 한 건의 토큰 **10.52배** 차이는 실제 관측값이지 일반적인 비용 비율이 아니다.

- 일반 결과 원문: `/tmp/wreckfish-prefect-ai-plain-result-20260926.json` (SHA-256 `254dd0b62ece2615a635d1d76f9646b0c2b67589fca5d85af5ad47d7e06ee9ba`).
- AI 결과 원문: `/tmp/wreckfish-prefect-ai-system-result-20260926.json` (SHA-256 `776405f183646e2540245c30ff3cffd3676473fa3bec6d4d1fea4659cc0f7526`). 두 파일의 `perspectives`에 각 요청/응답 SHA-256, 토큰, 호출 시간이 있다. 모델 응답 본문 자체는 보관되지 않았다.
- 실행 원문: `/tmp/wreckfish-prefect-ai-system-runtime-20260926/execution.json` (SHA-256 `5fcc7db5f6f9a07c8c519bc5812594c0366296339d759c94fbd2a5dd56493b6d`), `/tmp/wreckfish-prefect-ai-system-runtime-20260926/oracle-0.stderr` (SHA-256 `2bf27b42fe932524d07b2c28528e805a2e1848aab995b4cb5dd6d6cddf23c76b`). `src/run_approved.py --verify`로 Git·manifest·로그를 대조했다. `runtime_attested=false` 그대로다.
- 사용한 두 영수증의 `.used` 파일에 각 설정 해시가 기록됐다. 루프백 OAuth 프록시는 호출 뒤 종료했다. `/tmp` 원자료는 임시 보관이므로 장기 보존·독립 심사 원자료로 간주하지 않는다.

**실증 경계:** 이번에는 하나의 공개 결함에 대해 같은 작은 모델의 일반 검토와 현재의 사전 선언 실행 연계 경로를 비교했을 뿐이다. 둘 다 알려진 결함을 보고하지 않았고, AI 경로는 분석 불완전·토큰 10.52배 사용이었다. 강한 모델 `gpt-6-sol` 비교, A→F 인접 기여, 독립 봉인 80사례·제공자 청구 자료는 없다. 따라서 기술 우월성, 일반 Recall·Precision, A+ 달성 주장은 모두 미입증이다.

## 후속 무실행 정적 반례 탐색: 후보이지 AI 발견이 아님

앞선 모델 비교는 **변경 전** 코드·프롬프트의 실측으로 그대로 보존한다. 그 실패를 바탕으로 `src/modules/static_scan/counterexamples.py`를 추가했다. 동결 Git의 AST에서 함수 인수 → 해석된 같은 파일 함수 호출 → 0으로 나누거나 빈 컬렉션을 인덱싱하는 표현식을 추적한다. 입력 `0` 또는 `[]`가 닿는 반례를 제시하되, 그 입력이 계약상 허용되는지 확인하지 못하면 `static_hypothesis`로만 표시한다. 조기 반환·예외 가드, 재할당, 해석되지 않은 호출과 조건부 표현식은 보수적으로 처리한다. **대상 함수나 행동 검사는 실행하지 않는다.**

```sh
python3 -B src/scan_sources.py /tmp/wreckfish-prefect-retry-narrow-before f53bdda07f419ac559035f9836fa6af54304d17c /tmp/wreckfish-prefect-static-before-20260926 --symbol clamped_poisson_interval --static-probes
python3 -B src/scan_sources.py /tmp/wreckfish-prefect-retry-narrow-fixed c90f07b3e765b61aaeee41d4f475c312d3b8cef4 /tmp/wreckfish-prefect-static-fixed-20260926 --symbol clamped_poisson_interval --static-probes
```

| 원본 상태 | 무실행 정적 출력 | 판정 경계 |
| --- | --- | --- |
| 수정 전 Git `f53bdda07f419ac559035f9836fa6af54304d17c` | `clamped_poisson_interval:43`의 `average_interval=0` → 호출 59행 → `exponential_cdf:22`의 `1 / average_interval`: `zero_denominator` **후보 1건** | 앞서 실행으로 재현된 오류 경로와 위치가 일치하지만, 정적 출력은 실행 확인이나 입력 유효성 증명이 아님 |
| 수정 후 Git `c90f07b3e765b61aaeee41d4f475c312d3b8cef4` | 같은 심볼의 정적 후보 **0건** | 57–58행의 `average_interval <= 0` 조기 반환만 구별; 무결함 보장 아님 |

두 CLI 출력의 Git 출처 묶음을 다시 검증했다. 수정 전 간결 원문 `/tmp/wreckfish-prefect-static-before-probes-20260926.json`의 SHA-256은 `b7d02b282c1c26b0a6fd6fad68c66b238ea39517e6a32ca60af586a099c2fbf0`; 수정 후 `/tmp/wreckfish-prefect-static-fixed-probes-20260926.json`은 `31e6732ab2e6e5dbdec172454420eb640f7dddfafcc8e8ec25b15b18579e816f`. 출처 ID는 각각 `71e0e24d98e3ad149ceaf58e39d67aed1b561a379f88eb58b5cf88005cc4c0da`, `61aab9187457b2d9ef747f69a0c22f4a2c9203589081ff4824fc4c1cd301f9d2`; 문맥 잘림 없음. 정적 CLI는 모델 전송·대상 실행 영수증을 사용하지 않는다.

구조화 AI 문맥에도 정적 반례를 **확인할 단서로만** 추가했다. 같은 파일의 전체 module 원문이 있으면 중복된 함수 원문은 전송 문맥에서 한 번만 실어 반복을 줄인다. 기존 출처 검증·위치 검사에 쓰는 원본 문맥은 유지한다. 새 구조화 프롬프트 SHA-256은 `70996a3f6f4ad95f9631b0383dfbebf48db60602e2c21bd059a0a581b7afe116`; 일반 단일 프롬프트는 바꾸지 않았다. **이 변경 뒤 실제 모델 호출은 없음.** 이전 영수증은 이미 소진됐고, 새 프롬프트의 발견률·실제 토큰 절감은 미측정이다. 기존 모델 결과 0/1을 이번 정적 후보 1건으로 소급 변경하지 않는다.

적용 범위는 단순한 직접 표현식·같은 파일의 해석된 호출 한 단계다. 여러 파일을 넘는 값 흐름, 변수 별칭·복잡한 조건문, API가 0/빈 입력을 금지하는지의 판정은 하지 않는다. 테스트용 Git에서 빈 목록 인덱싱과 보호 분기·미해석 호출을 별도로 확인했고 전체 회귀 `python3 -B -m unittest discover -s tests -q` **165개 통과**. 이 1건의 공개 사례는 혁신성·일반 정확도·토큰 효율의 실증이 아니다. 동일 예산의 독립 반례 유무 짝비교와 실제 모델 권고의 유효성 판정 뒤에만 A+ 기술 기여로 제시할 수 있다.

## 후속 사용자 화면: 실행 전 위험 단서

`scan_sources.py`의 기존 JSON 출력을 유지하면서 `--static-probes --readable`을 추가했다. 새 터미널 출력은 동결 Git·출처 묶음·경계 입력·호출/실패 가능 위치를 보여주며 **결함 확증이나 사람/LLM 판정으로 표시하지 않는다**. 실모델 승인이나 대상 코드 실행 없이 아래 명령을 직접 실행했다.

```sh
python3 -B src/scan_sources.py /tmp/wreckfish-prefect-retry-narrow-before f53bdda07f419ac559035f9836fa6af54304d17c /tmp/wreckfish-prefect-readable-before-20260926 --symbol clamped_poisson_interval --static-probes --readable
python3 -B src/scan_sources.py /tmp/wreckfish-prefect-retry-narrow-fixed c90f07b3e765b61aaeee41d4f475c312d3b8cef4 /tmp/wreckfish-prefect-readable-fixed-20260926 --symbol clamped_poisson_interval --static-probes --readable
```

첫 화면: 후보 **1건**, `src/prefect/utilities/math.py:43`의 `average_interval=0` → 호출 59행 → `exponential_cdf:22`의 0으로 나눌 가능성. 둘째 화면: 후보 **0건 (0건도 안전 증명이 아님)**. 두 화면 모두 “대상 코드 실행·LLM 판정은 수행하지 않음”을 표시했다. 출처 묶음 ID는 위 JSON 실증과 동일하며 새 출력 경로는 `/tmp` 임시 저장이다. 보호 분기가 있는 정상 함수의 화면은 0건으로 표시하고, 인자 없이 `--readable`만 지정하면 근거 디렉터리를 만들기 전에 거절하는 CLI 회귀를 확인했다. 전체 `python3 -B -m unittest discover -s tests -q` **165개 통과**. 이는 사용자가 후보를 볼 수 있게 한 개발 확인이지, 실제 AI 발견률·심사 등급·사람 평가 또는 최종 80건 실측이 아니다.

## 자유 탐지 개발 파일럿: 공개 FastAPI 풀스택 코드의 승인 전 정적 확인

- **사전 범위:** [FastAPI full-stack template 0.12.0](https://github.com/fastapi/full-stack-fastapi-template/tree/84c5a9e11a9e58262599e3d772f5386924e02ca7)의 Git `84c5a9e11a9e58262599e3d772f5386924e02ca7`, Python 백엔드 `backend/`, 이 중 API 모듈 `backend/app/api/routes/items.py` 한 파일을 공개 개발용 짝비교 입력으로 선택했다. 특정 버그명·정답은 고르지 않았다. [MIT 원문](https://raw.githubusercontent.com/fastapi/full-stack-fastapi-template/84c5a9e11a9e58262599e3d772f5386924e02ca7/LICENSE)과 [Python ≥3.14 요구](https://raw.githubusercontent.com/fastapi/full-stack-fastapi-template/84c5a9e11a9e58262599e3d772f5386924e02ca7/backend/pyproject.toml)를 확인했다. 프론트엔드 TypeScript의 의미 분석은 이 범위 밖이다.
- **실제 한 일:** `git ls-remote --tags`의 `0.12.0`이 위 Git SHA와 일치했고 해당 태그를 `/tmp/wreckfish-open-discovery-fullstack-012-20260926`에 clone했다. 추적 Python 파일 **47개**(그중 `backend/` **44개**)를 불변 Git에서 Python **3.14.3**으로 정적 스캔했다. 출처 묶음 `5da0851315998c1dcec0c9118b3fe27ada3e33bdb0502e24c7087cd4b2562fed`의 Git SHA 대조를 통과했고 파싱 오류는 **0개**다. 아래 명령은 대상 코드 실행이나 모델 전송이 아니다.

```sh
python3.14 -B src/scan_sources.py /tmp/wreckfish-open-discovery-fullstack-012-20260926 84c5a9e11a9e58262599e3d772f5386924e02ca7 /tmp/wreckfish-open-discovery-py314-source-20260926 --symbol module:backend/app/api/routes/items.py --static-probes --readable
```

실제 화면은 `후보: 0건 (0건도 안전 증명이 아님)`이었다. 선택 모듈의 원문 **3,446바이트**, 그래프 문맥 **7노드·10,019 source bytes**, 잘림 없음, 경로는 모두 `backend/app/api/routes/items.py`였다. `retrieve` 결과의 정렬된 JSON SHA-256은 `bc62644e914c7e8584c9718faf333188d4281539174b9ad5013b3f423c51cdf3`. 원문 전체를 보낸 실제 모델 토큰량이나 버그 0건을 측정한 것은 아니다.

**해석기 불일치의 재현과 수정:** 첫 Python 3.12.4 스캔의 별도 묶음 `68301a9260fa6d65a0ab95594873b7ba7eba6fd1abc615e404849e5f320e2178`에는 `backend/app/api/deps.py:36`을 `parse_error`로 기록했다. 같은 Git 파일은 Python 3.14.3의 `ast.parse`에서 정상이다. 그 첫 묶음을 모델 비교 출처로 사용하지 않는다. 진단 CLI가 출처 스캔과 **같은 Python 파서 버전**을 요구하도록 변경했다. 승인형 시험 입력의 변경 전 실패·변경 후 통과를 확인했고, 실제 3.14 묶음을 Python 3.12 CLI로 검토하면 **승인 소진 전** 파서 불일치로 종료 코드 2, Python 3.14 CLI에 영수증 없이 넣으면 **승인 없음**으로 종료 코드 2였다. 대상 코드를 실행하거나 모델에 보내지 않았다.

**다음 쌍비교 입력만 고정:** 같은 Python 3.14 출처 묶음·선택 심볼을 `gpt-6-sol --single-baseline` 1회와 `gpt-6-luna`의 다섯 관점 경로에 사용한다. 두 모델 전용 설정 `/tmp/wreckfish-open-discovery-prep-20260926/strong.json`(해시 `9af3da3ec7789e6e465389daa534a23d05a9802f0d1d8f88d0787be8356043b4`)과 `system.json`(해시 `e842df12b9c1d09f81c05b874eb34b92ccaa057d2962d7da01c3cf8e77246144`)을 구조 검증했다. 두 군의 현재 구조화 프롬프트 SHA-256은 `70996a3f6f4ad95f9631b0383dfbebf48db60602e2c21bd059a0a581b7afe116`, 총 한도는 각 **40,000토큰·1,200초**이고 `nodes=[]`, `tools=[]`이므로 대상 실행 권한이 없다. 모델이 다르므로 소유자 승인은 각 1건씩 필요하다. 이 단일 기준선도 그래프 문맥을 받으므로 **일반 무구조 프롬프트와의 비교가 아님**. 모델 강도와 관점 분담이 동시에 달라지는 개발 비교이며 최종 가설별 실행 `F`가 아니다. 새 영수증이 없으므로 **두 모델 호출·발견 건수·LLM 품질 판정·실제 USD 비용은 모두 미실시/미측정**이다. 승인 설정은 저장소 SHA·모델·프롬프트·전송 자료를 묶지만 현재 CLI의 `--symbol` 값은 영수증에 직접 묶지 않는다. 실제 비교 시 두 결과의 선택 범위·출처 ID와 요청 명령을 따로 대조해야 한다. 모델 전용 설정의 `image_digest` 필드는 스키마상 필수일 뿐 이 경로에서 컨테이너를 실행하지 않는다.

**판정 계약:** 각 군의 제출 후보와 부분 실패를 모두 남기고, 같은 루트·원인·발생 조건·영향의 관점별 중복은 한 위험으로 병합한다. 군 간 의미상 중복·수정 권고 품질은 군명을 숨긴 별도 판정으로 구분하며, 기존 회귀·실행 재현이 없는 LLM 동의만으로 버그를 확인했다고 쓰지 않는다. 우선 비교 수치는 제출 건수, 확인된 고유 발견, 보류·거짓 경보, 판정된 권고 품질과 실제 사용 토큰·시간이다. 이번 공개 파일럿에는 전체 버그 수 분모가 없으므로 Recall을 보고하지 않는다. 최종 동결 80사례 평가의 성과로 합산하지 않는다.

회귀 `python3 -B -m unittest discover -s tests -q`는 **166개 실행(165개 통과·1개 건너뜀)**, `python3.14 -B -m unittest discover -s tests -q`는 **166개 통과**. 새 회귀는 스캔 파서 표시를 다르게 만든 실제 Git 출처 묶음을 시험용 승인으로 검토해, 수정 전 모델 요청까지 진행하던 경로가 수정 후 **요청·영수증 소비 없이 거절되는지** 확인한다. 이는 Python 3.14 원본에서 결함을 발견했다는 뜻이 아니라, 같은 소스를 잘못된 파서로 분석하지 않는 안전 장치다.

clone·출처 묶음·모델 설정은 모두 `/tmp`의 개발 자료로 장기 보존되는 독립 평가 원자료가 아니다. 승인 뒤의 실제 호출 결과와 원자료 한계는 다음 절에 기록한다.

## 자유 탐지 개발 파일럿: 소유자 승인 후 두 모델의 실제 결과

소유자가 위 두 RunManifest 해시를 단말에서 직접 승인한 영수증을 각각 검증했다. 같은 Git `84c5a9e11a9e58262599e3d772f5386924e02ca7`, Python 3.14 출처 묶음 `5da0851315998c1dcec0c9118b3fe27ada3e33bdb0502e24c7087cd4b2562fed`, 선택 범위 `module:backend/app/api/routes/items.py`, 구조화 프롬프트, 각 40,000토큰·1,200초 상한으로 호출했다. 두 결과의 `scope=selected_symbol_only`, `symbol`, 문맥 노드 7개, `source_bytes=10019`, `truncated=false`가 일치했다. `--single-baseline`도 그래프를 받으므로 **일반 무구조 LLM과의 비교가 아니다**.

```sh
set -o pipefail && python3.14 -B src/diagnose_approved.py /tmp/wreckfish-open-discovery-py314-source-20260926/runs/5da0851315998c1dcec0c9118b3fe27ada3e33bdb0502e24c7087cd4b2562fed /tmp/wreckfish-open-discovery-prep-20260926/strong.json /tmp/wreckfish-open-discovery-prep-20260926/strong-approval.json --symbol module:backend/app/api/routes/items.py --single-baseline | tee /tmp/wreckfish-open-discovery-prep-20260926/strong-result.json
set -o pipefail && python3.14 -B src/diagnose_approved.py /tmp/wreckfish-open-discovery-py314-source-20260926/runs/5da0851315998c1dcec0c9118b3fe27ada3e33bdb0502e24c7087cd4b2562fed /tmp/wreckfish-open-discovery-prep-20260926/system.json /tmp/wreckfish-open-discovery-prep-20260926/system-approval.json --symbol module:backend/app/api/routes/items.py | tee /tmp/wreckfish-open-discovery-prep-20260926/system-result.json
```

| 관측 | 강한 모델 단일 호출 | 작은 모델 다섯 관점 |
| --- | --- | --- |
| 모델 | `gpt-6-sol` | `gpt-6-luna` |
| 호출 및 상태 | `all` 1회 실패: `candidate_admission_invalid` | `structure` 완료 4,950토큰; `correctness` 완료 5,144; `performance` 완료 5,054; `concurrency` 완료 5,126; `tests` 예산 보류 0 |
| 총 사용량 / 모델 요청 시간 | **5,917토큰 / 20.689초** | **20,274토큰 / 15.217초**(완료된 4회 합계) |
| 채택된 임시 발견 / CLI 종료 | **0건 / 3** | **0건 / 3** |
| JSON 결과 SHA-256 | `c8611490d0d53a07b44f46d08a2f0863255d9c4c5c39b50d86cb8911ba023b2a` | `51bf55796b3ad956b3920cb55b093005539023cb64177377151b62b9b62efd54` |

두 JSON 원문은 위 `/tmp/wreckfish-open-discovery-prep-20260926/`에 있다. 각 완료/실패 요청의 요청·응답 SHA-256과 사용 토큰은 JSON `perspectives`에 기록됐다. `.used` 두 파일은 각각 승인된 RunManifest 해시 `9af3da3ec7789e6e465389daa534a23d05a9802f0d1d8f88d0787be8356043b4`, `e842df12b9c1d09f81c05b874eb34b92ccaa057d2962d7da01c3cf8e77246144`를 기록했다. 인증되지 않은 루프백 모델 서버는 호출 후 종료했다. **두 영수증은 소진됐으며 대상 코드·테스트·Profiler는 실행하지 않았다.** `/tmp` 원자료는 장기 보존 또는 독립 심사 원자료가 아니다.

강한 모델의 실패 코드는 후보의 접수 규칙 위반을 뜻한다. 모델 응답 **본문은 저장하지 않아** 어느 필드가 틀렸는지, 거절된 후보가 실제 결함인지 판정할 수 없다. 작은 모델의 4회 완료·후보 0건은 안전하다는 증거가 아니다. 이 파일럿에서 작은 모델은 강한 모델의 **3.43배 토큰**을 쓰고도 다섯 관점을 완료하지 못했다. 청구 원본 USD, 독립 정답, 다른 계열 LLM의 판정, 전체 버그 분모가 없어 확인된 결함·정밀도·재현율·우월성·A+ 등급은 모두 **미입증**이다. 모델과 분석 방식이 동시에 달라지므로 토큰 차이를 관점 분담의 단독 효과로 돌릴 수도 없다.

**실패 뒤의 별도 수정(재실측 아님):** 다섯째 `tests` 호출 전 남은 19,726토큰에서 기존 입력 JSON은 19,557바이트였다. 현재의 보수적 `입력 UTF-8 바이트 + 256` 예약식에서는 여유가 **-87**이라 전송 전 보류됐다. 원본 인증·위치 검증에 쓰는 문맥은 유지하고, 모델 입력에서 이미 전체 모듈을 실은 같은 파일의 함수 노드마다 반복하는 `blob_oid`·`source_sha256`만 뺐다. 같은 동결 문맥과 사용량으로 요청을 로컬에서 재구성하면 다섯째 입력이 **18,663바이트**, 사전 확인 여유가 **807**이다. 이는 요청 크기 계산과 시험용 공급자 응답의 다섯 관점 완료 확인이지 새 실모델 호출이나 실제 추가 발견이 아니다. 향후 호출에는 새 소유자 승인과 동결 조건의 별도 실측이 필요하다.

검증: 시험용 모델 응답을 사용한 다섯 관점 예산 경계 회귀 1건 통과. `python3 -B -m unittest discover -s tests -q`는 **167개 통과**, `python3.14 -B -m unittest discover -s tests -q`는 **167개 실행(166개 통과·1개 건너뜀)**. 두 명령은 실제 모델을 다시 호출하지 않았다.

## 반복 예산 보류 수정: 실제 입력 토큰으로 후속 관점 예약

이전에는 첫 관점부터 다섯째까지 **매번 요청 JSON의 UTF-8 바이트 수를 입력 토큰으로 예약**했다. 하지만 위 실제 호출은 관점당 약 5천 토큰을 사용했고, 다섯째 호출 전 남은 19,726토큰을 18,663바이트 입력으로 검사해 불필요하게 예산 경계에 걸렸다. 중복 해시 제거는 이 파일 하나에서만 807의 여유를 만든 조치였다.

`src/modules/diagnosis/model.py`는 첫 호출에서는 이전처럼 전체 요청 바이트 수와 고정 여유 256을 예약한다. 그 뒤에는 **같은 문맥을 공유하는 호출에서 제공자가 직전에 보고한 입력 토큰(캐시 입력 포함)**을 기준으로 잡고, 바뀐 두 관점 이름의 길이와 여유 256을 더한다. 실제 사용량은 매번 전체 승인 예산에서 차감하며, 응답 출력 상한은 남은 예산 이내로 유지한다. 입력 사용량 0·누락·초과 등 신뢰할 수 없는 응답에는 후속 호출을 중단한다. 다른 파일의 첫 호출, 실제 예산 부족, 시간 초과는 여전히 보류될 수 있다.

위 **수정 전 관측값으로만 계산**하면 다섯째 직전 잔액은 19,726토큰이다. 넷째 관점의 입력 토큰은 전체 사용량 5,126토큰보다 클 수 없으므로, 새 사전 예약은 최대 `5,126 + 11(concurrency) + 5(tests) + 256 = 5,398`토큰이다. 다섯째 요청의 사전 여유는 최소 **14,328토큰**이며 출력 상한 1,000토큰을 넣을 수 있다. 이는 같은 공급자 사용량이 반복된다는 조건의 **로컬 재계산**이지 실제 다섯째 모델 결과가 아니다. 제공자가 입력 계산을 갑자기 크게 바꾸면 사전 추정이 어긋날 수 있다. 실제 사용량이 잔액을 넘으면 사후 검증에서 초과로 실패·중단하며, 승인 예산 내 다섯 관점 완료를 보장하지 않는다.

회귀는 **수정 전 네 번만 호출되고 다섯째가 보류되는 경우**를 재현한 뒤, 수정 후 같은 합성 문맥·7,000토큰 상한에서 다섯 관점 모두 호출되는 것을 확인했다. 유효 입력 사용량 없는 응답·실제 한도 초과 응답은 이후 관점을 호출하지 않는 검사도 추가했다. `python3 -B -m unittest discover -s tests -q`: **168개 통과**. `python3.14 -B -m unittest discover -s tests -q`: **168개 실행(167개 통과·1개 건너뜀)**. 이 검사는 시험용 모델 응답이며 추가 소스 송신·실제 발견·A+ 우월성 실측이 아니다. 기존 영수증은 소진돼 재호출할 수 없다.

## 결함 발견 우선 재검토: 미검증 주장·비용·이전판

**접수 규칙은 결함의 중요도를 판정하는 단계가 아니었다.** `admit()`은 위치·출처 외에도 심각도 분류, 발생 조건, 다음 행동의 반증 방법과 예상 소요시간까지 요구한다. 기존에는 한 항목이 빠지거나 다른 출처 ID를 적으면 해당 관점의 모든 후보가 사용자 결과에서 사라졌다. 위 강한 모델의 `candidate_admission_invalid`가 어떤 필드 때문인지는 **응답 본문을 보관하지 않아 알 수 없다**. 그 주장을 참인 결함으로 되살릴 수도 없다.

후속 호출부터는 파싱된 모델 주장이 접수·출처 검사를 통과하지 못하면 CLI `unverified_candidates`에 원문 후보·관점·거절 코드를 별도로 남긴다. `check_code.py`의 `report.md`는 건수와 소유자 전용 `result.json` 위치를 알려준다. **이 목록은 봉인된 `findings`나 확인된 결함이 아니다.** 정답을 미리 판단해 가설을 없애지 않으면서도, 다른 파일·없는 줄·잘못된 출처 ID를 확인된 근거로 세탁하지 않는다. 출력이 JSON 자체로 해석되지 않으면 유효한 후보 객체를 복구할 수 없고 실패 상태만 기록한다. 합성 승인 진단에서 반증 방법이 없는 후보와 잘못된 출처 ID의 후보 두 건이 `unverified_candidates`에 남고, 봉인된 결과에는 0건임을 확인했다. 사용자 단일 진단 리포트에도 별도 미검증 목록 안내가 표시된다.

**토큰 상한에 대한 선택:** 개발 탐색에서 **40,000토큰은 품질 최적값으로 입증된 적이 없다**. 이번 작은 모델은 네 번에 20,274토큰을 쓰고도 후보를 내지 못했고, 이전 Prefect 개발 비교는 23,165토큰으로 같은 모델의 일반 단일 검토 2,201토큰보다 10.52배 썼다. 그래프 문맥을 관점마다 다시 보내는 비용을 포함하지만, 호출별 입력·출력 비용과 실제 USD 청구 원본은 없어 반복 문맥이 차지한 몫을 분리할 수 없다. **개발용**은 사례별 승인 상한을 충분히 크게 잡고 사용량·중복 입력·완료율을 관찰하는 비동결 실험이 합리적이다. **최종 우월성 비교**는 같은 총 토큰·시간 상한이 없으면 긴 호출을 무제한 사용하는 시스템과 단일 모델의 비교가 달라진다. 현재 RunManifest와 일회용 승인에는 양의 총 토큰 상한이 필수다. 이 보호를 제거하거나 소진된 영수증을 늘리지 않았으며, 무제한 개발 경로·최종 계약 변경도 구현하지 않았다. 상한 자체보다 불필요한 반복 입력의 비용/발견 효과를 같은 사례에서 비교해야 한다.

**이전 커밋 제안:** 결함 수정 전·후의 실제 공개 커밋을 개발용 짝으로 사용하는 것은 적절하다. 이미 Prefect의 이전판 `ZeroDivisionError`·수정판 검사 통과를 좁게 확인했다. 하지만 출력을 본 뒤 결함이 잘 보이는 판본만 바꾸면 성공률이 부풀려진다. 다음 비교에서는 사용권·지원 Python·원본 Git·동일 분석 범위·수정 전 행동 검사와 수정 후 대조를 **모델 호출 전에** 고정해야 한다. 수정 후 판본을 저장소 전체의 '정상'으로 취급하지 않고 해당 결함의 대조로만 쓴다. 공개 수정 내역은 개발 증거이며 숨긴 최종 정답이 아니다. 새 대상 소스 전송이나 대상 실행에는 각각 새로운 소유자 승인이 필요하다.

검증: 후보 객체가 접수 실패 뒤 결과에서 사라지는 경우를 재현하고, 수정 뒤 CLI의 미검증 목록과 별도 봉인 결과, `report.md` 안내를 실행으로 확인했다. 전체 `python3 -B -m unittest discover -s tests -q` **169개 통과**, `python3.14 -B -m unittest discover -s tests -q` **169개 실행(168개 통과·1개 건너뜀)**. 실제 이전 모델 후보의 내용·새로운 결함 발견·실모델 비용 절감은 측정하지 않았다.

## 다음 공개 개발 사례 사전 동결: Starlette 다중 바이트 범위의 조기 EOF (모델 호출 전)

**2026-09-27 선택, 새 모델 응답 관측 전 고정.** 앞서 모델 비교에 사용한 Prefect 재시도/지연 0과 다른 결함이다. [상류 최초 논의 #3582](https://github.com/Kludex/starlette/discussions/3582)는 오래된 파일 크기 정보로 다중 `Range` 응답을 보낼 때 파일이 짧아지면 빈 청크를 계속 전송하며 루프가 진행하지 않는다고 보고한다. [상류 수정 PR #3583](https://github.com/Kludex/starlette/pull/3583)은 빈 읽기에서 중단하는 변경과 회귀 검사를 포함하며, [병합 커밋](https://github.com/Kludex/starlette/commit/9774b08ef457e91e37e38c8a1abbfa3510427f21)의 직접 부모가 수정 전 SHA임을 Git에서 대조했다.

| 동결 항목 | 수정 전 | 수정 후 |
| --- | --- | --- |
| 상류 Git commit (40자) | [`ba504c555fbd6d02ea584c295667185a10453700`](https://github.com/Kludex/starlette/tree/ba504c555fbd6d02ea584c295667185a10453700) | [`9774b08ef457e91e37e38c8a1abbfa3510427f21`](https://github.com/Kludex/starlette/tree/9774b08ef457e91e37e38c8a1abbfa3510427f21) |
| 같은 Python 파일·분석 심볼 | [`starlette/responses.py:426-460`, `FileResponse._handle_multiple_ranges`](https://github.com/Kludex/starlette/blob/ba504c555fbd6d02ea584c295667185a10453700/starlette/responses.py#L426-L460) | [`starlette/responses.py:426-462`, 같은 메서드](https://github.com/Kludex/starlette/blob/9774b08ef457e91e37e38c8a1abbfa3510427f21/starlette/responses.py#L426-L462) |
| Git 출처 묶음 ID / 파서 | `72eea68d2993f7f34398dad7ea1acc2c30449f0724a54efff860ff67abcbd10d` / Python 3.14.3 | `7702456530c84158a6d585c0656a38131006681dd2883c8828f1e269f2c44d5a` / Python 3.14.3 |

`git rev-parse 9774b08ef457e91e37e38c8a1abbfa3510427f21^`의 출력은 정확히 `ba504c555fbd6d02ea584c295667185a10453700`이고 `merge-base --is-ancestor`도 통과했다. PR 병합 diff는 **해당 Python 파일의 빈 청크 검사 2행과 `tests/test_responses.py` 회귀 검사 추가**뿐이다. 수정 전 루프는 `file.read()`가 `b""`여도 `start += len(chunk)`가 진행되지 않고 `more_body=True`를 보낸다. 수정 후 같은 메서드는 빈 청크를 읽으면 `RuntimeError`를 낸다. [상류 회귀 검사 `test_file_response_multi_range_unexpected_eof`](https://github.com/Kludex/starlette/blob/9774b08ef457e91e37e38c8a1abbfa3510427f21/tests/test_responses.py#L1085-L1101)는 10바이트 파일의 `stat_result`를 보관한 뒤 내용을 3바이트로 줄이고 `Range: bytes=0-2,5-7` 요청에서 1초 제한 안에 정확한 예외가 나오는지 확인한다. 보고자 논의의 **세 번의 빈 청크 후 중지하는 유한 재현**과 이 상류 회귀 검사가 행동 oracle의 출처다. **우리 쪽에서 어느 판본의 대상 코드·oracle도 실행하지 않았으므로 전/후 통과·실패 실측은 아직 없다.**

두 commit의 `pyproject.toml`은 `requires-python = ">=3.10"` 및 Python 3.14 classifier를 선언한다. 두 판본의 [BSD-3-Clause 원문](https://github.com/Kludex/starlette/blob/9774b08ef457e91e37e38c8a1abbfa3510427f21/LICENSE.md)과 라이선스 선언을 확인했다. 선택한 Python 3.14.3은 지원 범위에 속한다. Git 원본 2개에서 각각 추적 Python **84개**를 대상 import 없이 정적 스캔했고, 저장된 `evidence.jsonl`에 `parse_error`가 없었으며 `verify_git_source`로 각각 84개 blob/OID/해시를 대조했다. 두 tree에 Git submodule gitlink는 없었다. `--symbol FileResponse._handle_multiple_ranges`의 선택 메서드 원문은 양쪽 문맥에 전부 포함됐다. 검색 주변 노드는 양쪽 모두 `truncated=true`이므로 전체 문맥 완전성이나 다른 결함 부재를 뜻하지 않는다.

재현 가능한 **무실행 출처 확보·스캔 계획**은 다음과 같다. 경로 네 개는 모두 새 `/tmp` 위치여야 하고, 재실행 시 이미 존재하는 경로 대신 새로운 이름으로 바꾼다. Git SHA를 먼저 대조하고 이후 진단에서도 **동일한 Python 3.14.3·선택 심볼**을 쓴다. 현 시점의 실제 정적 출처 묶음은 각각 `/tmp/wreckfish-public-pair-starlette-before-scan-20260927/runs/72eea68d2993f7f34398dad7ea1acc2c30449f0724a54efff860ff67abcbd10d`와 `/tmp/wreckfish-public-pair-starlette-after-scan-20260927/runs/7702456530c84158a6d585c0656a38131006681dd2883c8828f1e269f2c44d5a`이다. 새 경로로 스캔하면 출처 ID도 달라지므로 CLI가 반환한 `source_bundle`을 사용한다. `/tmp` 자료는 장기 보존된 독립 평가 원자료가 아니다.

```sh
FIXED_REPO=/tmp/wreckfish-starlette-eof-fixed-replay
BEFORE_REPO=/tmp/wreckfish-starlette-eof-before-replay
BEFORE_SOURCE_ROOT=/tmp/wreckfish-starlette-eof-before-source-replay
FIXED_SOURCE_ROOT=/tmp/wreckfish-starlette-eof-fixed-source-replay
git init "$FIXED_REPO"
git -C "$FIXED_REPO" fetch --depth=2 https://github.com/Kludex/starlette.git 9774b08ef457e91e37e38c8a1abbfa3510427f21
git -C "$FIXED_REPO" switch --detach 9774b08ef457e91e37e38c8a1abbfa3510427f21
git -C "$FIXED_REPO" worktree add --detach "$BEFORE_REPO" ba504c555fbd6d02ea584c295667185a10453700
git -C "$FIXED_REPO" rev-parse 9774b08ef457e91e37e38c8a1abbfa3510427f21^
git -C "$FIXED_REPO" merge-base --is-ancestor ba504c555fbd6d02ea584c295667185a10453700 9774b08ef457e91e37e38c8a1abbfa3510427f21
python3.14 -B src/scan_sources.py "$BEFORE_REPO" ba504c555fbd6d02ea584c295667185a10453700 "$BEFORE_SOURCE_ROOT" --symbol FileResponse._handle_multiple_ranges
python3.14 -B src/scan_sources.py "$FIXED_REPO" 9774b08ef457e91e37e38c8a1abbfa3510427f21 "$FIXED_SOURCE_ROOT" --symbol FileResponse._handle_multiple_ranges
```

**향후 승인/판정 경계:** 상류에 공개된 결함·수정·회귀 검사는 이 한 결함의 **개발용** oracle일 뿐 숨긴 최종 독립 gold가 아니다. 수정 commit은 **이 결함에 한해서만** 음성 대조군이며 저장소 전체 무결함을 증명하지 않는다. 먼저 동일 수정 전 SHA·`FileResponse._handle_multiple_ranges` 범위·모델/프롬프트·총 토큰/시간·후보 병합·판정 절차를 두 군에 맞춰 동결해야 한다. 이후 정확한 새 RunManifest마다 소유자가 본인 대화형 단말에서 새 일회용 영수증을 발급해야만 소스 모델 전송 또는 대상 실행을 고려한다. 직접 `src/diagnose_approved.py`를 사용할 때는 반드시 새 소유자 전용 비공개 경로에 `--response-output "$NEW_PRIVATE_RESPONSE_DIR"`을 지정하여 접수 실패 응답까지 감사용 원자료를 남긴다. 모델 전용 RunManifest는 아래처럼 준비했지만, 영수증·응답 보관 디렉터리는 만들지 않았다. 소진된 영수증을 재사용하지 않는다. 상류 oracle의 실행도 별도 승인·격리 조건 뒤에만 계획하며 무한 루프 가능성이 있는 수정 전 검사는 시간 상한과 유한 중지 조건을 갖춰야 한다. 이번에 수행한 것은 Git/라이선스·정적 출처 확인뿐이다. 새 모델 응답·검증된 발견·대상 런타임·실제 USD 청구·A+ 성공 주장은 **없다**.

### 모델 송신 전 준비된 네 설정(미승인)

소유자 전용 `/tmp/wreckfish-starlette-pair-prep-20260927/`(0700)에 모델 전용 `nodes=[]`, `tools=[]` 설정을 준비했다. 네 설정 모두 현행 구조화 프롬프트 SHA-256 `70996a3f6f4ad95f9631b0383dfbebf48db60602e2c21bd059a0a581b7afe116`, 루프백 모델 주소, **80,000토큰·1,200초** 총 상한으로 동일하다. 개발용 높은 상한은 이전 40,000토큰 보류를 재평가하려는 선택이지 무제한 호출·비용 효과 입증이나 최종 평가 한도 변경이 아니다. 강한 군은 같은 그래프 문맥의 `--single-baseline`이므로 **무구조 plain LLM 군은 아니다**.

| 수정 상태 | 모델·방식 | RunManifest 파일 | 승인 대상 해시(SHA-256) |
| --- | --- | --- | --- |
| 수정 전 `ba504c555fbd6d02ea584c295667185a10453700` | `gpt-6-sol` 1회 | `before-strong.json` | `d5fc5219714d37f0dfa51e9ec4cf3b10aefd5ebe9c8a7f7b8b155bcafac5bee9` |
| 수정 전 동일 SHA | `gpt-6-luna` 다섯 관점 | `before-system.json` | `1f66bf31fa1d025fde245ed237a4527dc839444a5f4598972c947d33c6b26890` |
| 수정 후 `9774b08ef457e91e37e38c8a1abbfa3510427f21` | `gpt-6-sol` 1회 | `after-strong.json` | `bbe44e5fdfbb321b33ce22fe3e191d56352d760609946f53277357e5ea9cacb9` |
| 수정 후 동일 SHA | `gpt-6-luna` 다섯 관점 | `after-system.json` | `b7a588bd4583754fb7ddbfac692d97d01a31152766212dc56e78c0402a1cee1d` |

Python 3.14.3에서 출처 두 묶음을 다시 검증해 추적 파일 각 84개, `parse_error` 0개를 확인했다. 네 설정으로 실제 `diagnose_approved.py --symbol FileResponse._handle_multiple_ranges --response-output ...`를 실행하면 **영수증 없음·종료 2, 응답 저장 경로 0개**로 모델 전송 전에 거절됨을 확인했다. 소유자만 자신의 대화형 단말에서 원본 Git·설정·상한·해시를 읽고 아래 네 영수증을 각자 발급할 수 있다. **이 명령은 아직 수행하지 않았다.**

```sh
python3.14 src/approve_run.py /tmp/wreckfish-public-pair-starlette-parent-full-20260927 /tmp/wreckfish-starlette-pair-prep-20260927/before-strong.json /tmp/wreckfish-starlette-pair-prep-20260927/before-strong-approval.json
python3.14 src/approve_run.py /tmp/wreckfish-public-pair-starlette-parent-full-20260927 /tmp/wreckfish-starlette-pair-prep-20260927/before-system.json /tmp/wreckfish-starlette-pair-prep-20260927/before-system-approval.json
python3.14 src/approve_run.py /tmp/wreckfish-public-pair-starlette-full-20260927 /tmp/wreckfish-starlette-pair-prep-20260927/after-strong.json /tmp/wreckfish-starlette-pair-prep-20260927/after-strong-approval.json
python3.14 src/approve_run.py /tmp/wreckfish-public-pair-starlette-full-20260927 /tmp/wreckfish-starlette-pair-prep-20260927/after-system.json /tmp/wreckfish-starlette-pair-prep-20260927/after-system-approval.json
```

승인 후에도 먼저 설정/영수증/Git을 다시 대조하고, 각 호출마다 **새** `--response-output /tmp/wreckfish-starlette-pair-prep-20260927/{판본}-{군}-responses` 경로를 사용해야 한다. 경로는 진단 명령이 자체 생성하며 기존 경로·심볼 불일치·소진된 영수증을 허용하지 않는다. 저장된 것은 정규화된 제공자 응답으로, 원시 HTTP 봉투까지는 보관하지 않는다. 수정 전/후의 알려진 결함에 해당하는 위치·원인만 짝 비교하고 다른 진짜 후보는 별도 미확인으로 남긴다. 첫 모델 호출·대상 실행·다른 계열 판정·독립 최종 점수는 **아직 없음**.

## Starlette 고정 판본 × 두 모델: 소유자 승인 후 실제 자유 탐지 (2026-09-27)

소유자가 네 RunManifest 해시를 대화형 단말에 입력해 발급한 영수증을 `verify_approval`로 재확인했다. `verify_git_source`로 두 Git의 추적 Python 파일 각 84개·파싱 오류 0개를 다시 대조하고, `/v1/models`에서 승인한 두 모델을 확인했다. `python3.14 -B src/diagnose_approved.py`를 네 영수증당 정확히 한 번 실행했다. 같은 `--symbol FileResponse._handle_multiple_ranges`, 프롬프트 SHA `70996a3f6f4ad95f9631b0383dfbebf48db60602e2c21bd059a0a581b7afe116`, 각 80,000토큰·1,200초 한도, `--response-output`의 새 개인 경로를 사용했다. 강한 모델은 `--single-baseline`, 작은 모델은 다섯 관점이다. 모델 전용 설정이므로 대상 코드·테스트·Profiler는 실행하지 않았다. 네 영수증 모두 `.used`로 소진됐고 루프백 서버는 종료했다.

| Git 판본·군 | 호출/완료/실패 | 미검증 후보 / 접수 발견 | 제공자 보고 토큰 / 요청 시간 합 | 개인 결과 JSON SHA-256 |
| --- | --- | --- | --- | --- |
| 수정 전 `ba504c5…`, `gpt-6-sol` | 1 / 0 / 1 (`candidate_ungrounded`) | 3 / 0 | 11,125 / 33.826초 | `before-strong-result.json` `1676440118ba1eed6be795a6b2e9fdbbeedcaec9a93947ee5fd914cd9528db17` |
| 수정 전 동일, `gpt-6-luna` | 5 / 4 / 1 (`correctness`: `candidate_ungrounded`) | 1 / 0 | 48,453 / 13.339초 | `before-system-result.json` `06ce8feef61aa881bbebfe0208e74254fa7e7a5aa52f120a41adeb0776449f53` |
| 수정 후 `9774b08…`, `gpt-6-sol` | 1 / 0 / 1 (`candidate_ungrounded`) | 4 / 0 | 12,027 / 39.519초 | `after-strong-result.json` `04b9a90dc8c825e6e4a306dc9b2b17b4711b27e4976d2a4297c28044ea2b5111` |
| 수정 후 동일, `gpt-6-luna` | 5 / 4 / 1 (`tests`: `candidate_ungrounded`) | 1 / 0 | 49,540 / 30.726초 | `after-system-result.json` `3e186531e7c87c77df875b47a181db3db51b9188bd79cba399ec73150b4b4623` |

각 CLI 종료 코드는 **3**(분석 불완전), `findings=[]`, `runtime_attested=false`다. 두 판본의 선택 메서드 원문은 포함됐으나 주변 문맥은 `truncated=true`다(선택 문맥 23,654/23,934바이트). 개인 결과 원문은 `/tmp/wreckfish-starlette-pair-prep-20260927/{before,after}-{strong,system}-result.json`, 정규화된 모델 응답은 같은 위치의 `*-responses/`(0700/0600)에 각각 1·5·1·5건 보관했다. 12개 응답 파일의 바이트 SHA-256과 결과의 `response_artifacts`를 모두 대조했다. 이는 원시 HTTP 봉투가 아니라 정규화된 제공자 응답이며, `/tmp`는 영구 보관소가 아니다. 표의 시간은 요청별 `wall_seconds` 합이지 전체 CLI 실행 시간이나 요금이 아니다. 작은 모델은 수정 전 토큰이 강한 모델의 **4.36배**, 수정 후 **4.12배**였다. 실제 USD 청구액은 확인하지 못했다.

**알려진 한 결함과의 별도 의미 대조:** 수정 전 강한 모델의 *미검증* 후보 1건은 `starlette/responses.py:448-451`의 빈 `read()` 후 `start`가 증가하지 않는 무진전 루프와, 파일이 `stat` 뒤 짧아진다는 조건을 설명했다. 상류 수정은 같은 루프의 빈 청크에서 `RuntimeError`를 내도록 했다. 따라서 이 **원시 가설 한 건은 상류에 공개된 EOF 결함의 위치·기전에 부합**한다. 그러나 해당 관점은 근거 접수에 실패했고 봉인 발견은 0건이다. 수정 전 작은 모델의 미검증 후보 1건은 `stat_result`의 비정규 파일 검증 주장으로, 이 EOF 결함과 무관하다. 수정 후 두 모델의 미검증 후보 5건도 EOF 무진전 주장이 아니다. 이외 주장에 대한 참·거짓은 별도 판정하지 않았으며, 수정 후 저장소 전체를 음성 정답으로 취급하지 않는다.

### 원문 탐지와 시스템 접수의 차이: 동일한 공개 EOF 결함 한 건

기존 승인 응답 12개와 결과 파일 4개를 다시 읽고 파일 SHA-256을 대조했다. **추가 모델 호출·대상 실행·새 채점기는 없다.** 원문 일치는 위에 사전 지정한 *다중 Range 조기 EOF 무진전*의 위치·조건·기전을 응답이 지적했는지만 본 개발용 의미 대조다.

| 판본 | 모델 | 원문 후보 전체 | 알려진 EOF 원문 일치 | 시스템 접수 `findings` |
| --- | --- | ---: | ---: | ---: |
| 수정 전 `ba504c5…` | `gpt-6-sol` | 3 | **1** | **0** |
| 수정 전 동일 | `gpt-6-luna` | 1 | 0 | 0 |
| 수정 후 `9774b08…` | `gpt-6-sol` | 4 | 0 | 0 |
| 수정 후 동일 | `gpt-6-luna` | 1 | 0 | 0 |

수정 후 강한 모델의 *단일* Range 조기 EOF 주장은 이 **다중** Range 무진전 결함의 일치 건수에 넣지 않았다. 원문 일치 1건도 접수 발견으로 소급하지 않으며, 다른 원문 후보의 참·거짓이나 모델의 전체 정확도는 판정하지 않았다. 수정 후 저장소 전체가 결함이 없다는 뜻도 아니다. 이 차이는 모델 탐지와 현행 형식 접수의 손실을 나란히 보여 줄 뿐, 최종 80사례 또는 A+ 우월성 지표가 아니다.

통합 `check_code.py`의 `report.md`는 이제 기존 `unverified_candidates`의 **모델 주장 위치·원인·거절 이유**를 별도 미검증 절에 보여 준다. 모델 문자열은 기존 보고서의 HTML/Markdown/제어문자 무해화 처리를 거치며 `findings`·우선순위·봉인된 다섯 JSON은 바꾸지 않는다. 합성 Git 소스·시험용 제공자 응답으로 실제 통합 CLI 경로를 실행해 종료 3, 미검증 1건의 위치/원인 표시, 봉인 발견 0건, HTML 태그 무해화, 출력 디렉터리 0700을 직접 확인했다(외부 모델 호출 0). 전체 회귀 `python3 -B -m unittest discover -s tests -q` **172개 통과**, `python3.14 -B -m unittest discover -s tests -q` **172개 실행(171개 통과·1개 건너뜀)**. 이 합성 기본 동작 확인을 위 네 승인 모델의 새 실행이나 EOF 탐지 성능 개선으로 세지 않는다.

실패 원인은 사후 원자료로 식별했다. 두 판본의 미검증 후보 **9건 모두** `evidence_ids`에 소스 기록 ID 대신 그래프 노드 ID를 넣었고, 첫 접수 단계는 `[source_evidence[location.path]]`만 허용한다. 그 밖에 9건 모두 `trigger` 필드를 빠뜨렸고, 일부는 `condition and trigger`로 두 필드를 합치거나 `taxonomy`를 `correctness/concurrency`처럼 복수로 적었다. 당시 `PROMPT`는 `source_evidence`와 그래프 ID를 구별하라고 명시하지 않았으며 `condition and trigger`라고 안내한 반면, 실제 `admit()`은 `condition`·`trigger` 분리를 요구했다. 근거 경계를 소급 완화하거나 예전 결과를 접수 발견으로 재기록하지 않는다. 프롬프트 계약 수정은 **새 버전·새 승인**에만 적용한다.

이 네 호출은 개발 공개 사례의 **후보 생성과 접수 손실 관찰**이다. 독립 실행 oracle, 별도 계열 LLM 판정, 숨긴 80사례, 같은 비용의 최종 `A_plain_llm` 대 `F_runtime_feedback`, 실제 USD·A+ 우월성 증거는 아니다. 상류 회귀 검사를 이번에 실행하지 않았으므로 전후 런타임 결과도 이 실측에 포함하지 않는다.

### 실측 후 모델 출력 계약 수정 (기존 네 결과와 분리)

`src/modules/diagnosis/model.py`의 구조화 `PROMPT`에서 `condition`·`trigger`를 각각 요구하고 `taxonomy` 허용값을 단일 값으로 명시했다. `evidence_ids`는 그래프 노드 ID가 아니라 `context.source_evidence[location.path]`의 **파일 출처 ID 한 개**를 배열에 담도록 지정했다. 출처/줄/후보 접수 검사와 네 승인 결과는 변경하지 않았다. 새 프롬프트 SHA-256은 `9df13fbb8997b310bc18f09d0672ccae2380a052d9897ee3c6d7f8ce823f48a7`; 과거 네 RunManifest·영수증은 이 계약에서 재사용할 수 없다.

검증: 실제 `--prompt-hash` CLI가 새 SHA를 출력했고, 과거 설정으로 실제 진단 CLI를 시도하면 **모델 전송 전 종료 2**(`Approved model prompt or network declaration does not match`)였다. 시험용 요청 1건은 입력의 파일 출처 ID와 실제 전송할 지시문을 대조하고 필드가 분리된 가설을 임시 후보 1건으로 수용했다(외부 모델 호출 0). 전체 회귀 `python3 -B -m unittest discover -s tests -q` **172개 통과**, `python3.14 -B -m unittest discover -s tests -q` **172개 실행(171개 통과·1개 건너뜀)**. 모델이 새 지시를 지키는지와 알려진 EOF 결함을 새 승인 호출에서 접수하는지는 아직 검증하지 못했다.

### 수정된 프롬프트 재실측 준비 (소유자 승인 전)

기존 네 결과와 분리해 새 프롬프트 해시 `9df13fbb8997b310bc18f09d0672ccae2380a052d9897ee3c6d7f8ce823f48a7`로만 바꾼 모델 전용 RunManifest 네 개를 소유자 전용 `/tmp/wreckfish-starlette-prompt-v2-prep-20260927/`에 준비했다. 기존 판본·모델·80,000토큰/1,200초 상한·`nodes=[]`·`tools=[]`·전송 범위 `source,context`는 유지한다. 이 개발용 비교는 새로운 프롬프트의 **접수율을 재측정**하기 위한 것이며, 앞선 호출과 프롬프트·시점이 달라 효과의 원인을 단정하지 않는다.

| 판본·군 | 신규 설정 | 승인 화면의 RunManifest SHA-256 |
| --- | --- | --- |
| 수정 전·`gpt-6-sol` 단일 호출 | `before-strong.json` | `ab5e4f6c2cfb685e9eca0ffa08a3a96c735ad3a07a42a962da5417fc1af7e0ca` |
| 수정 전·`gpt-6-luna` 다섯 관점 | `before-system.json` | `b07ca02ec890df785c0ebad23c4fcc186b4d415d3611927987b62f59ffa7b668` |
| 수정 후·`gpt-6-sol` 단일 호출 | `after-strong.json` | `89e362175eaa06514947c69d4b4249f6bc83fdb53a3cac220995bfbb8eab62ab` |
| 수정 후·`gpt-6-luna` 다섯 관점 | `after-system.json` | `219e3323908eaaa409af241e792eff7f38f11581e17a1b7854293eda8e011382` |

`verify_git_source`로 앞서 고정한 두 묶음의 Git SHA·Python 출처 84개씩을 다시 대조했다. 네 설정 모두 `manifest_hash`·`validate_model_plan`을 통과했고, 원설정과 비교해 **프롬프트 해시만** 다르다. 설정 디렉터리 0700·파일 0600을 확인했다. 실제 Python 3.14 `diagnose_approved.py --symbol FileResponse._handle_multiple_ranges --response-output` 네 경로 모두 신규 영수증이 없어 **종료 2**, 응답 저장 디렉터리 생성 0건이었다. 소스 전송·대상 실행·새 모델 응답은 **0건**. `/tmp` 준비물은 영구 제출 증거가 아니며 소실 시 출처·설정을 다시 검증하고 새 해시를 사용해야 한다.

소유자는 실제 실행을 원할 때 본인 대화형 단말에서 아래 네 명령의 **표시된 Git·설정·해시를 각각 직접 검토·입력**해야 한다. 대화로 동의하거나 과거 영수증을 재사용해서는 안 된다. 호출 전 두 군의 `--symbol` 범위를 동일하게 고정하고, 프록시를 필요한 동안에만 기동하며, 각 호출은 신규 개인 `--response-output` 경로에 정규화된 제공자 응답을 남겨야 한다.

```sh
python3.14 src/approve_run.py /tmp/wreckfish-public-pair-starlette-parent-full-20260927 /tmp/wreckfish-starlette-prompt-v2-prep-20260927/before-strong.json /tmp/wreckfish-starlette-prompt-v2-prep-20260927/before-strong-approval.json
python3.14 src/approve_run.py /tmp/wreckfish-public-pair-starlette-parent-full-20260927 /tmp/wreckfish-starlette-prompt-v2-prep-20260927/before-system.json /tmp/wreckfish-starlette-prompt-v2-prep-20260927/before-system-approval.json
python3.14 src/approve_run.py /tmp/wreckfish-public-pair-starlette-full-20260927 /tmp/wreckfish-starlette-prompt-v2-prep-20260927/after-strong.json /tmp/wreckfish-starlette-prompt-v2-prep-20260927/after-strong-approval.json
python3.14 src/approve_run.py /tmp/wreckfish-public-pair-starlette-full-20260927 /tmp/wreckfish-starlette-prompt-v2-prep-20260927/after-system.json /tmp/wreckfish-starlette-prompt-v2-prep-20260927/after-system-approval.json
```

영수증이 생기더라도 이 네 번은 **정적 모델 비교**만 허용한다. 상류 EOF 검사의 대상 실행에는 별도 RunManifest·소유자 승인·유한 중단 조건이 필요하다. 개발 사례의 접수율 변화와 최종 독립 80사례·USD 청구·A+ 판정은 합산하지 않는다.

### 수정된 프롬프트: 소유자 승인 후 네 건 실제 진단

소유자가 위 네 RunManifest의 해시를 본인 단말에 직접 입력해 새 영수증을 발급했다. `verify_approval`·`verify_git_source`로 승인 해시, 이전/수정 후 Git, 추적 Python 각 84개를 대조한 뒤 Python 3.14 `diagnose_approved.py`를 **영수증별 한 번씩** 실행했다. 두 모델은 같은 판본에서 `--symbol FileResponse._handle_multiple_ranges`·80,000토큰/1,200초 상한·구조화 프롬프트 `9df13fbb8997b310bc18f09d0672ccae2380a052d9897ee3c6d7f8ce823f48a7`을 사용했다. 강한 모델은 `--single-baseline` 1회, 작은 모델은 다섯 관점이다. 모델 전용 `nodes=[]`·`tools=[]`; **대상 코드·테스트·profiler는 실행하지 않았다.**

| 판본·군 | 완료/실패·CLI 종료 | 원문 후보 / 접수 `findings` / 미검증 | 제공자 보고 토큰·요청 시간 합 | 개인 결과 JSON SHA-256 |
| --- | --- | --- | --- | --- |
| 수정 전·`gpt-6-sol` | 1/0·0 | 4 / 4 / 0 | 12,239·48.408초 | `before-strong-result.json` `3bc7f1b23805521103690030095323527e53df6cd4043c0620cb34e9e5d2533a` |
| 수정 전·`gpt-6-luna` | 4/1(`correctness: candidate_ungrounded`)·3 | 3 / 2 / 1 | 50,583·65.533초 | `before-system-result.json` `d1d07b7ccfa3026d69ccc48372803c2001e921d51b3cdc0eddce88830e79fd41` |
| 수정 후·`gpt-6-sol` | 1/0·0 | 4 / 4 / 0 | 11,761·34.043초 | `after-strong-result.json` `148a98d84333e5ab5af23492a5ada9312703d26fc5af5dedca32cf0e70473898` |
| 수정 후·`gpt-6-luna` | 5/0·0 | 1 / 1 / 0 | 49,749·27.159초 | `after-system-result.json` `76009e3b9d38f047203d8ad9faf04a1dd9e550c10a6afc8d3a88adb29ed738d8` |

네 실행의 선택 문맥은 판본별 각각 **23,654/23,934바이트**로 양군이 같고, 주변 문맥은 둘 다 `truncated=true`다. 실제 호출은 총 12회 중 11회 완료·1회 관점 분류 불일치로 실패, 원문 후보 12건 중 **임시 접수 11건·미검증 1건**이다. 각 호출의 정규화 응답을 `*-responses/`에 보관하고 결과의 `response_artifacts.response_sha256`·관점별 `response_sha256`·실제 파일 SHA-256이 모두 일치하는지 대조했다(디렉터리 0700·파일 0600). 네 일회용 영수증의 `.used`도 확인했고 루프백 프록시는 호출 직후 종료했다. `/tmp`의 원자료는 영구 보존·독립 심사 자료가 아니다.

**사전 지정한 다중 Range 조기 EOF 한 건과의 개발용 대조:** 수정 전 강한 모델의 접수 후보 하나는 `starlette/responses.py:449-452`의 빈 `file.read()` 뒤 `start`가 증가하지 않는 조건과 빈 청크 시 중단·검사 권고를 명시했다. 이는 실제 수정이 추가한 `if not chunk: raise RuntimeError(...)`와 **위치·발생 조건·기전이 부합**한다. 수정 전 작은 모델의 원문 후보 세 건도 같은 EOF 무진전을 기술했다. 그중 두 건은 접수됐지만 `location`이 `438-440`(헤더 설정)과 `447`(헤더 전송)로, 실제 읽기·빈 청크 검사 `449-452`를 정확히 가리키지 않는다. 나머지 `correctness` 응답은 파일 출처 ID는 맞았지만 `taxonomy=concurrency`로 관점과 달라 `candidate_ungrounded` 처리됐다. 따라서 작은 모델 실행은 **불완전(종료 3)**하다. 접수된 두 건은 별개 결함 두 개가 아니라 **한 알려진 원인의 중복 주장**이다. 수정 후 양 모델에는 이 *다중 Range 무진전* 주장이 없었다. 수정 후의 단일 Range 조기 EOF 등 다른 가설의 진실 여부는 이 공개 수정으로 판단하지 않는다.

기존 프롬프트 호출에서는 네 판본 모두 접수 0건이었지만, 이번 결과의 접수 증가를 **프롬프트 변경의 인과 효과나 진단 정확도 향상**으로 확정할 수 없다. 새로운 비결정적 모델 호출이며 수정 전 작은 모델에는 실패 관점과 잘못된 위치가 남았다. `findings`는 출처 줄·형식 검사에 **임시 접수된 정적 가설**이지 실행 확인·독립 정답 판정이 아니다. 전체 토큰은 124,332개(수정 전 작은/강한 4.13배, 수정 후 4.23배); 요청 시간 합은 전체 진단 시간이나 실제 청구 USD가 아니다. 공개 한 결함의 개발 대조를 최종 80사례의 Precision/Recall·우월성·A+ 성과에 합산하지 않는다.

## v27 실제 증거 재검증과 추가 역할 비교 승인 준비

**수행한 것:** Python 3.14에서 `verify_git_source`·`graph`·`retrieve`로 두 Starlette 판본의 원본 출처를 재검증했다. 각 84개 Python 파일·파싱 오류 0개·문맥 23,654/23,934바이트가 기존 기록과 일치했다. 네 결과 파일의 위 SHA-256, 제공자 응답 12개와 감사/참조 SHA, 호출별 입력·출력·캐시 사용량 합 **124,332토큰**도 모두 일치했다. 후보는 그대로 source_only/deferred이며 독립 진실 판정이나 새 모델 호출이 아니다. 기존 네 영수증은 `verify_approval`에서 모두 `approval already consumed`로 거절됐다.

**재검증 불가 증적:** 과거 Prefect의 `run_approved.py --verify` 명령 두 개를 실제 실행했으나 `/tmp/wreckfish-prefect-before-oracle-manifest.json`, `/tmp/wreckfish-prefect-fixed-oracle-manifest.json` 부재로 모두 종료 2였다. 기록된 `/tmp` 경로와 현재 저장소의 `execution.json`·oracle/holdout 자료 이름을 확인했지만 해당 재검증 원자료는 찾지 못했다. 과거 실행 관측을 취소하는 것은 아니나 현재 제출 가능한 재현 원자료로 셀 수 없다. 새 실행은 별도 승인과 원본 복구가 필요하다.

**보존:** 남아 있는 Starlette 결과·정규화 응답·설정·소진 영수증 총 28개 파일을 `/home/wy/.local/share/wreckfish/a-plus-verification/starlette-boundary-v27/prior-archive/`에 바이트 그대로 복사하고 SHA-256 일치를 확인했다. 소유자 디렉터리 0700·파일 0600이다. `prior-results-verification.json`에 재검증 관측, `comparison-plan.json`에 원경로·보존경로·파일 SHA를 기록했다. 이 보존본은 이전 결과의 복사본이지 새로운 실행이나 독립 제3자 증명이 아니다. Git 저장소·출처 묶음은 기존 `/tmp` 경로이므로 향후 소실 시 고정 upstream SHA와 앞선 절차로 복구·검증해야 한다.

### 새 실행 범위

- 사전에 고정했던 Starlette 수정 전/후 두 판본과 `FileResponse._handle_multiple_ranges`만 사용한다. 다른 결과가 잘 나오는 사례를 사후 선택하지 않는다.
- 각 판본에서 `gpt-6-sol` 단일, `gpt-6-luna` 다섯 관점, `gpt-6-luna --boundary-review` 여섯 역할의 세 군을 새 영수증으로 비교한다. 각 실행의 선언된 총 한도는 80,000토큰·1,200초이며 도구/실행 node는 없다. 여섯 설정 모두 현행 `manifest_hash`·`validate_model_plan`을 통과했다.
- 강한 단일 군도 같은 그래프 심볼 문맥을 사용하므로 최종 full raw-source 기준선은 아니다. 추가 역할용 지시문은 기존 다섯 역할에도 추가되고 `다섯 관점+일반 재검토` 대조는 아직 구현되지 않았다. 따라서 이 여섯 실행이 성공해도 새 역할만의 인과 효과·최종 F 우월성·A+을 입증하지 않는다.
- 평가할 관측은 고유 원인·원인 연산 위치·성립 조건, 중복, 미판정 진실, 실패/보류, 모든 호출의 캐시 포함 토큰과 요청 시간이다. 실제 USD·전체 결함 Recall·저장소 전체 무결함을 산출하지 않는다.

새 파일은 모두 `/home/wy/.local/share/wreckfish/a-plus-verification/starlette-boundary-v27/` 아래에 있다.

| 판본·군 | 설정 파일 | 소유자가 확인할 RunManifest SHA-256 |
| --- | --- | --- |
| 수정 전·강한 단일 | `before-strong.json` | `ab5e4f6c2cfb685e9eca0ffa08a3a96c735ad3a07a42a962da5417fc1af7e0ca` |
| 수정 전·작은 다섯 | `before-five.json` | `b07ca02ec890df785c0ebad23c4fcc186b4d415d3611927987b62f59ffa7b668` |
| 수정 전·작은 여섯 | `before-boundary.json` | `dbfd3db8d417c2030a7b407e7fef7975ba4c321d039508911be8972036ee584f` |
| 수정 후·강한 단일 | `after-strong.json` | `89e362175eaa06514947c69d4b4249f6bc83fdb53a3cac220995bfbb8eab62ab` |
| 수정 후·작은 다섯 | `after-five.json` | `219e3323908eaaa409af241e792eff7f38f11581e17a1b7854293eda8e011382` |
| 수정 후·작은 여섯 | `after-boundary.json` | `8ac8a1ccf99337115d7061a3f942bf56e514b5910708a310418c5fc64f43b435` |

기존 네 군과 해시가 같은 설정도 **새 영수증**이 필요하다. 소진 영수증의 복사본은 재사용하지 않는다. 실제 여섯 `diagnose_approved.py` 명령은 모두 영수증 부재로 전송 전 종료 2였고, 응답 디렉터리·승인 영수증 생성은 0개였다(`approval-preflight.json`). 승인용 셸 파일은 `bash -n` 검사를 통과했으며 승인 명령을 자동 실행하거나 해시를 대리 입력하지 않았다.

소유자가 본인 대화형 단말에서 다음을 실행하면 여섯 설정이 차례로 표시된다. Git·모델·한도를 확인하고 **매번 표시된 해시를 직접 입력**해야 한다. 이 스크립트는 승인만 하며 모델·대상 코드를 실행하지 않는다.

```sh
bash /home/wy/.local/share/wreckfish/a-plus-verification/starlette-boundary-v27/approve-comparison.sh
```

승인 후 실행할 정확한 argv는 `comparison-plan.json`의 각 `diagnose_argv`에 있다. 응답 경로는 해당 폴더의 `{판본}-{군}-responses`로 고정했고 아직 생성하지 않았다. **이번 검증의 새 모델 호출·대상 실행은 0건**이며 승인 뒤에도 공개 개발 결과를 최종 독립 80사례 지표로 합산하지 않는다.

### v27 소유자 승인 후 실제 여섯 비교 실행

소유자가 여섯 설정을 승인한 뒤 `verify_approval`로 모두 정확한 해시·미사용 상태임을 확인했다. 두 Git 출처 각 84개를 재검증하고 루프백 모델 서버의 `gpt-6-sol`·`gpt-6-luna` 제공을 확인한 다음, 사전에 기록한 Python 3.14 `diagnose_argv`를 순서대로 **각 한 번** 실행했다. 재시도·프롬프트/접수 규칙 변경·대상 실행은 하지 않았다. 완료 후 모델 서버를 종료했다.

| 판본·군 | 완료/실패·종료 코드 | 원문 후보/임시 접수/미검증 | 총 토큰 | CLI 프로세스 벽시계(초) |
| --- | --- | --- | --- | --- |
| 수정 전·강한 단일 | 1/0·0 | 4/4/0 | 12,453 | 61.713 |
| 수정 전·작은 다섯 | 4/1·3 | 3/2/1 | 50,629 | 51.272 |
| 수정 전·작은 여섯 | 6/0·0 | 1/1/0 | 59,914 | 35.549 |
| 수정 후·강한 단일 | 1/0·0 | 4/4/0 | 12,181 | 54.301 |
| 수정 후·작은 다섯 | 4/1·3 | 2/1/1 | 50,706 | 53.802 |
| 수정 후·작은 여섯 | 6/0·0 | 0/0/0 | 59,546 | 11.682 |

실제 호출 24회 중 22회 완료·2회 실패, 제공자 보고 총 **245,429토큰**, 원문 후보 14개·임시 접수 12개·미검증 2개다. 시간은 실제 CLI 프로세스 측정이며 이전 표의 요청 시간 합과 다르다. 각 한 번의 순차 실행·캐시/제공자 변동·출력량 차이가 있어 속도 개선 인과로 해석하지 않는다. 후보 수는 고유 결함 수나 독립 참양성 수가 아니다.

**추가 역할의 직접 관측:** `assumptions`는 수정 전/후 모두 `candidates=[]`를 반환했고 두 호출 합계 19,742토큰을 사용했다. 여섯 역할 전체 토큰은 다섯 관점보다 수정 전 **18.34%**, 수정 후 **17.43%** 많았다. 여섯 역할에서 나온 수정 전 EOF 후보 1개는 새 역할이 아니라 기존 `correctness`에서 나왔다. 이번 사례에서는 새 역할의 추가 발견을 관측하지 못했으며 토큰 절감도 없었다.

**알려진 다중 Range EOF와 위치 대조:**

- 강한 단일 수정 전 후보는 실제 읽기·진행식·전송 루프 `449-452`를 지목하고 파일 축소→빈 읽기→진행 없음이라는 조건을 설명했다.
- 작은 다섯의 수정 전 접수 두 후보는 같은 EOF 원인의 중복이다. correctness의 `448-451`은 seek와 실제 read/갱신식을 포함하지만, concurrency의 `426-460`은 메서드 전체다. 이전 실측의 두 잘못된 위치와 동일하게 취급하지 않는다.
- 작은 여섯의 수정 전 correctness 후보는 원인을 설명했으나 **444줄 `else:`**만 지목해 실제 읽기/갱신식의 위치는 틀렸다.
- 수정 후 세 군 모두 해당 *다중 Range 무진전*을 주장하지 않았다. 강한 군의 다른 가설 4개와 다섯 관점의 background 가설은 별도 진실 미판정이다. 여섯 역할의 후보 0개를 수정판 전체가 안전하다는 증거로 보지 않는다.
- 다섯 관점은 양쪽 모두 `tests` 호출이 실패했다. 수정 전은 taxonomy=concurrency, 수정 후는 taxonomy=correctness로 호출 관점과 달라 `candidate_ungrounded` 처리됐다. 여섯 역할의 완료율 개선만으로 발견 정확도 개선을 주장하지 않는다.

**원자료:** 위 소유자 전용 지속 경로에 `{판본}-{군}-result.json`, `-stderr.log`, `-responses/`, `execution-ledger.json`, `comparison-result.json`을 저장했다. 24개 응답의 실제 파일 SHA와 결과 참조/감사 SHA, 모든 호출의 사용량 합, 여섯 `.used` 해시, 디렉터리 0700·파일 0600을 확인했다. `comparison-plan.json`과 `approval-preflight.json`은 승인 전 기록으로 보존하며 실제 실행 여부는 새 ledger/result로 판독한다.

| 결과 파일 | SHA-256 |
| --- | --- |
| `before-strong-result.json` | `66c7ea386bf5d87e6a45944a98560cfd66946af05165b5db32f341815143960b` |
| `before-five-result.json` | `23aeb6b3512f6255d74ab5c835fb144f5101d72b79cb95f527047220bf8835f1` |
| `before-boundary-result.json` | `33c84452eff6f2990497ba36676e9158951c1b82a540e447d92a0d383bdf435b` |
| `after-strong-result.json` | `fc35ac6be90c8b1df475c24542274c4447be110705434c868d603deba6bc6844` |
| `after-five-result.json` | `8e5474f408d331d8c745162d94065877fe4cb3444212bf5be26213fdd44b07a7` |
| `after-boundary-result.json` | `600a0a80ee093394f9f1ee91e6a757304169e5e7e2bdb973275864027f699b89` |

**결정:** 여섯 역할을 기본 경로나 최종 평가로 승격하지 않는다. 이번 공개 한 사례에서 추가 역할의 직접 기여는 없었으며, 전역 프롬프트 차이·비결정적 호출·일반 재검토 대조 부재 때문에 다른 차이의 원인도 분리할 수 없다. 현재 공개 개발 결과는 A+·독립 정밀도/발견률·최종 F 우월성 증거가 아니다. 이후 개선은 위치를 코드 연산과 연결하는 경로와 역할/분류 불일치에서 유효 원인이 탈락하는 문제를 먼저 검토하되, 이번 결과는 소급 변경하지 않는다.

## v28 P0 승인·후보 접수 수정과 오프라인 재생

**범위:** [계획 030의 P0](../../.wayfinder/ai-a-plus-code-health/tickets/030.md)만 구현했다. 정상 후보 동반 탈락·역할/분류 혼동·충돌 묶음의 전체 실행 중단을 고쳤다. P1 관점별 지침, P2 정적 근거, P3 품질/비용 실험은 수행하지 않았다. 새 외부 모델 호출·공개 대상 실행은 모두 **0건**이다.

### 승인·봉인 계약

- `run-manifest-v2.analysis`는 모드·역할 순서·범위·심볼·기준 SHA·실제 전달 문맥의 SHA를 승인에 묶는다. `--prepare-manifest`는 전송 없이 이 설정만 생성한다. v1이나 선택 불일치는 영수증 소진 전에 거절한다.
- 모든 역할은 기존 다섯 taxonomy를 사용할 수 있다. 호출 완료와 행 접수를 분리하고, 원래 후보 행·순번·SHA·거절 이유·finding ID를 감사에 남긴다. 정확한 동일 원인 키에서 trigger·분류·다음 행동·파일이 충돌하면 해당 묶음 전체만 미검증으로 남긴다. 의미 중복이나 인과 위치를 새로 증명하는 기능은 아니다.
- 최종 다섯 객체는 `evidence-contract-v2`, 출처 묶음은 v1이다. 미검증 행은 봉인된 보고서에서 표시하고, `candidate_counts`와 `analysis_status`로 부분 실패를 구분한다. single/plain 최종 봉인·실행 제한과 `source_only/deferred`는 유지한다.
- 응답 저장 옵션은 필수다. 정규화 응답 파일과 내장 행 감사를 별도로 대조하며, 둘 다 실제 제공자 호출이나 결함 진실의 독립 증명은 아니다.
- 기본 five/plain 프롬프트는 그대로다. boundary에서 기존 역할의 분류 일치 지시만 제거해 해시는 `025093f590a4f759a2205a25f1b0202860866d311ae647d69edb49f18fba37bd`로 변경됐다. 과거 승인은 새 실행에 사용할 수 없다.

### 변경 전 검증기와 실제 로컬 확인

자료 경로: `/home/wy/.local/share/wreckfish/a-plus-verification/p0-contract-v28/`(소유자 전용).

- **수정 전 재현:** 정상 행+잘못된 줄을 넣으면 접수 0·미검증 2·호출 실패였다. structure 역할의 유효한 performance 후보도 접수 0·미검증 1·호출 실패였다(`before.jsonl`).
- **과거 검증기 보존:** 제품 수정 전에 `src/`·`tests/` 77파일을 `legacy-verifier-v27.tar.gz`로 보존했다. SHA-256 `c2419de272e7ab2cc8a20747de79aabadaa22419812ecf0c5fe1925ec697c138`, 파일별 해시는 `legacy-verifier-v27.json`에 있다. 추출본으로 과거 manifest 6개·감사 4개·응답 24개의 연결을 오프라인 검증했다(`legacy-verification.json`). 원래 여섯 실행에는 최종 봉인물이 없었으므로 과거 최종 보고서 재검증까지 수행한 것은 아니다.
- **실제 CLI:** 합성 Git·시험용 승인·합성 응답으로 `diagnose_approved.py` subprocess의 준비→승인 소비→응답 저장→후보 분리→봉인 경로를 실행했다. 여섯 원문 행 중 정상 2개 유지, null/잘못된 줄 2개와 동일 키 충돌 2개는 미검증. 호출은 다섯 개 모두 완료, 종료 **3**, 보고서는 **불완전·접수 2·미검증 4·확증 0**이었다. 실제 보고서 `cli-aujs14pw/report.md`와 `smoke-summary.json`에 보존했다.
- 실제 응답 파일 1바이트 변경·파일 부재는 재검증이 거절했다. 선택 범위 변경과 v1 설정은 실제 CLI **종료 2·시험 영수증 미소진**이었다.
- **회귀:** `uv run --no-project --python 3.14 python -m unittest discover -s tests`에서 201개 실행, **200개 통과·1개 건너뜀**. 시험용 응답과 회귀 결과를 실모델 성과로 집계하지 않는다.

### 기존 24개 응답의 새 접수 규칙 재생

원본 `starlette-boundary-v27/` 결과·응답·소진 영수증은 변경하지 않았다. Git 두 판본과 응답 해시를 대조한 뒤 저장 응답만 주입해 별도 `*-replay.json` 및 `replay-summary.json`을 만들었다.

| 판본·군 | 당시 임시 접수 | 새 규칙 오프라인 접수 | 미검증 |
| --- | ---: | ---: | ---: |
| 수정 전·강한 단일 | 4 | 4 | 0 |
| 수정 전·작은 다섯 | 2 | 3 | 0 |
| 수정 전·작은 여섯 | 1 | 1 | 0 |
| 수정 후·강한 단일 | 4 | 4 | 0 |
| 수정 후·작은 다섯 | 1 | 2 | 0 |
| 수정 후·작은 여섯 | 0 | 0 | 0 |

역할/분류 불일치로 탈락한 두 행이 보존됐다. **새 탐지·참양성 증가가 아니다.** 후보 중복·위치의 인과 적합성·참/거짓은 여전히 별도 판정 대상이다. 재생의 245,429토큰은 과거 사용량이지 신규 비용이 아니다. boundary 재생은 새 프롬프트에 대한 응답도 아니다. 독립 80사례·전체 F 비교·USD 청구·A+ 차단 조건은 유지한다.

## v29 P1 역할별 지침과 승인 경계 구현

**범위:** [029의 P1 구현](../../.wayfinder/ai-a-plus-code-health/tickets/029.md#v29-p1-역할별-지침구현과-로컬-검증). `run-manifest-v3`의 `model.prompt_sha256`은 모드별로 순서 있는 `{role, instructions}`의 canonical UTF-8 JSON SHA-256이다. 공통 계약과 역할별 검토 절차를 실제 모델 요청에 넣는다. five와 boundary의 처음 다섯 지시문은 같다. plain의 이전 일반 지시문은 유지하되 v3 모드 해시를 적용한다. single은 짧은 일반 검토다. 모델 미사용 설정은 `analysis:null`이다. 최종 형식은 `evidence-contract-v2`, 출처는 v1 그대로다.

**수정 전 검증기 보존:** 제품 수정 **전** `src/`·`tests/` 80파일과 파일별 해시·Python 3.14.3을 소유자 전용 `/home/wy/.local/share/wreckfish/a-plus-verification/p1-instructions-v29/`에 보존했다. `legacy-verifier-v28.tar.gz` SHA-256은 `dfddcefd179d17e0cb0a7718792167e71d544e78841a45369c0f8183019bc435`다. 추출한 **v28 검증기**로 기존 합성 P0 최종 묶음의 접수 2·미검증 4 및 정규화 응답 5개를 오프라인 재검증했다(`legacy-verification.json`). 기존 실모델 최종 봉인물이 있다는 주장은 아니다. 보존본은 신규 전송이나 승인에 쓰지 않는다.

**실제 CLI·격리 응답 확인:** `uv run --no-project --python 3.14 python -m unittest discover -s tests`에서 **206개 실행, 205개 통과·1개 건너뜀**. 저장소 밖 시험용 Git, 일회용 승인과 합성 제공자 응답으로 `diagnose_approved.py`의 실제 subprocess를 실행했다(`cli2/summary.json`). five 5회·boundary 6회 요청, 둘 다 접수 1·미검증 1·확증 0·종료 3. 응답 파일과 최종 묶음을 각각 재검증하고 불완전/미검증 보고서 표시도 렌더링해 확인했다. 사용량·문맥 상태가 같은 첫 다섯 실제 요청 payload는 **완전히 동일**했다. single/plain은 `--prepare-manifest`와 모드별 해시를 확인했으며 실제 모델 경로 실행까지 확인한 것은 아니다. v2·다른 모드·변조 해시의 CLI 호출은 종료 2·영수증 미소진이었다.

**악성 데이터 시험:** 별도 고정 Git 소스 주석과 전달할 로그에 명령형 문자열을 넣고 실제 지침·입력을 로컬에서 캡처했다. 합성 모델의 정상 행 1건은 유지하고 위조 출처 ID 1건은 `candidate_source_invalid`로 보류됐다(모델 요청 모사 5회, 소스 실행·외부 요청 0건). **실제 LLM이 주입을 무시한다는 증거는 아니다.**

**변경 한계:** 후속 호출 예약은 직전 제공자 입력(캐시 포함)에 이전/현재 역할과 지시문 바이트·256 여유를 더한다. 전체 입력 재예약은 하지 않는다. 회귀에서는 예산 경계·부분 실패와 접수 보존을 확인했지만 제공자의 실제 토큰 계산·USD 청구는 측정하지 않았다. **신규 실모델 호출·대상 코드 실행은 0건**이며, 합성 후보 1건을 실제 결함·정밀도 향상으로 해석하지 않는다. 이전 v27/v28 응답은 바뀐 지침의 품질 증거가 아니다. P2 정적 근거·P3 품질/비용 비교와 A+ 차단 조건은 남는다.

## v30 P2 정적 점검·P3 개발 비교 경로의 실제 범위

**구현:** [030의 P2/P3 계획](../../.wayfinder/ai-a-plus-code-health/tickets/030.md#p2--코드에서-검토-단위를-추출하고-근거를-연결)을 개발 선택 경로로 적용했다. 기존 `--review-units raw`와 다섯 관점/과거 원자료는 바꾸지 않았다. `outline`은 Git 원본 AST의 분기·반복·종료·호출 위치 목록, `cards`는 전달한 원문 안에서만 반복 조건·단순 변수 변경·구문상 중첩 방어/종료를 묶는다. 파일 경로·source SHA·심볼·구문 종류·UTF-8 바이트 위치에 결속된 ID, 추출/전달/누락 ID와 예산상 전체 목록 밖 개수를 문맥·역할 감사·최종 봉인에 남긴다. 두 방식은 서로 다른 문맥 SHA와 일회용 승인 설정을 요구하며 단일 기준선은 기존 원문만 받는다. `generic` 여섯째 역할은 기본 다섯 지침을 유지하되 별도 모드/해시/승인으로 한 번만 실행한다. AST 관계·후보와 점검 항목의 줄 일치는 인과·도달성·실제 점검 coverage가 아니다.

**고정 공개 소스의 대상 코드 무실행 확인:** Starlette 수정 전 commit `ba504c555fbd6d02ea584c295667185a10453700`의 기존 출처 묶음(선택 `FileResponse._handle_multiple_ranges`)을 Git blob으로 재검증했다. `prepare_analysis(...,review="outline")`는 점검 항목 ID 24개 중 23개 전달·1개 누락, 예산 밖 미열거 240개였다. `review="cards"`는 ID 22개 전달·0개 누락, 미열거 248개였다. 같은 438·447·450줄의 호출은 열 위치가 다른 각각의 AST 항목이다. 카드 예산 때문에 한 목록의 수가 작아도 탐지 누락이나 비용 절감의 실측이 아니다. 시험용 Git과 모사한 제공자 응답으로 outline/cards 다섯 역할의 승인이 일치할 때만 처리, 잘못된 모드의 영수증 미소진, 응답·후보 감사 봉인/변조 거절, 일반 여섯째 역할의 후보 비전달과 별도 승인/봉인을 확인했다. 실제 모델 송신·Starlette 대상 실행은 **이번 확인에 없음**.

**실행 전 동결한 개발 기준선 계획:** 소유자 전용 `/tmp/wreckfish-development-v30-prep-20260927/baseline-plan.json`에 같은 수정 전 Starlette Git 함수의 작은 단일 `gpt-6-luna`, 작은 다섯 `gpt-6-luna`, 강한 단일 `gpt-6-sol`을 각각 세 회차로 섞어 저장했다. 계획 SHA-256은 `b02519f6343c26231c5984414168f2f78a0f1b13251fa948b38412707fb50592`, 총 계획 호출 21회·회차별 토큰 상한 80,000/벽시계 1,200초다. 알려진 EOF 원인은 상류 수정 PR·회귀 검사 **문서**에 연결했으며 우리 쪽에서 검사 실행·독립 정답 봉인은 하지 않았다. 생성 명령은 신규 승인이나 모델 호출을 수행하지 않는다. 실제 `compare_development.py` CLI에 결과 0건을 입력하니 `small_single`/`strong_single` 호출 누락 각 3건, `small_five` 15건, USD 모두 N/A, 미실행·정적 자료 미제출 차단을 보고했다. 같은 Git 문맥의 기존 좁은 `N_static`을 결정적으로 재생하니 가설 0건(정답 0건을 뜻하지 않음), 상태 `git_static_replay_verified`였다. 계획·해시·로컬 경로는 독립 시각·승인·판정 원본 증명이 아니다.

위 `b02519f6…`은 CLI가 출력한 **canonical JSON 본문 해시**다. 줄바꿈을 포함한 계획 파일의 별도 바이트 SHA-256은 `3b368841d1fb706bccb037cafcb98831c8b7e4bc8dd732c8a8615671c960a6cf`다. 부모/파일 권한은 각각 0700/0600이었다.

**첫 실행 승인 준비(발급 전):** 계획 순서 첫 항목은 수정 전 Starlette `repeat-1/strong_single`이다. 위 Git 출처 묶음과 현행 `single` 지침, 모델 `gpt-6-sol`, 80,000토큰/1,200초, 대상 실행 노드·도구 없음으로 `/tmp/wreckfish-development-v30-prep-20260927/first-strong-manifest.json`을 준비했다. 재계산한 분석 문맥·모델·상한은 계획과 같고 RunManifest 해시는 `5db743441ab41763ebdc2a1efaf7f87f736d3648224d08f904324f3a571879d4`다. **영수증 미발급·모델 호출 0·대상 실행 0**. 소유자의 직접 입력 전에는 이 설정으로 전송하지 않는다. 나머지 회차도 각각 새 영수증과 응답 경로가 필요하다.

**검증/잔여 관문:** Python 3.14 전체 회귀 259건 실행(258건 통과·1건 건너뜀). 실모델의 `P0→P1`, `P1→P2a`, `P2a→P2b`와 실제 여섯 역할 세 군의 3회×동예산 짝실험, 독립 판정·부정 사례·위치 적합성·실제 USD 영수증은 미수집이다. P0의 보존 v28 검증기는 현행 개발 비교기에 통합하지 않았으며 보존 자료만으로 새 P0 실험을 승인할 수 없다. 현 프록시의 출력 상한 비강제와 이 호스트의 자원 제한 미강제, 최종 80사례/운영·제안서 수용 조건은 그대로다. 신규 소스 전송/대상 실행에는 계획과 별개로 각 실행 정확한 RunManifest를 소유자가 대화형 단말에서 직접 승인해야 한다. AST·합성 응답·계획 호출 수는 참양성 증가나 A+ 실측이 아니다.

**판정 누락과 보류의 분리 확인:** 저장된 응답의 접수 후보가 세 회차에 각각 1건이고 독립 판정 행이 없는 개발용 입력에서, 수정 전에는 미확인 3건인데도 완료 회차 3건으로 표시됐다. 현재는 `missing_judgments=3`, `explicit_unknown_judgments=0`, 불완전 회차 3건 및 `missing_judgment` 차단을 보고한다. 합성 입력의 세 행에 명시적 `U`를 넣은 경우와 여섯째 호출의 오프라인 재조합도 두 상태를 분리한다. 이는 합성 응답에 대한 집계 정확성 검증이며 독립 판정을 새로 수행한 결과가 아니다. Python 3.14 전체 회귀 261건 실행(260건 통과·1건 건너뜀).

**동결 기준선 승인 설정 확대(아직 전송 전):** 위 첫 항목 외에 나머지 8개도 계획 `order`의 회차·군 이름으로 `/tmp/wreckfish-development-v30-prep-20260927/{repeat-N}-{arm}-manifest.json`에 준비했다. 예외는 첫 항목의 `first-strong-manifest.json`이다. 모든 9개에서 CLI가 인증 Git 문맥·지침·모드로 생성한 해시와 계획의 모델·역할·심볼·80,000토큰/1,200초·실행 노드 없음이 일치하고 파일 권한은 0600이다. 강한 단일 3회는 같은 설정 해시 `5db743441ab41763ebdc2a1efaf7f87f736d3648224d08f904324f3a571879d4`, 작은 단일 3회는 `089f5b0a6d23da8afd37507668088019fdb46513ecd89e0b411e5483ded8d447`, 작은 다섯 3회는 `9fd523a91240413bfb1f613e5bc6c14cbb06ccdfe1a8232fdc36054a1f872517`이다. 설정 본문이 같은 회차끼리 해시가 같더라도 **회차마다 별도의 대화형 소유자 승인 영수증·응답 경로**가 필요하다. 현재 발급 영수증 0개·모델 호출 0건·대상 실행 0건이며 승인 시점/실제 호출 순서는 이 준비만으로 인증되지 않는다.

작은 다섯 군 첫 회차를 실제 `diagnose_approved.py`에 승인 영수증 없이 전달한 결과 `unavailable or invalid approval receipt`로 종료 2였고 응답 디렉터리·영수증이 생성되지 않았다. 이는 승인 차단 확인일 뿐 실모델 성능 검증이 아니다.

## v30 기준선 첫 회차: 소유자 승인 후 실제 강한 모델 1회

소유자가 첫 `repeat-1/strong_single` RunManifest 해시 `5db743441ab41763ebdc2a1efaf7f87f736d3648224d08f904324f3a571879d4`를 직접 승인했다. 승인 영수증을 고정 Git `ba504c555fbd6d02ea584c295667185a10453700`·선택 심볼 `FileResponse._handle_multiple_ranges`·역할 지침·80,000토큰/1,200초 상한과 대조하고, 미사용 상태를 확인한 뒤 `python3.14 -B src/diagnose_approved.py SOURCE_BUNDLE MANIFEST RECEIPT --symbol FileResponse._handle_multiple_ranges --single-baseline --response-output RESPONSE_DIR`을 실행했다. 영수증은 소진됐으며 승인 범위에 실행 노드·도구가 없어 대상 코드를 실행하지 않았다.

실제 `gpt-6-sol` **1호출 완료**(모델 호출 45.044초, 11,736토큰). 원문 후보 3건은 모두 접수됐고 미검증 행은 0건이다. 이는 **접수된 가설 3건**이지 참양성 3건이 아니다. CLI 출력은 `/tmp/wreckfish-development-v30-prep-20260927/repeat-1-strong_single-result.json`에 0600으로 보존했고 SHA-256은 `3c0b4626e83a2c986b7d3c11a6375a94b8f249eb49591e4bb60fe1c13832c7f0`이다. 별도 0600 정규화 응답 SHA-256은 `90eb2927863ff71b4a7924047d64b009fa12cde5b204db2324c6dd5d3c9eaf17`; 저장 바이트·사용량·후보 인덱스와 감사 내용을 `verify_responses`로 다시 대조했다. 제공자 wire 원본·USD 청구·독립 결함 판정 증거는 아니다. 호출 뒤 루프백 모델 서버를 종료했다.

계획 순서 첫 실행만 담은 임시 개발 비교 입력/보고를 같은 비공개 디렉터리에 보존했다(`first-partial-comparison-input.json` SHA `a2b56ded9810f31d1105f327e6832cad757019d20339be52ee111514fb2d64d2`, `first-partial-comparison-report.json` SHA `6d68f7f932fd439b282879a54e4cdb49c73e6374d48f4e2d870ca96783609101`). 실제 비교 CLI는 계획한 모델 호출 21개 중 첫 1개 완료, 나머지 20개 미실행으로 보존했다. 강한 군의 접수 3·독립 판정 누락 3으로 `TP=0, FP=0, U=3`, 불완전 회차 3이다. `N_static`은 이 심볼/파일에서 지원되는 두 좁은 반례형에 한해 Git 재생 검증 완료·가설 0건이다. USD는 미확보로 `null`; 누락·미판정으로 승격 차단이다. 다음 계획 순서 `repeat-2/strong_single`을 실행하려면 내용 해시가 같더라도 **별도의 새 소유자 영수증**이 필요하다. 이 한 개발 회차를 A+ 효과·강한 모델 우월성·정확도로 해석하지 않는다.

## v30 기준선 두 번째 회차: 강한 모델 재실행

동결 순서의 `repeat-2/strong_single`에 대해 소유자가 동일한 설정 해시 `5db743441ab41763ebdc2a1efaf7f87f736d3648224d08f904324f3a571879d4`를 **새 영수증**으로 직접 승인했다. 승인 전 Git SHA `ba504c555fbd6d02ea584c295667185a10453700`·심볼·지침/문맥·모델·80,000토큰/1,200초 한도·미사용 여부를 대조했다. `gpt-6-sol` 두 번째 1호출은 정상 완료(모델 41.683초, CLI 42.633초, 11,818토큰). 후보 4건 모두 접수, 미검증 0건. 영수증 소진을 확인했고 대상 코드 실행은 없으며 호출 뒤 루프백 모델 서버를 종료했다.

원자료는 소유자 전용 `/tmp/wreckfish-development-v30-prep-20260927/repeat-2-strong_single-result.json`(SHA-256 `f12c788b47d2ca50116b3c3f4f017febb5851b41896120cf06c62c9097e2dda2`) 및 0600 정규화 응답(SHA-256 `c7a62c61d231ca20f14c7fde73703d3b3aacdf2da71c449b59e6f95df52103f4`)으로 보존했다. 응답 바이트·사용량·후보 행을 `verify_responses`로 재검증했다. 앞의 회차를 유지한 부분 비교 입력 `two-partial-comparison-input.json`의 SHA-256은 `1f3008ea86c135b2bb7ae126f0c9eddf6b506ce82587c7845e5c8ecfab6d08df`, 보고 `two-partial-comparison-report.json`은 `078eb50b699e463a3a2453663e220a2e77adfcf385dc0af438b814a8b0dda6c3`이다.

두 강한 단일 회차 합계는 **2호출·23,554토큰·접수 가설 7건**이다. 독립 판정 7건 모두 누락으로 `TP=0, FP=0, U=7`; 21호출 중 완료 2·미실행 19이고 `N_static`은 좁은 두 반례형에서만 재생 검증·가설 0건이다. 가설 간 중복·참거짓은 아직 판정하지 않았고 제공자 USD 영수증도 없다. 다음 동결 순서 `repeat-2/small_single`에는 `089f5b0a6d23da8afd37507668088019fdb46513ecd89e0b411e5483ded8d447`에 대한 소유자의 별도 영수증이 필요하다. 접수 건수만으로 개선이나 모델 우월성을 주장하지 않는다.

## v30 기준선 세 번째 회차: 작은 모델 단일 검토

소유자가 계획 순서 `repeat-2/small_single`의 모델 전용 v3 설정 해시 `089f5b0a6d23da8afd37507668088019fdb46513ecd89e0b411e5483ded8d447`를 새 영수증으로 직접 승인했다. 송신 전 동일 Git `ba504c555fbd6d02ea584c295667185a10453700`·심볼·문맥 SHA·단일 역할 지침·80,000토큰/1,200초·미사용 영수증을 대조했다. `gpt-6-luna` 단일 1호출은 정상 완료(모델 21.414초, CLI 22.297초, 10,420토큰), 후보 1건 접수·미검증 0건이다. 승인 영수증 소진을 확인했고 대상 실행은 없으며 모델 서버를 종료했다.

0600 비공개 원자료 `/tmp/wreckfish-development-v30-prep-20260927/repeat-2-small_single-result.json`의 SHA-256은 `e3fc3f31a105ea97145126c2f13fcac95655d3ce0170d36c9d1105156250f935`, 별도 정규화 응답 SHA-256은 `334cd73b0638b24bdad423da192d7ba2aa65fcc94c69d31ff655d12c4a51c4ea`이다. `verify_responses`로 응답·사용량·행 인덱스를 재확인했다. 앞의 두 회차를 그대로 보존한 부분 비교 입력 `three-partial-comparison-input.json` SHA-256 `5d8bafc2d49133da0052eb459036b2c4e7d9a7597610c86237868be12b307f6f`, 보고 `three-partial-comparison-report.json` SHA-256 `c526c58691ac8ce689fd8ecfd0b7cbecd20496f3cb8002dae9f21af85cb6dea1`이다.

계획 전체 21호출 중 **3완료·18미실행**, 누적 사용량 **33,974토큰**(강한 단일 2회 23,554·작은 단일 1회 10,420). 접수된 원문은 강한 군 7건, 작은 단일 1건이지만 독립 원인 판정 8건 모두 누락이고 `TP/FP`는 판정되지 않았다. 좁은 `N_static`은 여전히 두 반례형의 가설 0건이다. 후속 `repeat-1/small_five`를 실행하려면 별도의 해시 `9fd523a91240413bfb1f613e5bc6c14cbb06ccdfe1a8232fdc36054a1f872517`에 대한 소유자 영수증이 필요하다. 원문 후보 수만으로 어느 모델의 정확도나 비용 우월성도 주장할 수 없다.
