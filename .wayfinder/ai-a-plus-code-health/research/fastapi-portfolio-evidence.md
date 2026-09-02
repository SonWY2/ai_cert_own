# Python 3.14 + FastAPI·asyncio 코드 건강검진용 공개 포트폴리오 근거

> 조사 기준일: 2026-08-29  
> 목적: `.wayfinder/ai-a-plus-code-health/tickets/024.md`의 **구현·검증 가능한 평가 명세**.  
> 조사 범위: 공식 GitHub API/파일, 고정 tag/commit, `pyproject.toml`, 공식 test·benchmark·load-test 문서만 읽었다. 대상 저장소의 코드·테스트·benchmark·profiler는 실행하지 않았고, formatter/linter도 실행하지 않았다.  
> 판정어: **FACT** = 링크한 원문이 직접 확인되는 사실, **DESIGN** = 이 프로젝트의 검증 설계, **UNKNOWN** = 이번 조사로 확인하지 못한 것.

## 1. 조사 규칙과 선택 원칙

1. 후보는 이름/별 개수가 아니라 `immutable revision + license + Python 3.14 package metadata + FastAPI/ASGI/asyncio evidence + 재현 가능한 workload`로 심사한다.
2. 공개 저장소는 파일·benchmark가 사전학습에 포함됐을 가능성이 매우 높다. 따라서 공개 후보는 **pilot의 재현성·회귀·계측 보정**에만 쓰고, 진단 일반화·최종 승자 판정의 단독 근거로 쓰지 않는다. 이는 외부 수치가 프로젝트 성과라는 뜻이 아니다.
3. BugsInPy/SWE-bench와 같은 patch-resolution 자료의 정답 패치를 이 시스템의 “전체 결함 gold”로 세지 않는다. 이 포트폴리오는 결함의 존재를 seeded mutation/수동 adjudication으로 별도 표시한다.
4. FastAPI·Starlette 자체는 제품 대상과 프레임워크가 순환된다. 이들은 **라우팅/ASGI/API 계측 baseline**으로만 사용하며 제품 건강검진 점수에 섞지 않는다.
5. Python 3.14 실행 가능성을 metadata로 확인하지 못한 후보는 `UNKNOWN`으로 남긴다. `requires-python` 범위/3.14 classifier는 “실행 보장”이 아니라 **설치 후보 조건**이다. 실제 fixture 재생은 별도 격리 검증이 필요하다.

## 2. 후보 검증 표

약어: `C` correctness, `P` performance, `K` concurrency/cancellation, `A` API/OpenAPI/HTTP contract, `X` cross-file/topology. `●` 원문에 직접 workload/test 근거, `△` 설계로 보완해야 함, `—` 이 목적에는 부적합.

| 공개 후보 (고정 revision) | License / Python 3.14 근거 | FastAPI·ASGI·asyncio 근거 | 규모 지표 (이 snapshot의 tracked `.py`) | Strata `C/P/K/A/X` | 재현 workload와 정상/known-positive 제작 | 공개 오염·채택 판정 |
|---|---|---|---:|---|---|---|
| **Langflow v1.11.5**  [`ab52f7f8b911bb42712cefdfe9af3ed02db560a6`](https://github.com/langflow-ai/langflow/tree/ab52f7f8b911bb42712cefdfe9af3ed02db560a6) | MIT. `pyproject.toml`: `requires-python = ">=3.10,<3.15"`, `license = "MIT"`. 3.14를 포함하지만 별도 classifier는 확인하지 못함. | `src/backend/base/langflow/main.py`가 `FastAPI`, `asynccontextmanager`, `CORSMiddleware`를 import하고 `async def lifespan(app: FastAPI)`를 정의. `pyproject.toml`의 `asyncio_mode = "auto"`. | 3,594 `.py` / 693,991 lines (docs·tests 포함); `src/backend` 1,494 / 362,941 lines. 측정은 `git ls-files` 기준이며 제품 LOC 주장 아님. | **●/●/●/●/●** | `src/backend/tests/unit/test_chat_endpoint.py`에 `@pytest.mark.benchmark` async build-flow/chat 계약이 있다. `src/backend/tests/locust/README.md`는 setup→headless Locust, 사용자 유형, `ramp100`/`stepramp`, p50/p95/p99·RPS·failure를 명시한다. 정상군은 고정 commit의 no-LLM test fixture/로컬 dependency로 고정한다. known-positive는 router 등록 누락, async 경로의 `time.sleep`, 취소/timeout 삼키기, schema↔service 반환 불일치, DB query fan-out을 **overlay mutation**으로 하나씩 주입하고 mutation manifest에 파일/line/원인/기대 invariant를 기록한다. | 공개 대형 앱이라 오염 **높음**. **Pilot 채택 1순위**(실제 다중 모듈·API·async·load); 외부 모델 API 없이 no-LLM/결정적 flow를 기본으로 한다. |
| **Prefect 3.8.4** [`57ee2c2c10f662fee32807c126a117adce32dd28`](https://github.com/PrefectHQ/prefect/tree/57ee2c2c10f662fee32807c126a117adce32dd28) | Apache-2.0. `pyproject.toml`: `requires-python = ">=3.10,<3.15"`, Python 3.14 classifier. | `src/prefect/server/api/server.py`는 FastAPI REST app이며 asyncio/AnyIO 경로를 사용한다. 공식 `benches/bench_flows.py`는 sync와 `async def anoop_function` flow를 모두 다룬다. | 1,901 `.py` / 693,547 lines; `src/prefect` 820 / 180,984 lines. `git ls-files` snapshot 지표. | **●/●/●/●/●** | `benches/bench_flows.py`의 async subflow benchmark는 `num_flows = 5, 10, 20`, `anyio.run`, concurrent `tg.start_soon`을 사용한다. 정상군은 noop flow + SQLite/isolated API fixture. known-positive는 task cancellation 누락, bounded concurrency 제거, API route status/schema 변경, cross-module state mutation, sync blocking call 삽입으로 만든다. **주의:** benchmark 첫 docstring은 “higher number of tasks; blocked by engine deadlocks in CI”라고 명시하므로 이를 성능 gold/통과 기준으로 쓰지 않는다. | 공개 오염 **높음**. **Pilot 채택**(workflow concurrency와 API); deadlock caveat 때문에 별도 K 결과와 P 결과를 보고한다. |
| **FastAPI Users v15.0.5** [`9ef8cd82619856772ac06a178b114eb47c79586c`](https://github.com/fastapi-users/fastapi-users/tree/9ef8cd82619856772ac06a178b114eb47c79586c) | MIT. `pyproject.toml`: Python 3.14 classifier, `requires-python = ">=3.10"`. | `fastapi_users/router/register.py`의 `get_register_router`가 `APIRouter`를 만들고 `async` user-manager 호출/HTTP status를 사용한다. OpenAPI test와 examples가 router/manager/schema의 다중 파일 계약을 보여준다. | 88 `.py` / 9,188 lines; package `fastapi_users` 25 / 1,848 lines. 작지만 auth/API cross-file 기준으로 유용. | **●/△/●/●/●** | 공식 `tests/test_openapi.py`, router tests, examples를 정상 workload로 고정하고 in-process DB/HTTP client로 재생한다. P는 본래 benchmark가 없어 `△`: 동일 API를 1/10/100 concurrent 요청으로 계측하는 별도 harness가 필요하다. known-positive는 dependency override/auth scope/status code/schema와 manager↔router signature를 mutation한다. | 공개 코드 오염 **높음**, 규모/성능 대표성 **낮음**. **Pilot 채택**(auth/API correctness control); 최종 제품 성능 결론에는 사용하지 않는다. |
| **full-stack-fastapi-template** [`486f054cc8d1aead59ec96cc0a16933d06c10e0d`](https://github.com/fastapi/full-stack-fastapi-template/tree/486f054cc8d1aead59ec96cc0a16933d06c10e0d) | MIT (`LICENSE`). `backend/pyproject.toml`: `requires-python = ">=3.14,<4.0"`, Ruff `target-version = "py314"`, `fastapi[standard]`, `sqlmodel`, `psycopg`. | `backend/app/main.py`의 FastAPI app/router와 `backend/app/api/routes/items.py`의 CRUD router를 확인. package metadata에 FastAPI entrypoint가 있다. | 43 `.py` / 2,907 lines. 템플릿이므로 큰 실사용 제품의 규모 지표로 해석 금지. | **●/△/△/●/●** | README의 Docker/Compose + backend CRUD/health 경로를 정상 baseline으로 고정하되 외부 DB는 test container/SQLite 등으로 격리한다. P/K는 별도 `httpx.AsyncClient` harness에서 deterministic barrier와 payload size를 사용한다. known-positive는 route include 누락, sync DB call in async route, transaction rollback 누락, response model mismatch를 overlay로 주입한다. | 공개 템플릿 오염 **높음**, 현실 규모 **낮음**. **Pilot의 Python 3.14 정상 대조군으로 채택**; final holdout 아님. |
| **Starlette 1.6.0** [`4f250d6b814587e20c5365f0a5f0c4d42bcb929f`](https://github.com/Kludex/starlette/tree/4f250d6b814587e20c5365f0a5f0c4d42bcb929f) | BSD-3-Clause. `pyproject.toml`: `requires-python = ">=3.10"`, Python 3.14 classifier. | ASGI framework source (`starlette/applications.py`, `starlette/routing.py`)와 async endpoint/ASGI runner를 확인. | 71 `.py` / 19,275 lines. | **●/●/●/●/●** | 공식 `benchmarks/README.md`와 `benchmarks/routing_benchmark.py`: 30 resource groups × 4 routes = 120-route table, small variant, hit/miss/405; 각 요청에 fresh ASGI scope를 만든다. 정상군은 benchmark 기대 status. known-positive는 route order/method match, middleware cancellation, body-limit, response serialization을 mutation한다. | 공개 framework 오염 **매우 높음**, 제품 순환 **높음**. **계측 baseline만 채택**, 제품 점수·final holdout에서 제외. |
| **FastAPI 0.141.1** [`95f8322ee1dcda7ceace7b1c4f6c9915b36d748f`](https://github.com/fastapi/fastapi/tree/95f8322ee1dcda7ceace7b1c4f6c9915b36d748f) | MIT. `pyproject.toml`: `requires-python = ">=3.10"`, Python 3.14 classifier. | framework 자체. `tests/benchmarks/test_general_performance.py`가 `FastAPI`, `Depends`, `TestClient`와 sync/async route를 사용한다. | 1,136 `.py` / 112,887 lines (tests/docs 포함); package 25 / 5,130 lines. | **●/●/△/●/●** | 공식 benchmark는 `--codspeed`가 없으면 module-level skip하고, 300-item payload, dependency chain, GET/POST/async validation을 benchmark한다. 해당 source가 정의한 workload를 router/serialization baseline으로만 재생한다. known-positive는 dependency resolution, response model/status, route registration을 mutation한다. | 공개 framework 오염 **매우 높음**, 대상 순환 **명시적**. **Framework calibration only**; final holdout/제품 순위 금지. |
| **vLLM 0.28.0** [`2cf0a6915ce544dc493a0990f2ea38d81601128a`](https://github.com/vllm-project/vllm/tree/2cf0a6915ce544dc493a0990f2ea38d81601128a) | Apache-2.0. `pyproject.toml`: `requires-python = ">=3.10,<3.15"`, Python 3.14 classifier. | `vllm/entrypoints/openai/api_server.py`가 FastAPI app, ASGI server, async request/stream 경로를 제공한다. | 4,231 `.py` / 1,417,398 lines; `vllm` package 2,216 / 831,687 lines. GPU/native/model artifact와 Python 코드 규모를 분리 기록해야 한다. | **△/●/●/●/●** | 공식 `benchmarks/README.md`는 offline inference, online serving, dataset utilities를 분리하고 `benchmark_serving.py`/OpenAI API test paths를 안내한다. 정상군은 고정 model artifact·tokenizer·GPU/driver image와 exact request seed를 함께 고정한다. known-positive는 batching/scheduler bound, cancellation, streaming chunk order, OpenAI schema, cross-module engine↔API contract mutation으로 만든다. | 공개·모델/벤치 오염 **높음**; hardware/model dependency와 출력 비결정성이 큼. **Pilot의 조건부 serving/performance track**이지 일반 FastAPI correctness corpus나 final holdout이 아니다. |
| **Open WebUI** [`d3e8bf3405e848cfba377814d0aa7ba7290e414d`](https://github.com/open-webui/open-webui/tree/d3e8bf3405e848cfba377814d0aa7ba7290e414d) | **부적합**: `pyproject.toml`이 `requires-python = ">= 3.11, < 3.13.0a1"`; 3.14 불가. `LICENSE`는 “Open WebUI License”의 branding/end-user 제한이 있는 custom license이며 GitHub API도 `NOASSERTION`. | `backend/open_webui/main.py`에 `FastAPI`, `AsyncSession`, `async def`, 많은 API router가 확인된다. | 이 표에서는 size를 측정했지만 3.14 gate 때문에 채택 판정에 쓰지 않는다. | **●/●/●/●/●** (3.14 gate 실패) | `/health`, async DB ping, chat/model routes와 tests는 workload 후보이나 3.14 검증 corpus로 사용하지 않는다. | **최종/파일럿 제외**: Python 3.14 incompatibility와 license redistribution 조건. 공개 오염도 높음. |

### Package metadata가 실제 실행을 보장하지 않는 이유

`requires-python`는 resolver가 허용하는 범위일 뿐, 이 조사에서 Python 3.14 interpreter로 dependency install/test를 수행하지 않았다. 특히 C-extension/GPU/DB/OS 의존성은 별도 evidence가 필요하다. 따라서 표의 “3.14 근거”는 다음 세 단계로 해석한다.

- **Green candidate**: metadata가 3.14를 명시/포함하고, 소스·tests·workload 경로가 확인됨. (Langflow, Prefect, FastAPI Users, template, Starlette, FastAPI)
- **Conditional**: metadata는 통과하지만 native/hardware/runtime prerequisite가 크다. (vLLM)
- **Red/UNKNOWN**: metadata가 3.14를 배제하거나 조건을 확인하지 못했다. (Open WebUI는 Red; 별도 후보에서 metadata 미확인 시 UNKNOWN 유지)

## 3. pilot 고정 포트폴리오

다음 네 개를 **versioned pilot corpus**로 고정한다.

1. **Langflow v1.11.5** — 실제 대형 다중 모듈 FastAPI/async/API/load 사례.
2. **Prefect 3.8.4** — workflow engine의 async/concurrency/cancellation과 FastAPI server.
3. **FastAPI Users v15.0.5** — 작은 auth/API 정상 대조군, cross-file contract가 명료함.
4. **full-stack-fastapi-template pinned commit** — Python 3.14 전용 설치·FastAPI CRUD 정상 대조군.

Starlette와 FastAPI는 같은 pilot 실행에서 **framework/measurement calibration lane**으로 함께 고정할 수 있으나, 위 네 제품의 A+/건강 점수에 합산하지 않는다. vLLM은 GPU image·model artifact가 제공되는 별도 **conditional performance lane**으로만 고정한다.

각 고정 corpus manifest에는 다음을 저장한다.

```yaml
repo: langflow-ai/langflow
revision: ab52f7f8b911bb42712cefdfe9af3ed02db560a6
license: MIT
python: "3.14.x"
source_digest: sha256:<checkout-tree-digest>
dependency_lock_digest: sha256:<lockfile-digest>
workload:
  - static_snapshot
  - repository_tests_selected_by_manifest
  - deterministic_http_or_inprocess_harness
  - optional_load_profile
external_model_api: false
public_pretraining_contamination: high
```

`source_digest`, lock digest, OS/container image, environment variables, DB schema seed, request seed, and workload version are 필수다. Git SHA만으로 generated files, submodules, untracked fixtures, model/tokenizer artifact가 고정되었다고 가정하지 않는다.

## 4. 구현 가능한 평가 계약

### 4.1 층화와 출력

각 실행은 하나의 총점만 내지 않고 아래 key로 결과를 낸다.

```text
(public_real | synthetic_mutation | anonymous_real)
× (correctness | performance | concurrency | API | cross_file)
× (static_only | approved_dynamic)
× (repo, revision, workload, environment)
```

각 finding은 `finding_id`, 파일/심볼/line range, detector version, evidence kind, severity hypothesis, reproducibility command, expected invariant, observed result, confidence, reviewer decision을 가진다. “미검출”은 결함 없음이 아니라 **관측 가능한 oracle 범위 안에서 미검출**이다.

### 4.2 정상 대조군

- 고정 revision을 untouched checkout으로 보존한다.
- repository-native tests/workloads의 expected HTTP status, response schema, OpenAPI path, task completion, cancellation outcome을 baseline trace로 기록한다.
- dynamic 실행은 network/model provider를 끄고 local DB/in-process ASGI/fixture service를 쓴다. 시간·random·UUID·scheduler interleaving은 injectable seed/clock/barrier로 고정한다.
- 정상 대조군의 pass는 “코드가 건강하다”가 아니라 해당 workload contract를 충족했다는 뜻이다.

### 4.3 Known-positive mutation

각 mutation은 원본 checkout과 별도 overlay에서만 생성한다. 원본 공개 revision은 절대 수정하지 않는다.

| 계층 | 최소 mutation family | 관측 가능한 oracle |
|---|---|---|
| Correctness | status code/exception mapping/계산 결과/transaction rollback을 한 줄 변경 | expected response/body/DB invariant 위반 |
| API | router include 누락, parameter/schema/response model 변경, auth dependency 제거 | OpenAPI diff, 2xx↔4xx contract, auth boundary |
| Concurrency | lock 제거, shared mutable state, cancellation swallow, timeout 미전파, unbounded `gather` | barrier에서 lost update/deadlock/leak/order violation |
| Performance | async route 안 blocking I/O, N+1 query, payload serialization 폭증, queue bound 제거 | fixed workload p50/p95/p99, CPU/DB call count, bounded resource invariant |
| Cross-file | router↔service↔schema signature mismatch, settings/env 이름 drift, migration↔model 불일치 | import/route discovery, type/schema trace, end-to-end request |

Mutation gold에는 “결함을 만들었다”는 fact만 넣고, Critical/High는 영향·노출·재현 증거를 가진 reviewer가 adjudicate한다. 같은 defect family의 공개 code line을 train/evaluation 모두에 재사용하지 않도록 family-level split을 적용한다.

### 4.4 성능·동시성 보고

- 절대 threshold는 repository README의 “production grade” 문구를 프로젝트 성과로 복사하지 않는다. 예를 들어 Langflow Locust 문서의 p95/실패율 grade는 그 load script의 운영 편의 기준일 뿐 이 시스템의 universal health gate가 아니다.
- 성능은 동일 machine/image/DB seed/payload/request count에서 baseline 대비 paired delta와 raw distribution을 보고한다.
- 동시성은 request count만으로 판단하지 않고 bounded concurrency, cancellation, timeout, lock ownership, cleanup, ordering, lost update를 별도 invariant로 판정한다.
- Prefect benchmark의 CI deadlock caveat와 vLLM의 GPU/model artifact 의존성은 결과의 limitation 필드에 의무 기록한다.

## 5. 후보별 재현 workload 명세 (향후 실행; 이번 조사에서는 미실행)

| Candidate | 최소 workload | 외부 모델 API 정책 |
|---|---|---|
| Langflow | no-LLM build/chat async test trace; `/health`; deterministic flow run; Locust `NormalUser`/`SustainedLoadUser`를 5→10→20 user 단계로 짧게 재생하고 100-user profile은 별도 stress로 둔다. | 기본 false. provider를 켜야 하는 공개-flow 실험은 model/version/prompt/timeout/cost를 manifest에 고정하고 pilot 결과와 분리한다. |
| Prefect | noop sync/async flow 5/10/20; sequential vs concurrent subflows; API route smoke; cancellation/timeout barrier. | false. 외부 LLM은 workload에 필요하지 않다. |
| FastAPI Users | register/login/reset/OpenAPI routes with isolated DB; concurrent same-user and invalid-token cases; 1/10/100 request levels. | false. |
| full-stack template | `/health`, auth, items CRUD, validation/404/transaction rollback; `httpx.AsyncClient` with deterministic DB fixture. | false. |
| Starlette | official 120-route hit/miss/405 ASGI runner; response/body-limit/stream path; separate middleware cancellation run. | false; framework calibration only. |
| FastAPI | official general-performance benchmark source with `--codspeed` gate; 300-item JSON, dependency chain, sync/async validation; no score mixing with products. | false; framework calibration only. |
| vLLM | pinned model/tokenizer + OpenAI-compatible `/v1` request/stream/batch; fixed GPU/driver/container and warm/cold phase separated. | no hosted model API; local artifact only. If artifact unavailable, mark workload unavailable, not failure. |

모든 dynamic run은 “대상 코드 실행 금지”인 본 조사와 구별되는 후속 validation 단계다. 이 문서 작성 중에는 어떤 candidate test/server/benchmark/profiler도 실행하지 않았다.

## 6. final holdout에 쓰면 안 되는 후보

- **FastAPI와 Starlette**: framework 자체라 제품 대상과 순환되고 공개 학습/benchmark 오염도 매우 높다. calibration lane 외 금지.
- **full-stack-fastapi-template**: 정상 Python 3.14 대조군으로 유용하지만 템플릿이며 규모·운영결함 대표성이 없다. final real holdout 금지.
- **vLLM**: GPU/driver/model/tokenizer와 native extension 결과가 지배하므로 일반 FastAPI/async 건강의 final correctness gold 금지. 조건부 performance lane만 허용.
- **Open WebUI**: pinned metadata가 `<3.13.0a1`이라 Python 3.14 요구를 충족하지 않고, custom license/branding 제한도 있다. 채택·재배포·holdout 금지.
- **모든 공개 후보의 원래 issue/PR/patch labels**: 발견된 결함의 존재를 보조하는 provenance일 수 있으나 저장소 전체의 complete gold나 severity oracle로 사용 금지.

최종 holdout은 공개 후보가 아닌 **요건을 통과한 익명 실제 사례 + holdout 전용 Python 3.14 fixture mutation family**로 구성한다.

## 7. Python 3.14 전용 합성 FastAPI fixture가 채워야 할 공백

공개 후보 조합만으로는 다음이 완전하지 않다.

1. **3.14-only runtime gate**: `requires-python >=3.14`, lockfile, ASGI server, deterministic local DB를 실제로 설치/재생하고 Python 3.13과 결과를 섞지 않는다.
2. **작지만 완전한 topology**: `app/main.py → api/routers → services → repositories → models/schemas → settings`, migration, generated OpenAPI, worker/CLI entrypoint를 다중 파일로 제공한다.
3. **실제 async 경계**: lifespan startup/shutdown, `asyncio.TaskGroup`, timeout/cancellation, `asyncio.to_thread` sync boundary, async DB transaction, streaming/SSE 또는 WebSocket 중 적어도 하나를 deterministic barrier로 덮는다.
4. **재현 가능한 concurrency oracle**: N개 요청의 lost-update/duplicate side effect, cancellation cleanup, semaphore/queue bound, lock ordering을 expected trace로 저장한다. sleep timing에 의존하지 말고 Event/Barrier를 사용한다.
5. **API contract oracle**: route include, dependency override, auth scope, request/response model, status code, OpenAPI operation id, backward-compatible change를 snapshot/diff한다.
6. **성능 결함의 통제**: sync I/O-in-async, N+1, unbounded fan-out, oversized serialization, queue starvation을 각각 한 mutation으로 만들고 fixed payload/DB seed/call count와 paired benchmark를 제공한다.
7. **교차 파일·생성물**: schema↔service, settings↔env, migration↔model, router↔dependency, test↔fixture 관계를 graph로 명시한다. generated OpenAPI/migration을 gold에서 숨기지 않는다.
8. **오염 방지**: 새 commit/비공개 mutation family를 final split 전에 고정하고, public source names/문구를 그대로 복사한 fixture 대신 behavior-equivalent 자체 domain을 쓴다.
9. **외부 서비스 0 기본값**: model API, SaaS DB, network callback 없이 실행한다. 필요한 provider는 local fake와 contract trace로 대체한다.

## 8. 익명 실제 사례 admission 조건

익명 사례는 아래 체크리스트를 모두 통과해야 final holdout에 들어간다.

- **법률/보안**: 소유자 서면 허가, license/사용범위 확인, secret/token/PII/고객명/도메인/내부 URL 제거, 재식별 위험 검토. 원본은 평가 workspace 밖에 보관하고 report에는 digest와 비식별 metadata만 남긴다.
- **불변성/출처**: source tree digest 또는 file manifest, 기준 commit/빌드, Python 3.14.x, OS/container, dependency lock/hash, DB schema/seed, 실행 command를 보존한다. force-push 가능한 branch명만으로 admission하지 않는다.
- **실행성**: clean isolated replay가 외부 network/model API와 secrets 없이 성공하거나, 불가한 dependency가 있으면 local stub/recorded contract로 대체된다. 재생 불가 사례는 final score에서 제외하고 limitation으로 남긴다.
- **오라클 품질**: 관측된 bug report/trace/impact, 재현 workload, expected behavior, affected version, severity rationale가 있어야 한다. patch가 존재해도 patch text 자체를 gold로 세지 않고, 최소 2인의 독립 reviewer가 evidence를 adjudicate한다.
- **층화/누수 방지**: correctness/performance/concurrency/API/cross-file 및 static/dynamic 태그, defect family, temporal metadata를 기록한다. 같은 service·mutation family·문구가 train/pilot/final에 겹치지 않게 family/temporal split한다.
- **모델 정책**: 익명 final holdout에서는 외부 모델 API를 금지한다. 공개 pilot에서 허용된 API 사용 결과도 final holdout의 입력·oracle·prompt로 재사용하지 않는다.
- **삭제/철회**: contributor가 철회를 요청하면 case id를 tombstone하고 이미 공개된 aggregate와 raw artifact의 보존 범위를 기록한다.

## 9. 결론

**FACT**로 고정 가능한 공개 근거는 Langflow·Prefect·FastAPI Users·full-stack template의 네 pilot 후보와 FastAPI/Starlette calibration, 조건부 vLLM lane이다. **DESIGN**으로는 네 제품 후보의 untouched 정상군, overlay mutation known-positive, 다섯 strata, paired workload, contamination-aware split을 하나의 manifest 계약으로 구현한다. Python 3.14 전용 fixture와 익명 실제 사례 admission이 없으면 공개 corpus 결과만으로 “대규모 코드 건강”이나 A+ 우월성을 주장하지 않는다.

### 조사에 사용한 원문 링크와 핵심 excerpt

- [Langflow v1.11.5 `pyproject.toml`](https://raw.githubusercontent.com/langflow-ai/langflow/ab52f7f8b911bb42712cefdfe9af3ed02db560a6/pyproject.toml): `requires-python = ">=3.10,<3.15"`, `license = "MIT"`.
- [Langflow FastAPI app](https://raw.githubusercontent.com/langflow-ai/langflow/ab52f7f8b911bb42712cefdfe9af3ed02db560a6/src/backend/base/langflow/main.py): `from fastapi import FastAPI`; `@asynccontextmanager`; `async def lifespan(app: FastAPI)`.
- [Langflow async benchmark test](https://raw.githubusercontent.com/langflow-ai/langflow/ab52f7f8b911bb42712cefdfe9af3ed02db560a6/src/backend/tests/unit/test_chat_endpoint.py): `@pytest.mark.benchmark`와 `async def test_build_flow(...)`.
- [Langflow official Locust README](https://raw.githubusercontent.com/langflow-ai/langflow/ab52f7f8b911bb42712cefdfe9af3ed02db560a6/src/backend/tests/locust/README.md): setup/load-test 2단계, `--users 20 --duration 120`, `ramp100`/`stepramp`, p50/p95/p99/RPS/failure/error tracking.
- [Prefect 3.8.4 `pyproject.toml`](https://raw.githubusercontent.com/PrefectHQ/prefect/57ee2c2c10f662fee32807c126a117adce32dd28/pyproject.toml): `requires-python = ">=3.10,<3.15"`, Apache-2.0, Python 3.14 classifier.
- [Prefect flow benchmark](https://raw.githubusercontent.com/PrefectHQ/prefect/57ee2c2c10f662fee32807c126a117adce32dd28/benches/bench_flows.py): `async def anoop_function`, `num_flows` 5/10/20, `anyio.run`, `tg.start_soon`; top TODO가 CI deadlock을 명시.
- [FastAPI Users v15.0.5 `pyproject.toml`](https://raw.githubusercontent.com/fastapi-users/fastapi-users/9ef8cd82619856772ac06a178b114eb47c79586c/pyproject.toml): `requires-python = ">=3.10"`, Python 3.14 classifier.
- [FastAPI Users register router](https://raw.githubusercontent.com/fastapi-users/fastapi-users/9ef8cd82619856772ac06a178b114eb47c79586c/fastapi_users/router/register.py): `APIRouter`, `async` manager call, `HTTP_201_CREATED`.
- [full-stack template backend metadata](https://raw.githubusercontent.com/fastapi/full-stack-fastapi-template/486f054cc8d1aead59ec96cc0a16933d06c10e0d/backend/pyproject.toml): `requires-python = ">=3.14,<4.0"`, `target-version = "py314"`, FastAPI/SQLModel dependencies, `app.main:app`.
- [Starlette 1.6.0 metadata](https://raw.githubusercontent.com/Kludex/starlette/4f250d6b814587e20c5365f0a5f0c4d42bcb929f/pyproject.toml): BSD-3-Clause, `requires-python = ">=3.10"`, Python 3.14 classifier.
- [Starlette routing benchmark README](https://raw.githubusercontent.com/Kludex/starlette/4f250d6b814587e20c5365f0a5f0c4d42bcb929f/benchmarks/README.md) 및 [source](https://raw.githubusercontent.com/Kludex/starlette/4f250d6b814587e20c5365f0a5f0c4d42bcb929f/benchmarks/routing_benchmark.py): 120-route synthetic table, hit/miss/405, fresh ASGI scope.
- [FastAPI 0.141.1 metadata](https://raw.githubusercontent.com/fastapi/fastapi/95f8322ee1dcda7ceace7b1c4f6c9915b36d748f/pyproject.toml): MIT, `requires-python = ">=3.10"`, Python 3.14 classifier.
- [FastAPI general performance benchmark](https://raw.githubusercontent.com/fastapi/fastapi/95f8322ee1dcda7ce7b1c4f6c9915b36d748f/tests/benchmarks/test_general_performance.py): `--codspeed` gate, 300-item payload, dependencies, sync/async GET/POST tests.
- [vLLM 0.28.0 metadata](https://raw.githubusercontent.com/vllm-project/vllm/2cf0a6915ce544dc493a0990f2ea38d81601128a/pyproject.toml): Apache-2.0, `requires-python = ">=3.10,<3.15"`, Python 3.14 classifier.
- [vLLM OpenAI FastAPI server](https://raw.githubusercontent.com/vllm-project/vllm/2cf0a6915ce544dc493a0990f2ea38d81601128a/vllm/entrypoints/openai/api_server.py) 및 [benchmark README](https://raw.githubusercontent.com/vllm-project/vllm/2cf0a6915ce544dc493a0990f2ea38d81601128a/benchmarks/README.md): FastAPI OpenAI-compatible serving와 offline/online benchmark 분리.
- [Open WebUI metadata](https://raw.githubusercontent.com/open-webui/open-webui/d3e8bf3405e848cfba377814d0aa7ba7290e414d/pyproject.toml): `requires-python = ">= 3.11, < 3.13.0a1"`, FastAPI/uvicorn/SQLAlchemy asyncio dependencies.
- [Open WebUI license](https://raw.githubusercontent.com/open-webui/open-webui/d3e8bf3405e848cfba377814d0aa7ba7290e414d/LICENSE): “Open WebUI License”, branding and end-user restrictions.
- [Open WebUI FastAPI app](https://raw.githubusercontent.com/open-webui/open-webui/d3e8bf3405e848cfba377814d0aa7ba7290e414d/backend/open_webui/main.py): `app = FastAPI(...)`, many `include_router`, async chat/health/DB paths.
