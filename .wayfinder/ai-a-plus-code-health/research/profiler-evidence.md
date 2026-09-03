# Python 동적 검증 도구: 관찰력·왜곡·운영 제약 근거

- 조사 기준일: 2026-08-29
- 티켓: `tickets/006.md`
- 범위: cProfile, py-spy, Scalene, Memray, VizTracer, `sys.monitoring`, 표준 `asyncio` 관찰 기능
- 프로젝트 상태: 현재 저장소에는 설계 문서만 있고 실행 증적은 없다. 이 문서는 외부 근거를 정리한 연구 자산이며 어떤 도구도 채택하지 않는다.
- 실행 정책: 정적 읽기는 자동화할 수 있지만 코드 실행·테스트·profiler는 정책 승인 후에만 가능하다. 이번 조사에서는 대상 코드를 실행하지 않았다.

## 주장 분류와 판독 규칙

| 표기 | 의미 |
|---|---|
| **FACT** | 링크된 원문이 직접 규정한 API·동작·제약, 현재 패키지 메타데이터, 또는 논문에 실제로 보고된 실험 결과. 다른 버전·플랫폼·프로젝트 워크로드에 그대로 일반화하지 않는다. |
| **PROJECT-HYPOTHESIS** | 외부 근거에서 이 시스템에 적용해 볼 설계 또는 검증 가설. 승인된 격리 실험 전에는 사실이나 위험으로 승격하지 않는다. |
| **UNSUPPORTED** | vendor의 정성·정량 주장, 오래되었거나 충돌하는 비교, 또는 현재 프로젝트에 대한 실행 증적이 없어 의사결정 근거로 쓰면 안 되는 주장. |

`FACT`는 “우리 코드에서도 성립한다”는 뜻이 아니다. 특히 vendor 문서의 **기능 스위치가 존재한다**는 것은 FACT일 수 있지만, 그 기능이 **정확하고 저오버헤드다**라는 성과 주장은 독립 또는 프로젝트 대조 실험 없이는 UNSUPPORTED다.

## 요약

1. **FACT — 단일 도구가 모든 차원을 진단하지 않는다.** cProfile은 호출/반환/예외 기반 결정론적 시간·호출 통계, py-spy는 외부 프로세스의 표본 스택, Scalene은 문서상 CPU/네이티브/system/memory/async의 다차원 표본, Memray는 할당 추적, VizTracer는 함수 이벤트의 시간 순서, `sys.monitoring`은 저수준 실행 이벤트, 표준 asyncio 도구는 task/await 관계와 느린 callback을 각각 다룬다. [Python profiler 문서](https://docs.python.org/3/library/profile.html#what-is-deterministic-profiling), [py-spy README](https://github.com/benfred/py-spy), [Scalene README](https://github.com/plasma-umass/scalene#scalene-overview), [Memray 문서](https://bloomberg.github.io/memray/), [VizTracer 문서](https://viztracer.readthedocs.io/en/stable/), [`sys.monitoring`](https://docs.python.org/3/library/sys.monitoring.html), [asyncio 개발 문서](https://docs.python.org/3/library/asyncio-dev.html)
2. **FACT — profiler 결과는 benchmark가 아니다.** Python 공식 문서는 profiler가 Python 이벤트에는 비용을 더하지만 C 함수에는 같은 방식으로 비용을 더하지 않아 Python 대 C 비교를 왜곡할 수 있다고 경고하고, 별도 benchmark에는 `timeit`을 쓰라고 명시한다. [Python profiler 소개](https://docs.python.org/3/library/profile.html#introduction-to-the-profilers)
3. **FACT — cProfile은 공식적으로 대부분 사용자에게 권장되는 stdlib 후보지만 무조건적인 프로젝트 기본값 근거는 아니다.** 결정론적 관찰은 호출 수와 호출 관계를 제공하지만, 잦은 호출에는 이벤트 처리 오차가 누적될 수 있고 memory, syscall별 I/O, process 간 집계, asyncio await graph를 직접 제공하지 않는다. [cProfile 소개와 한계](https://docs.python.org/3/library/profile.html#limitations)
4. **FACT — 외부 attach는 ‘비침습’과 동의어가 아니다.** py-spy 기본 표본은 일관된 스택을 읽기 위해 대상을 잠깐 멈출 수 있고 `--nonblocking`은 중단을 피하는 대신 부분 프레임/표본 오류를 허용한다. Memray와 VizTracer attach는 대상에 코드를 주입하며 debugger 권한과 대상 환경 설치가 필요하다. [py-spy FAQ](https://github.com/benfred/py-spy#how-can-i-avoid-pausing-the-python-program), [Memray attach](https://bloomberg.github.io/memray/attach.html), [VizTracer attach](https://viztracer.readthedocs.io/en/stable/remote_attach.html)
5. **FACT — 표본과 계측은 서로 다른 왜곡을 만든다.** 표본은 짧거나 드문 경로를 놓칠 수 있고 상대 비중만 제공한다. 호출/line 계측은 이벤트 빈도에 비례해 비용과 function bias를 만들 수 있다. cProfile 공식 문서와 2023 OSDI 연구가 각각 이 원리를 설명한다. [결정론적 대 통계적 profiling](https://docs.python.org/3/library/profile.html#what-is-deterministic-profiling), [Scalene OSDI 논문 §6.2](https://www.usenix.org/system/files/osdi23-berger.pdf)
6. **FACT — 현재 호환성은 버전 고정 근거가 필요하다.** 2026-08-29 PyPI 기준 py-spy 0.4.2, Scalene 2.3.0, Memray 1.20.0, VizTracer 1.1.1이다. 지원 Python/OS 범위가 서로 다르며 native/free-threaded 지원은 wheel과 기능별로도 다르다. [py-spy PyPI JSON](https://pypi.org/pypi/py-spy/json), [Scalene PyPI JSON](https://pypi.org/pypi/scalene/json), [Memray PyPI JSON](https://pypi.org/pypi/memray/json), [VizTracer PyPI JSON](https://pypi.org/pypi/viztracer/json)
7. **PROJECT-HYPOTHESIS — 후속 결정 티켓은 ‘기본 도구’를 먼저 고르지 말고 질문→관찰 차원→왜곡 예산→권한→호환성 순으로 후보를 좁혀야 한다.** 각 후보는 동일 workload의 unprofiled control과 번갈아 반복하고, 핵심 경로 기여는 profiler 비중이 아니라 별도 counterfactual 대조의 결과 차이로 입증해야 한다. [pyperf 반복/워밍업 지침](https://pyperf.readthedocs.io/en/latest/run_benchmark.html), [NIST randomized block 설계](https://www.itl.nist.gov/div898/handbook/pri/section3/pri332.htm)
8. **UNSUPPORTED — 이 프로젝트에서 어떤 도구가 ‘낮은 오버헤드’, ‘정확’, ‘운영에 안전’, ‘기본값’이라는 결론.** 저장소 실행 증적이 없고, 공개 수치는 오래된 버전·제한된 Linux/CPython/benchmark 또는 vendor 연구에서 나온다. [OSDI 2023 실험 설정과 위협](https://www.usenix.org/system/files/osdi23-berger.pdf), [Memray 성능 실험 설정](https://bloomberg.github.io/memray/performance.html)

## 차원별 관찰 범위

기호: `직접`은 해당 차원의 전용 데이터, `간접`은 시간/스택에서 추론, `없음`은 도구 자체 산출물이 없음을 뜻한다.

| 도구 | CPU / 시간 | memory | I/O | event loop / async | thread / multiprocess | 근거 등급과 주의 |
|---|---|---|---|---|---|---|
| cProfile | **직접(함수 단위)**: 모든 call/return/exception과 `tottime`, `cumtime`, 호출 수. 현재 CPython 3.14 기본 timer는 monotonic performance counter다. | 없음 | **간접**: 함수 내부 경과시간에는 대기가 섞일 수 있지만 CPU 실행과 syscall/queue/remote latency를 분리하지 않는다. | 없음: coroutine의 Python 이벤트는 보일 수 있어도 task identity, suspended await duration, await graph는 전용 산출물이 아니다. | 한 interpreter의 이벤트; process별 파일은 `pstats.Stats.add()`로 합칠 수 있으나 프로세스 추적/정렬을 자동 제공하지 않는다. | **FACT**. [공식 문서](https://docs.python.org/3/library/profile.html), [CPython 3.14 `_lsprof.c`](https://github.com/python/cpython/blob/3.14/Modules/_lsprof.c). 3.14 구현은 `sys.monitoring`을 쓰므로 구버전 thread 동작을 현재에 추정하지 말고 버전별 canary가 필요하다. |
| py-spy | **직접(표본 스택)**: 모든 Python thread stack 표본, 선택적으로 GIL-holder와 일부 native stack. | 없음 | **간접/휴리스틱**: 기본은 idle thread를 제외하려 하고 `--idle`로 포함할 수 있으나 OS별 idle 판정 race와 Windows blocking-I/O 한계가 문서화돼 있다. | 전용 task/await graph 없음. 현재 실행 중인 thread stack은 보지만 suspended task 전체를 보여준다는 근거는 없다. | `--subprocesses`가 새 child에 attach해 PID/cmdline과 함께 포함. | **FACT**(문서화 범위), async 누락 정도는 **PROJECT-HYPOTHESIS**. [README/FAQ](https://github.com/benfred/py-spy). |
| Scalene | **직접(문서상 line/function)**: Python/native/system 분리, real/virtual time 선택, stitched stack 옵션. | **직접(문서상)**: line별 growth, Python/native 분리, copy volume, leak 후보. | **간접 분류**: README는 system time을 sleep/I/O로 표시한다. syscall·endpoint·bytes를 직접 식별하는 I/O tracer는 아니다. | 현재 README는 await line에 suspended wall time과 mean/peak concurrency를 귀속한다고 한다. | README는 thread와 `multiprocessing` 지원을 주장한다. | **FACT**는 기능 인터페이스 존재까지. 정확도·낮은 overhead·모든 framework 포괄은 **UNSUPPORTED**. [README](https://github.com/plasma-umass/scalene#scalene-overview), [OSDI 2023 논문](https://www.usenix.org/conference/osdi23/presentation/berger). |
| Memray | CPU profiler가 아님. allocation call stack은 기록하지만 CPU 비중을 뜻하지 않는다. | **직접**: 기본은 system allocator 요청; native 할당 포함. `--trace-python-allocators`로 pool 내부 객체 할당까지 늘릴 수 있다. peak/leak/temporary allocation reporter 제공. | 없음; capture file I/O 자체가 workload에 간섭할 수 있다. | 없음 | 모든 thread 할당; `--follow-fork`는 fork child마다 별도 capture 파일 생성. live와 follow-fork는 양립하지 않는다. | **FACT**. [run](https://bloomberg.github.io/memray/run.html), [API](https://bloomberg.github.io/memray/api.html). ‘모든 Python 객체’는 기본값에서 거짓이며 allocator 추적 옵션이 필요하다. |
| VizTracer | **직접(이벤트 timeline)**: Python/C 함수 entry/exit의 순서와 duration. sampling이 아니라 tracing이다. | 대상 memory profiler는 아님. 다만 trace buffer가 자체 RAM을 쓴다. | **간접**: 긴 함수/구간과 사용자 event 상관은 보이지만 syscall별 I/O metric은 없다. | `--log_async`가 task를 별도 lane처럼 시각화한다. | Python 3.12+ Python thread, multiprocessing/concurrent.futures, 제한된 subprocess patch; Windows `multiprocessing.Pool` 제약. | **FACT**. [concurrency](https://viztracer.readthedocs.io/en/stable/concurrency.html), [basic usage](https://viztracer.readthedocs.io/en/stable/basic_usage.html). 완전한 시간선은 circular buffer overflow와 filter 사용 시 성립하지 않는다. |
| `sys.monitoring` | profiler가 아니라 PY_START/RETURN/YIELD/RESUME, CALL, LINE, INSTRUCTION 등 callback 기반 event API. timer·집계·통계는 사용자가 구현해야 한다. | 없음 | 직접 없음 | coroutine yield/resume 이벤트는 있으나 task/await 관계와 wait 원인은 별도 결합이 필요하다. | event/callback은 thread가 아니라 interpreter 단위. process 간 수집은 별도. | **FACT**. CPython 3.12 추가, tool ID 0–5. [현재 문서](https://docs.python.org/3/library/sys.monitoring.html), [PEP 669](https://peps.python.org/pep-0669/). |
| stdlib asyncio debug/introspection | CPU profiler가 아님. slow callback과 느린 selector operation을 로그한다. | 없음 | selector 지연과 blocking이 loop를 막는 현상을 관찰하지만 endpoint/bytes별 I/O profiler는 아니다. | debug mode, `all_tasks()`, `Task.get_stack()`, Python 3.14 `capture_call_graph()`, 외부 `python -m asyncio ps/pstree PID`. | loop/thread별 task; process 통합 없음. | **FACT**. [개발 문서](https://docs.python.org/3/library/asyncio-dev.html), [task introspection](https://docs.python.org/3/library/asyncio-task.html#introspection), [3.14 call graph](https://docs.python.org/3/library/asyncio-graph.html), [3.14 CLI](https://docs.python.org/3/library/asyncio-tools.html). |

### 놓치는 것과 해석 한계

| ID | 상태 | 근거가 말하는 것 | 시스템이 금지해야 할 과잉 해석 |
|---|---|---|---|
| B-01 | **FACT** | cProfile의 `cumtime`은 callee 포함, `tottime`은 제외이며 profiler clock/event 비용은 호출이 많은 함수에 누적될 수 있다. [공식 문서](https://docs.python.org/3/library/profile.html#limitations) | `cumtime` 상위 = 그 함수 자체가 CPU를 소비했다, 작은 함수의 절대시간이 정밀하다, C가 Python보다 빠르다는 결론. |
| B-02 | **FACT** | py-spy는 표본 프로파일이고 기본 표본 일관성을 위해 대상 일시 정지가 있을 수 있다. `--nonblocking`은 partial frame/error trade-off다. [FAQ](https://github.com/benfred/py-spy#how-can-i-avoid-pausing-the-python-program) | 표본 0 = 실행되지 않음, 낮은 표본 = 위험 없음, nonblocking 결과 = 완전한 stack truth. |
| B-03 | **FACT** | py-spy idle 판정에는 activity-read와 stack-read 사이 race, OS/architecture 미구현, blocked-I/O 분류 한계가 있다. `--gil`은 GIL을 놓은 extension 실행을 누락한다. [FAQ](https://github.com/benfred/py-spy#how-do-you-detect-if-a-thread-is-idle-or-not), [GIL FAQ](https://github.com/benfred/py-spy#how-does-gil-detection-work) | idle 제외 profile을 I/O 대기의 증거로 사용, `--gil` 결과를 전체 CPU/native 소비로 사용. |
| B-04 | **PROJECT-HYPOTHESIS** | 짧고 드문 함수 또는 일정 주기와 동기화된 작업은 표본에서 누락/편향될 수 있다. 통계적 profiling은 상대적 indication이라는 공식 원리에서 파생된다. [공식 비교](https://docs.python.org/3/library/profile.html#what-is-deterministic-profiling) | 한 번의 표본 run으로 tail/rare-path 부재를 확정. 후보 검증에서는 sample rate와 시작 phase를 달리해 민감도를 확인해야 한다. |
| B-05 | **FACT** | 2023 Scalene 논문은 signal 지연과 stack을 이용해 Python/native/system을 추론하고, memory 변화가 threshold를 넘을 때 표본을 낸다. 당시 구현은 약 10MB 이상의 threshold와 signal/allocator interposition을 사용했다. [논문 §2–3](https://www.usenix.org/system/files/osdi23-berger.pdf) | 2026 버전의 모든 async/thread/native workload에서 같은 정확도·threshold가 성립한다고 추정. |
| B-06 | **FACT** | Memray 기본은 system allocator 요청을 추적하므로 Python pool이 재사용한 개별 객체는 보지 않는다. `--trace-python-allocators`는 훨씬 많은 데이터와 slowdown을 만든다. [run 문서](https://bloomberg.github.io/memray/run.html#python-allocator-tracking) | 기본 capture를 Python object count/lifetime의 완전한 census로 사용. |
| B-07 | **FACT** | Memray native symbolification은 capture와 같은 machine의 같은 binaries/libraries가 필요하며 debug info가 없으면 file/line이 불완전하다. macOS는 debug info 부재로 더 부정확할 수 있다. [native mode](https://bloomberg.github.io/memray/native_mode.html) | 다른 image/machine에서 생성한 native report의 주소를 정확한 source line으로 취급. |
| B-08 | **FACT** | VizTracer는 기본 1,000,000-entry circular buffer를 쓰며 오래된 entry를 버린다. 문서는 약 100B/entry RAM preallocation과 dump 시 10k entry당 약 1–2MB를 제시한다. [basic usage](https://viztracer.readthedocs.io/en/stable/basic_usage.html#circular-buffer-size) | 장시간 run의 trace 시작부터 끝까지가 모두 남았다고 가정. |
| B-09 | **FACT** | VizTracer include/exclude file 검사는 오히려 매 entry에서 경로를 검사해 성능에 큰 악영향을 줄 수 있고, C 함수 제외는 overhead/file size를 줄이지만 C event를 잃는다. [filter](https://viztracer.readthedocs.io/en/stable/filter.html) | filter를 무조건 비용 절감 수단으로 사용하거나 filter 전후 비중을 직접 비교. |
| B-10 | **FACT** | `sys.monitoring`의 LINE/INSTRUCTION callback은 callback 실행 비용이 지배할 수 있다. PEP 669의 memory 표는 3.12 설계 당시 code object당 LINE/INSTRUCTION 활성화 비용을 큰 폭으로 예상했다. [PEP 669 performance](https://peps.python.org/pep-0669/#performance) | “low impact” 명칭만으로 line/instruction 전역 계측이 저비용이라고 판정. PEP 수치는 현재 구현 benchmark가 아니라 설계 당시 예상이다. |
| B-11 | **FACT** | asyncio debug mode는 잘못된 thread의 non-threadsafe API에 예외를 내고 slow selector/callback을 로그한다. 기본 slow callback 경계는 100ms이며 조정 가능하다. [asyncio debug](https://docs.python.org/3/library/asyncio-dev.html#debug-mode) | debug on/off를 동일 의미의 workload로 간주하거나 100ms 미만 callback을 정상으로 판정. |
| B-12 | **FACT** | `Task.get_stack()`은 suspended coroutine에서 한 stack frame만 반환한다. Python 3.14 call-graph API는 cooperative Future/Task 관계가 기록돼야 전체 awaited-by graph를 만든다. [Task.get_stack](https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.get_stack), [call graph low-level API](https://docs.python.org/3/library/asyncio-graph.html#low-level-utility-functions) | 한 task stack snapshot을 전체 await chain 또는 wait duration 분포로 해석. |

## 오버헤드 근거의 품질

### 공개 수치

| 도구 | 공개 결과 | 증거 한계 | 판정 |
|---|---|---|---|
| cProfile | 2023 OSDI 연구의 10개 pyperformance-derived workload에서 median runtime 1.73×. 공식 문서는 “reasonable overhead”라고만 한다. [OSDI Table 3](https://www.usenix.org/system/files/osdi23-berger.pdf), [공식 소개](https://docs.python.org/3/library/profile.html#introduction-to-the-profilers) | Linux 5.13, CPython 3.10.9, 2022 도구, 각 10회; 현재 CPython 3.14 cProfile은 `sys.monitoring` 구현이므로 숫자 이식 불가. 논문 저자는 Scalene 저자다. | **FACT**(그 실험 결과), 현재 프로젝트 overhead는 **UNSUPPORTED** |
| py-spy | 같은 연구에서 median 1.02×. README는 “extremely low overhead”라고 주장한다. [OSDI Table 3](https://www.usenix.org/system/files/osdi23-berger.pdf), [README](https://github.com/benfred/py-spy) | 표본 rate/options/native/subprocess/nonblocking과 workload가 달라지면 달라진다. 저자 이해상충과 버전 노후화가 있다. | **FACT**(그 실험 결과), 일반적 “production safe”는 **UNSUPPORTED** |
| Scalene | 같은 연구에서 CPU 1.02×, full 1.32× median. 현재 README 한 곳은 typical 10–20%, 다른 비교 문구는 pyperformance 35%라고 적는다. [OSDI Table 3](https://www.usenix.org/system/files/osdi23-berger.pdf), [README](https://github.com/plasma-umass/scalene#fast-and-accurate) | 도구 저자 연구, 2022 build/CPython 3.10.9. README 수치는 서로 다른 설정/버전일 수 있으나 재현 조건이 같은 표에 있지 않다. | **FACT**(논문 실험), 현재 vendor 정량 일반화는 **UNSUPPORTED** |
| Memray | 같은 연구에서 median 3.98× 및 약 3MB/s capture growth를 보고했다. Memray 자체 성능 페이지는 pyperformance/pyperf 반복, isolated CPU 등 방법을 공개하지만 Python 3.10.9·Memray 1.5.0이다. [OSDI §6.5/Table 3](https://www.usenix.org/system/files/osdi23-berger.pdf), [Memray performance](https://bloomberg.github.io/memray/performance.html) | 현재 1.20.0과 다르고 allocation rate, native, Python allocator, output filesystem에 강하게 의존한다. 자체 페이지 결과 그래프는 vendor 측 실험이다. | **FACT**(과거 실험), 현재 프로젝트 overhead는 **UNSUPPORTED** |
| VizTracer | 공식 문서는 “low-overhead”라고 하지만 비교 가능한 수치·환경·반복·분포를 제공하지 않는다. [문서 홈](https://viztracer.readthedocs.io/en/stable/) | 이벤트 빈도, C event, filters, async, buffer/dump 크기에 따라 달라진다. | **UNSUPPORTED** |
| `sys.monitoring` | PEP 669는 no-event에서 1–2% speedup 예상, 적은 event callback은 기존 `settrace`보다 훨씬 저렴할 것으로 예상했다. LINE처럼 heavy instrumentation은 callback 비용이 지배한다고 명시했다. [PEP 669](https://peps.python.org/pep-0669/#performance) | 역사적 설계 문서의 예상이며 현재 callback 구현이나 프로젝트 결과가 아니다. | **FACT**(PEP의 예상/제약), 실제 overhead는 **UNSUPPORTED** |
| asyncio debug/introspection | 공식 문서는 기능과 threshold를 정의하지만 slowdown 숫자는 제시하지 않는다. [asyncio debug](https://docs.python.org/3/library/asyncio-dev.html#debug-mode) | selector/callback 빈도, logging sink, stack 수집에 따라 다름. | **UNSUPPORTED** |

### 프로젝트 overhead 검증 계약

다음은 채택 결론이 아니라 후속 실험이 따라야 할 **PROJECT-HYPOTHESIS**다.

1. 승인된 fixture마다 `no-profiler control`과 `tool+exact-options treatment`를 동일 image, Python, dependency lock, input/seed, worker 수, warm-up 상태로 실행한다. [pyperf architecture와 warm-up](https://pyperf.readthedocs.io/en/latest/run_benchmark.html#pyperf-architecture)
2. 실행 순서는 단순히 control 전부 후 treatment 전부가 아니라 block 내에서 교차/무작위화한다. host load, thermal state, cache, run order를 block metadata로 보존한다. NIST는 “block what you can, randomize what you cannot”를 권고한다. [NIST randomized blocks](https://www.itl.nist.gov/div898/handbook/pri/section3/pri332.htm)
3. wall time, process CPU, peak RSS, output bytes, 실패율, timeout, request/throughput/latency 또는 batch records/s를 동시에 수집한다. profiler 자체 순위가 아니라 **workload의 사용자 관찰 metric 변화**를 probe effect로 판정한다.
4. 최소 반복 수를 고정 상수로 미리 가장하지 않는다. run/value/warm-up을 충분히 늘리고 분포·불안정 경고·raw run을 보존한다. [pyperf reproducibility](https://pyperf.readthedocs.io/en/latest/run_benchmark.html#how-to-get-reproducible-benchmark-results)
5. pyperformance는 whole application을 선호하는 범용 benchmark suite이지만 프로젝트 대표 workload를 대체하지 않는다. [pyperformance 목적](https://pyperformance.readthedocs.io/)
6. profiler 옵션을 바꾸면 별도 treatment다. 예: py-spy `--nonblocking/--gil/--idle/--native`, Memray `--native/--trace-python-allocators/--aggregate`, VizTracer filter/C-function/async, Scalene cpu-only/memory/async, `sys.monitoring` event set.
7. 허용 overhead budget은 이 연구가 정하지 않는다. 운영 SLO·CI 시간·storage/security 정책의 후속 결정 입력이어야 한다.

## 권한·호환성·운영 제약

| 도구 | 2026-08-29 호환성 근거 | 권한/대상 변경 | process·artifact 제약 | 상태 |
|---|---|---|---|---|
| cProfile | stdlib. 현재 문서는 Python 3.14.7. `pstats` 파일은 미래 버전·다른 OS·다른 profiler와 호환 보장 없음. [문서](https://docs.python.org/3/library/profile.html#the-stats-class) | 별도 ptrace 없음. 그러나 workload 실행 자체가 정책 승인 대상이고 프로세스 내부 callback을 활성화한다. | 정상 return 전 종료 시 출력이 없을 수 있다. process별 profile 수집/merge가 필요. | **FACT** |
| py-spy 0.4.2 | README: CPython 2.3–2.7, 3.3–3.14; Linux/macOS/Windows/FreeBSD. native stack은 Linux x86-64/ARM/AArch64와 Windows x86-64 중심. [README](https://github.com/benfred/py-spy), [PyPI](https://pypi.org/project/py-spy/) | child를 launch하면 Linux에서 보통 root 불필요; 기존 PID attach는 보통 ptrace/root, macOS는 root, Docker/Kubernetes는 대개 `SYS_PTRACE`. host hardening 완화는 보안 영향. | stripped symbols/ABI 탐색, SIP, Alpine/musl, container namespace를 canary. | **FACT** |
| Scalene 2.3.0 | PyPI `Requires-Python: >=3.8, !=3.11.0`; classifier는 Python 3.8–3.14, Linux/macOS/Windows. current wheels와 architecture availability는 대상 matrix에서 별도 확인. [PyPI JSON](https://pypi.org/pypi/scalene/json), [install](https://github.com/plasma-umass/scalene#installation) | launch/in-process sampling, signals, allocator interposition을 사용한다. old paper의 NVIDIA accounting 설정은 superuser가 필요할 수 있었다. [OSDI §2–4](https://www.usenix.org/system/files/osdi23-berger.pdf) | README의 current async/free-threaded/multiprocess 기능은 격리 canary가 필요. GUI는 offline 가능하나 AI optimization provider는 별도 외부 전송 경로다. | **FACT**(metadata/mechanism), 성과는 **UNSUPPORTED** |
| Memray 1.20.0 | CPython >=3.9; PyPI classifier 3.9–3.15, Linux/macOS, Windows 미지원. [PyPI JSON](https://pypi.org/pypi/memray/json) | run은 대상 내부에서 allocator를 intercept. attach는 gdb/lldb와 ptrace 권한, 대상 env에 Memray 설치, code injection이 필요하며 crash/deadlock 가능성 때문에 문서는 dev machine만 권고한다. [attach](https://bloomberg.github.io/memray/attach.html) | follow-fork는 child별 파일. aggregate는 작지만 process kill/OOM 시 유용한 파일이 남지 않을 수 있다. default mmap output은 filesystem 제약, buffered I/O는 더 느리고 crash-resilience가 낮다. [run](https://bloomberg.github.io/memray/run.html) | **FACT** |
| VizTracer 1.1.1 | Python >=3.10; classifier 3.10–3.14 및 free-threaded, Linux/macOS/Windows. [PyPI JSON](https://pypi.org/pypi/viztracer/json) | normal run은 in-process. attach는 Windows 미지원, Linux gdb/macOS lldb, 대상 env import 가능성이 필요. installed attach는 SIGUSR1/2를 점유한다. [remote attach](https://viztracer.readthedocs.io/en/stable/remote_attach.html) | pre-3.12는 `sys.setprofile`, 3.12+는 `sys.monitoring`을 써 같은 mechanism 도구와 충돌 가능. `os._exit`은 저장 불가. [limitations](https://viztracer.readthedocs.io/en/stable/limitations.html) | **FACT** |
| `sys.monitoring` | Python 3.12 추가. current docs는 tool ID 0–5, profiler/debugger/coverage convention을 정의한다. [문서](https://docs.python.org/3/library/sys.monitoring.html) | in-process callback. 권한 상승은 없지만 임의 callback 코드가 실행되고 audit event가 발생한다. | tool ID 충돌 확인, global/local event 정리, callback recursion/다른 tool 상호작용 관리가 필요. process별 구현. | **FACT** |
| asyncio stdlib | debug/task stack은 넓은 버전에서 가능. call graph와 외부 `ps/pstree`는 Python 3.14 추가. [graph](https://docs.python.org/3/library/asyncio-graph.html), [tools](https://docs.python.org/3/library/asyncio-tools.html) | in-process debug는 별도 ptrace 없음. 3.14 외부 inspection은 target 코드를 실행하지 않지만 supported platform과 inspect permission이 필요하다. [CLI](https://docs.python.org/3/library/asyncio-tools.html) | loop/thread별 snapshot이며 분포나 duration을 자동 축적하지 않는다. remote inspection은 Linux `CAP_SYS_PTRACE`, macOS root, Windows admin/SeDebugPrivilege 등이 필요할 수 있다. [CPython permission guide](https://docs.python.org/3/howto/remote_debugging.html#permission-requirements) | **FACT** |

**PROJECT-HYPOTHESIS — 권한 원칙:** 기존 host의 `ptrace_scope`, seccomp, container capability, SIP 또는 remote-debug 설정을 profiler 편의를 위해 영구 완화하지 않는다. 승인된 일회용 sandbox에서 최소 권한으로 launch 우선, attach는 별도 승인·감사·teardown을 거친다. 이는 attach가 process memory 읽기 또는 code injection을 사용한다는 공식 제약에서 파생된다. [CPython permission guide](https://docs.python.org/3/howto/remote_debugging.html#permission-requirements), [Memray attach security warning](https://bloomberg.github.io/memray/attach.html#debugger-privileges), [py-spy permissions](https://github.com/benfred/py-spy#when-do-you-need-to-run-as-sudo)

## 후속 결정용 조건부 후보 집합

아래는 도구 선정이 아니라 **진입 조건과 탈락 조건**이다. 조건을 충족해도 채택이 아니라 격리 평가 후보가 된다.

| 후보 | 후보가 되는 질문/조건 | 단독으로 부족하거나 보류하는 조건 | 필요한 최소 대조 |
|---|---|---|---|
| cProfile을 ‘기본 후보’로 평가 | 승인된 재실행이 가능; stdlib만 허용; 함수별 call count/caller/callee와 누적시간이 질문; pure-Python 호출 구조가 핵심; attach 권한이 없어야 함. [공식 용도](https://docs.python.org/3/library/profile.html) | allocation/native/system/I/O/await/multiprocess가 핵심; 매우 call-dense한 경로; tail/sporadic chronology; workload가 정상 return하지 않음. [한계](https://docs.python.org/3/library/profile.html#limitations) | unprofiled control 대 cProfile, 호출 밀도가 다른 fixture, Python 버전별 thread/process capture 완전성. |
| py-spy 추가 후보 | 재시작 없이 기존 PID의 all-thread stack 표본이 필요; 낮은 계측성 표본을 결정론적 profile과 교차검증; child process/GIL/native 지원 범위가 질문과 일치; ptrace 정책 승인 가능. [README](https://github.com/benfred/py-spy) | 짧거나 희귀 호출의 정확한 count; memory; suspended asyncio task 전체; native가 미지원 architecture; 권한 완화 불가. | sample rate/phase 반복, blocking/nonblocking 결과와 error rate, `--idle`/`--gil` sensitivity, control overhead. |
| Scalene 추가 후보 | 한 run에서 line별 Python/native/system, allocation/copy, async await concurrency 또는 multiprocess 가설을 좁혀야 함; target wheel/platform과 signal/allocator mechanism이 격리 환경에서 허용. [README](https://github.com/plasma-umass/scalene#scalene-overview) | vendor 정확도만 근거; 작은/짧은 workload; gevent/monkeypatch/signal/allocator 충돌; 결과에 포함된 AI patch suggestion을 진단 증거로 쓰려 함. | cpu-only와 각 기능 추가 treatment, 현재 version canary, synthetic ground truth와 대표 workload, cProfile/py-spy 또는 Memray의 독립 차원 교차검증. |
| Memray 추가 후보 | RSS 증가, allocation hotspot, native allocator, leak/temporary object, fork child memory가 질문; 충분한 disk와 재실행 가능; Linux/macOS CPython. [run](https://bloomberg.github.io/memray/run.html) | CPU/I/O/event-loop 질문; Windows; production attach 우선; OOM 직전 aggregate만 보존; capture/PII 경로 불명. | default→필요 시 native→필요 시 Python allocator를 각각 별도 run, output growth/overhead, child capture completeness, known allocation/leak fixture. |
| VizTracer 추가 후보 | sporadic latency, 함수 순서, task/thread/process 상호작용을 timeline으로 봐야 함; 관심 구간이 buffer 안에 들어감; Python 3.10+. [basic](https://viztracer.readthedocs.io/en/stable/basic_usage.html), [concurrency](https://viztracer.readthedocs.io/en/stable/concurrency.html) | aggregate hotspot만 필요; 매우 높은 event rate/장시간; Windows Pool 또는 일반 subprocess patch 조건 불일치; 다른 profile hook 도구와 동시 사용. | no-trace control, buffer overflow flag, C function/filter/async를 별도 treatment, known-order concurrency fixture. |
| `sys.monitoring` custom probe 후보 | 기존 도구가 답하지 못하는 특정 PY_YIELD/RESUME/CALL/LINE event가 있고 Python 3.12+가 확정; 최소 event/local-code만 켜는 작은 probe를 구현·검증할 가치가 있음. [공식 API](https://docs.python.org/3/library/sys.monitoring.html) | 범용 profiler가 이미 답함; Python <3.12/다른 implementation; global LINE/INSTRUCTION이 필요; tool ID/cleanup contract 없음. | no-event/no-op-callback/real-callback 세 treatment, local 대 global event, event count ground truth, cleanup 후 무영향 확인. |
| asyncio stdlib 관찰 후보 | loop starvation, slow callback, pending task, await chain/cycle가 질문; 3.14이면 call graph/`ps`/`pstree`를 격리 최신 경로로 평가. [debug](https://docs.python.org/3/library/asyncio-dev.html), [CLI](https://docs.python.org/3/library/asyncio-tools.html) | CPU/memory/endpoint I/O attribution; task lifetime/latency histogram; 비-asyncio framework; 3.14 기능을 기준 브랜치에 강제. | debug off/on, threshold sweep, known task tree/deadlock fixture, snapshot completeness와 overhead. |

**UNSUPPORTED:** “항상 cProfile부터”, “운영은 항상 py-spy”, “다차원이므로 Scalene 하나면 충분”, “memory면 Memray가 무조건 정확”, “timeline이면 VizTracer가 저비용” 같은 규칙. 위 원문은 그런 프로젝트 전역 결론을 지지하지 않는다.

## 안전한 실행 순서

다음 단계는 **PROJECT-HYPOTHESIS**이며 승인 전에는 1단계에서 멈춘다.

1. **정적 triage(자동 허용):** 위험 후보, 핵심 경로, 실행 entrypoint, Python/OS/architecture, concurrency model, expected workload와 관찰 질문을 기록한다. 도구를 아직 선택하지 않는다.
2. **정책 승인 packet:** 정확한 command/image/tool version/options, 입력 데이터 등급, outbound network, ptrace/capability/signal/port, CPU/RAM/disk/time cap, artifact 경로·retention·삭제, stop condition, 담당자를 명시한다.
3. **격리 preflight:** target과 동일한 disposable image에서 설치/wheel/native symbol/debug info, tool-ID/signal/port 충돌, output 쓰기, child/fork 수집, clean teardown을 최소 fixture로 확인한다. production PID attach는 여기서 하지 않는다.
4. **대표 workload 계약:** 정기 기준 브랜치와 release candidate에 동일한 snapshot/input/seed/worker/concurrency/warm-up을 사용한다. cold-start, steady-state, CPU-heavy, native-heavy, allocation-heavy, I/O-heavy, asyncio, multiprocess 중 실제 노출을 대표하는 strata를 따로 둔다. pyperformance는 안정화 도구이지 제품 workload 대체물이 아니다. [pyperformance](https://pyperformance.readthedocs.io/)
5. **무계측 control:** profiler 없이 정상 실행을 반복해 output correctness, throughput/latency, wall/CPU/RSS, error, system noise를 저장한다. profiler는 benchmark 용도가 아니라는 Python 경고를 지킨다. [공식 profiler 경고](https://docs.python.org/3/library/profile.html#introduction-to-the-profilers)
6. **한 번에 한 treatment:** 한 profiler와 한 option set만 켠다. 여러 profiler를 동시에 켜지 않는다. 특히 profile/monitoring hook, signals, allocators, trace buffer가 상호 간섭할 수 있다. [VizTracer hook 충돌](https://viztracer.readthedocs.io/en/stable/limitations.html), [`sys.monitoring` tool model](https://docs.python.org/3/library/sys.monitoring.html)
7. **가장 좁은 범위부터 확장:** 질문을 답하는 최소 event/기간/process/file 범위로 canary한 뒤 증거 공백이 남을 때만 native, Python allocator, line/instruction, async, all-subprocess, longer buffer를 각각 별도 run으로 추가한다.
8. **probe-effect gate:** control 대비 correctness/error/timeout/resource/latency가 예산을 넘거나 rank가 option 변화에 불안정하면 결과는 `DYNAMIC_OBSERVED_BIASED`로 보류한다. overhead 자체를 빼서 “보정한 시간”을 만들지 않는다.
9. **독립 교차 관찰:** 같은 현상을 다른 원리의 도구나 stdlib metric으로 확인한다. 예: deterministic call count 대 external sampling, RSS/allocator record, profiler stack 대 asyncio await graph. 일치하지 않으면 원인을 조사하지 평균내지 않는다.
10. **핵심 경로 counterfactual:** profiler hotspot만으로 기여를 확정하지 않는다. 기능 보존 대체, 경로 bypass/toggle, input stratum 제거, concurrency 변화 등 사전 정의한 treatment와 control을 같은 block에서 비교한다. 결과 metric의 effect와 불확실성을 기록한다. [NIST block design](https://www.itl.nist.gov/div898/handbook/pri/section3/pri332.htm)
11. **승격/폐기:** 재현성과 counterfactual을 통과한 항목만 검증된 위험 우선순위표에 넣는다. 실패한 가설도 tool/options/workload와 함께 남겨 선택적 보고를 막는다.
12. **최신 기능 격리:** Python 3.14 asyncio external introspection, current async/free-threaded profiler support, custom `sys.monitoring` probe는 기준 경로와 별도 experiment lane에서만 평가하고 호환·overhead·의미가 입증되기 전 release gate에 편입하지 않는다.

## 시스템 설계에 주는 함의

### 1. 동적 검증은 opt-in capability여야 한다

- **PROJECT-HYPOTHESIS:** 정기 기준 브랜치와 release candidate의 자동 단계는 정적 읽기까지다. 동적 run은 승인 token이 있는 job만 수행하며 token은 tool/version/options/workload/권한/resource cap에 묶인다.
- **PROJECT-HYPOTHESIS:** 승인되지 않은 상태를 실패로 위장하지 않고 `NOT_RUN_POLICY`로 출력한다. 실행 증거가 없으면 risk row는 `STATIC_HYPOTHESIS` 이상으로 승격하지 않는다.
- 근거: attach와 debug/profile은 process 동작·권한·보안 상태를 바꿀 수 있다. [py-spy 권한](https://github.com/benfred/py-spy#when-do-you-need-to-run-as-sudo), [Memray attach caveats](https://bloomberg.github.io/memray/attach.html#caveats), [asyncio debug behavior](https://docs.python.org/3/library/asyncio-dev.html#debug-mode)

### 2. 관찰 모델은 하나의 ‘profile score’가 아니라 typed evidence여야 한다

**PROJECT-HYPOTHESIS:** 내부 event schema는 최소한 다음 차원을 분리한다.

- `cpu_sample`, `elapsed_call`, `call_count`, `allocation`, `resident_memory`, `copy_volume`, `system_wait`, `async_suspended`, `slow_callback`, `task_graph`, `timeline_event`
- `wall_clock`와 `process_cpu`, Python/native/system, active/idle/GIL-filtered, parent/child PID, thread/task ID
- exact `tool`, `version`, `options`, Python build(GIL/free-threaded 포함), OS/kernel/arch/image digest
- `sampling_interval`, event set, trace window, buffer capacity/overflow, lost/partial sample count, symbol quality

근거: 각 도구가 서로 다른 값을 측정하므로 합치면 의미가 사라진다. [cProfile 필드 정의](https://docs.python.org/3/library/profile.html#instant-user-s-manual), [Memray allocator 모델](https://bloomberg.github.io/memray/run.html#python-allocator-tracking), [asyncio task 모델](https://docs.python.org/3/library/asyncio-task.html#task-object)

### 3. 검증된 위험 우선순위표의 최소 열

| 열 | 의미 |
|---|---|
| `rank`, `risk_id`, `state` | `STATIC_HYPOTHESIS`, `NOT_RUN_POLICY`, `DYNAMIC_OBSERVED`, `DYNAMIC_OBSERVED_BIASED`, `CONTRAST_CONFIRMED`를 분리한다. |
| `commit_pair`, `workload_id`, `stratum`, `environment_digest` | 기준 브랜치와 RC를 동일 조건으로 재현하는 identity. |
| `dimension`, `location`, `process/thread/task scope` | CPU/memory/I/O/loop 등 typed evidence와 source path/symbol. |
| `tool_version_options`, `observation_window`, `coverage_limits` | 결과가 무엇을 보았고 놓쳤는지. |
| `control_distribution`, `profiled_distribution`, `probe_effect` | profiler 때문에 바뀐 wall/CPU/RSS/latency/error/output. |
| `observed_share_or_bytes`, `uncertainty`, `repeat_count` | 표본 비중·할당량·호출시간과 변동성; 서로 다른 단위를 섞지 않는다. |
| `counterfactual`, `effect_on_user_metric`, `confidence` | 핵심 경로 기여를 확인한 대조와 effect. 없으면 `CONTRAST_CONFIRMED` 금지. |
| `permission_delta`, `data_sensitivity`, `artifact_uri_hash`, `retention` | 감사·보안·재현 정보. |
| `source_urls`, `limitations`, `decision_needed` | 원문, 알려진 왜곡, 후속 결정 사항. |

- **PROJECT-HYPOTHESIS:** 우선순위는 profiler의 hotspot percentage 하나가 아니라 사용자 영향(effect), 노출 빈도, 재현성, counterfactual confidence, 증거 완전성을 기반으로 한다. 차원이 다른 값은 단일 정밀 숫자로 억지 합산하지 않고 동률 bucket 또는 명시적 정책 가중치를 사용한다.
- **UNSUPPORTED:** 현 시점에서 risk-score 공식이나 pass/fail overhead threshold를 고정하는 것. 제품 SLO와 workload 자료가 없다.

### 4. branch 비교에는 format과 version pin이 필요하다

- **FACT:** cProfile stats는 미래 버전 또는 다른 OS와 file compatibility가 보장되지 않는다. [pstats 문서](https://docs.python.org/3/library/profile.html#the-stats-class)
- **FACT:** Memray native report는 capture와 같은 machine/library가 필요하다. [native mode](https://bloomberg.github.io/memray/native_mode.html)
- **PROJECT-HYPOTHESIS:** 기준/RC는 같은 tool/Python/image에서 새로 수집하고 raw vendor format을 장기 비교의 유일한 schema로 쓰지 않는다. normalization은 source identity와 원 raw artifact를 함께 보존한다.

### 5. 실패와 누락도 1급 증거여야 한다

- `permission_denied`, `unsupported_python`, `unsupported_arch`, `symbol_missing`, `buffer_overflow`, `capture_lost_on_oom`, `partial_stack`, `child_missing`, `tool_conflict`, `target_crash`, `timeout`을 risk finding과 분리해 기록한다.
- **PROJECT-HYPOTHESIS:** 누락을 0으로 대체하지 않는다. 예를 들어 child capture 없음은 child CPU 0이 아니고, sample 0은 경로 미실행이 아니다. [py-spy sampling model](https://github.com/benfred/py-spy#how-does-py-spy-work), [Memray follow-fork](https://bloomberg.github.io/memray/run.html#tracking-across-forks)

## 새 아이디어

1. **PROJECT-HYPOTHESIS — capability manifest:** job 시작 전에 Python/OS/arch/build, ptrace, debugger, symbols, wheel, fork/spawn, event-loop 종류, signal/tool-ID 점유를 정적으로/비실행적으로 판별해 가능한 후보만 보여준다. 실제 attach 또는 profiler activation은 승인 후다.
2. **PROJECT-HYPOTHESIS — probe-effect fingerprint:** 각 tool-option 조합을 `runtime ratio`, `CPU ratio`, `peak RSS delta`, `artifact MB/s`, `error/timeout delta`, `lost sample` 벡터로 저장한다. 한 숫자보다 option별 왜곡을 비교하기 쉽다. [Memray overhead sources](https://bloomberg.github.io/memray/performance.html#source-of-the-overhead)
3. **PROJECT-HYPOTHESIS — dimension triangulation graph:** 정적 후보→cProfile 호출 관계→py-spy stack sample→Memray allocation→asyncio task graph처럼 서로 다른 원리의 evidence edge를 연결하되 자동 합산하지 않는다. 독립 edge 수와 모순을 confidence 입력으로 쓴다.
4. **PROJECT-HYPOTHESIS — negative-control fixtures:** no-op function density, known sleep/socket wait, short burst, native GIL-release, bounded leak, task deadlock, fork/spawn child를 갖춘 작은 synthetic fixture로 도구 의미를 먼저 검증한다. synthetic 성능 순위를 제품 결과로 사용하지 않는다.
5. **PROJECT-HYPOTHESIS — async flight window:** 장시간 full trace 대신 stdlib task snapshot/3.14 `pstree`로 blocked branch를 좁힌 뒤 승인된 짧은 VizTracer/Scalene window를 여는 경로를 실험한다. [asyncio CLI](https://docs.python.org/3/library/asyncio-tools.html), [VizTracer remote duration](https://viztracer.readthedocs.io/en/stable/remote_attach.html)
6. **PROJECT-HYPOTHESIS — evidence expiry:** tool/Python minor, OS image, concurrency model, workload 또는 critical path가 바뀌면 기존 dynamic evidence를 stale로 표시한다. 2023 공개 overhead 수치를 현재 버전에 적용할 수 없는 문제를 시스템적으로 막는다.
7. **PROJECT-HYPOTHESIS — artifact pressure preflight:** event/allocation rate로 worst-case trace/capture 크기를 짧은 canary에서 추정하고 cap 초과 전에 중단한다. circular buffer overwrite와 OOM capture loss를 명시적으로 검출한다. [VizTracer buffer](https://viztracer.readthedocs.io/en/stable/basic_usage.html#circular-buffer-size), [Memray OOM/aggregate](https://bloomberg.github.io/memray/run.html#losing-capture-files-after-oom-errors)

## 기각 또는 보류 아이디어

| 아이디어 | 상태 | 이유 |
|---|---|---|
| cProfile을 모든 승인 run의 고정 기본값으로 즉시 채택 | **보류** | stdlib/호출 통계 장점은 FACT지만 I/O/async/memory/native/multiprocess 질문을 답하지 못하고 call-density bias가 있다. 후보 조건으로만 유지한다. [공식 한계](https://docs.python.org/3/library/profile.html#limitations) |
| py-spy를 ‘production safe’로 자동 attach | **기각** | vendor의 safe 주장은 독립 증거가 아니며 ptrace/root/capability와 대상 pause 또는 partial-read trade-off가 있다. [README FAQ](https://github.com/benfred/py-spy#when-do-you-need-to-run-as-sudo) |
| Scalene 하나로 CPU/memory/I/O/async를 모두 확정 | **기각** | 기능 폭은 넓지만 system/I/O는 추론이고 현재 버전 정확도·overhead 프로젝트 증거가 없다. README 비교는 현재 다른 도구도 지원하는 기능을 “Scalene only”로 적는 등 의사결정 표로 신뢰하기 어렵다. [Scalene 비교](https://github.com/plasma-umass/scalene#comparison-to-other-profilers) |
| Scalene AI optimization/patch 성과를 진단 성과로 사용 | **기각** | patch 제안은 외부/로컬 model 선택과 별개 기능이며 hotspot의 원인·기여를 증명하지 않는다. vendor도 provider credential과 제안 복사를 설명할 뿐 진단 검증을 보장하지 않는다. [Scalene AI section](https://github.com/plasma-umass/scalene#ai-powered-optimization-suggestions) |
| 여러 profiler를 한 run에 동시에 켜서 비용 절감 | **기각** | hook/tool ID/signal/allocator/output 간 상호작용으로 관찰 대상과 profiler 자체가 바뀐다. VizTracer는 같은 mechanism 도구 충돌을 명시한다. [VizTracer limitations](https://viztracer.readthedocs.io/en/stable/limitations.html) |
| Memray `--trace-python-allocators --native`를 첫 memory run으로 사용 | **보류** | 공식 문서가 더 느리고 훨씬 큰 파일을 경고한다. default에서 정보 공백이 확인된 후 별도 treatment로만 후보. [run](https://bloomberg.github.io/memray/run.html#python-allocator-tracking) |
| OOM 진단에 Memray aggregate만 사용 | **기각** | process가 종료 전에 aggregate를 계산하지 못하면 유용한 capture가 남지 않는다. [aggregated capture](https://bloomberg.github.io/memray/run.html#aggregated-capture-files) |
| py-spy `--gil` profile을 전체 CPU 진실로 사용 | **기각** | GIL을 release한 native extension activity를 누락한다고 공식 FAQ가 경고한다. [GIL FAQ](https://github.com/benfred/py-spy#how-does-gil-detection-work) |
| asyncio debug를 release gate에 항상 활성화 | **보류** | 동작을 바꾸고 공식 정량 overhead가 없다. event-loop 질문의 승인된 별도 treatment로 평가한다. [debug mode](https://docs.python.org/3/library/asyncio-dev.html#debug-mode) |
| Python 3.14 asyncio `ps/pstree`, free-threaded profiling, custom `sys.monitoring`을 즉시 기준 경로에 포함 | **보류/격리** | 최신 기능은 target version/platform과 의미·overhead 증거가 필요하다. 실험 lane 결과가 쌓일 때까지 standard release gate와 분리한다. [asyncio tools](https://docs.python.org/3/library/asyncio-tools.html), [`sys.monitoring`](https://docs.python.org/3/library/sys.monitoring.html) |
| vendor overhead 수치로 pass/fail budget 설정 | **기각** | 공개 실험은 버전·host·workload가 다르고 일부는 vendor authored 또는 정성 주장이다. [OSDI setup](https://www.usenix.org/system/files/osdi23-berger.pdf), [Memray setup](https://bloomberg.github.io/memray/performance.html#test-system) |

## 미해결 질문

1. 기준 브랜치와 release candidate가 실제로 지원해야 하는 Python minor, CPython/free-threaded/PyPy, OS, architecture, container 조합은 무엇인가? 호환 후보를 결정하는 선행 입력이다. [현재 package metadata](https://pypi.org/pypi/scalene/json)
2. production-like workload strata는 무엇이며 cold start, steady state, peak concurrency, long tail, data size, cache warmness, network/DB fixture를 어떻게 고정할 것인가? [pyperf warm-up/반복](https://pyperf.readthedocs.io/en/latest/run_benchmark.html)
3. 사용자 영향 metric과 허용 probe-effect budget은 무엇인가? throughput, p95/p99, batch duration, peak RSS, error/timeout 중 release gate 우선순위가 없다.
4. profiler 승인 authority, audit record, 만료 시간, ptrace/capability/attach 허용 환경은 무엇인가? [permission requirements](https://docs.python.org/3/howto/remote_debugging.html#permission-requirements)
5. source path, arguments/return/local variables, task names, endpoint 정보가 capture에 들어갈 때 데이터 등급·redaction·retention은 무엇인가? VizTracer와 py-spy는 선택적으로 값/locals를 기록할 수 있다. [py-spy dump locals](https://github.com/benfred/py-spy#dump), [VizTracer extra logs](https://viztracer.readthedocs.io/en/stable/extra_log.html)
6. multiprocessing은 `fork`, `spawn`, `forkserver`, worker pool, Gunicorn/Celery 중 무엇인가? 도구별 child 추적 의미와 파일 병합이 다르다. [Memray fork](https://bloomberg.github.io/memray/run.html#tracking-across-forks), [VizTracer concurrency](https://viztracer.readthedocs.io/en/stable/concurrency.html)
7. asyncio 외에 Trio, AnyIO, gevent/greenlet, uvloop을 쓰는가? 표준 asyncio 관찰과 vendor async attribution의 coverage를 별도 검증해야 한다.
8. native extensions는 symbols/debug info와 동일-image report generation을 보장할 수 있는가? [Memray native mode](https://bloomberg.github.io/memray/native_mode.html)
9. 핵심 경로의 기여를 검증할 기능 보존 counterfactual은 무엇인가? path bypass가 semantics를 바꾸면 causal evidence가 되지 않으므로 사전 정의가 필요하다. [NIST experiment design](https://www.itl.nist.gov/div898/handbook/pri/section3/pri3.htm)
10. profiler artifact의 최대 크기, 저장소, encryption, upload 허용 여부, OOM/crash 시 salvage 규칙은 무엇인가? [Memray capture options](https://bloomberg.github.io/memray/run.html), [VizTracer buffer](https://viztracer.readthedocs.io/en/stable/basic_usage.html#circular-buffer-size)
11. current release별 independent overhead/accuracy 자료가 있는가? 이번 조사에서는 2024년 이후 동일 workload·동일 옵션으로 cProfile/py-spy/Scalene/Memray/VizTracer를 비교한 독립 원문을 찾지 못했다. 이 공백은 **UNSUPPORTED**를 유지해야 할 이유다.

## 출처

### Python 공식 원문

1. Python 3.14.7, **The Python Profilers** — 결정론적 profiling, cProfile 권장 범위, benchmark 경고, 필드, 한계, pstats 호환성. <https://docs.python.org/3/library/profile.html>
2. CPython 3.14 source, **`Modules/_lsprof.c`** — cProfile의 performance counter와 `sys.monitoring` callback 구현. <https://github.com/python/cpython/blob/3.14/Modules/_lsprof.c>
3. Python 3.14.7, **`sys.monitoring` — Execution event monitoring** — 3.12+, tool IDs/events/callbacks. <https://docs.python.org/3/library/sys.monitoring.html>
4. PEP 669, **Low Impact Monitoring for CPython** — historical rationale, performance/memory expectations와 heavy callback 제약. <https://peps.python.org/pep-0669/>
5. Python 3.14.7, **Developing with asyncio** — debug mode, selector와 slow callback 관찰, concurrency model. <https://docs.python.org/3/library/asyncio-dev.html>
6. Python 3.14.7, **Coroutines and tasks** — `all_tasks`, `get_stack`, cooperative task semantics. <https://docs.python.org/3/library/asyncio-task.html#introspection>
7. Python 3.14.7, **Call graph introspection** — 3.14 `capture/print_call_graph`와 awaited-by cooperation. <https://docs.python.org/3/library/asyncio-graph.html>
8. Python 3.14.7, **Command-line introspection tools** — 3.14 external `ps/pstree`, 무코드실행 inspection과 permission. <https://docs.python.org/3/library/asyncio-tools.html>
9. Python 3.14.7, **Remote debugging attachment protocol** — OS별 permission과 hardening 영향. <https://docs.python.org/3/howto/remote_debugging.html#permission-requirements>
10. Python 3.14.7, **timeit** — profiler가 아닌 timing 도구, GC와 측정 caveat. <https://docs.python.org/3/library/timeit.html>

### 도구 공식 원문과 현재 패키지 메타데이터

11. benfred, **py-spy README/FAQ** — sampling/read-memory model, versions/platforms, native/subprocess, idle/GIL, permission/container, nonblocking trade-off. <https://github.com/benfred/py-spy>
12. PyPI, **py-spy 0.4.2 metadata** (2026-04-24 upload). <https://pypi.org/pypi/py-spy/json>
13. plasma-umass, **Scalene README** — current documented capabilities/options/install; 성능·정확성 문구는 vendor 주장으로 취급. <https://github.com/plasma-umass/scalene>
14. PyPI, **Scalene 2.3.0 metadata** (2026-05-12 upload). <https://pypi.org/pypi/scalene/json>
15. Bloomberg, **Memray documentation home** — allocator/native memory scope. <https://bloomberg.github.io/memray/>
16. Bloomberg, **Memray run** — native/Python allocator, fork, OOM, aggregate, file I/O. <https://bloomberg.github.io/memray/run.html>
17. Bloomberg, **Memray attach** — debugger privileges, injection, dev-only caveat. <https://bloomberg.github.io/memray/attach.html>
18. Bloomberg, **Memray native mode** — symbol/debug info와 same-machine 제약. <https://bloomberg.github.io/memray/native_mode.html>
19. Bloomberg, **Memray performance** — pyperformance/pyperf 방법과 old version 실험. <https://bloomberg.github.io/memray/performance.html>
20. Bloomberg, **Memray API** — thread/fork tracking과 RSS sample interval. <https://bloomberg.github.io/memray/api.html>
21. PyPI, **Memray 1.20.0 metadata** (2026-08-07 upload). <https://pypi.org/pypi/memray/json>
22. VizTracer, **official docs** — tracing 목적. <https://viztracer.readthedocs.io/en/stable/>
23. VizTracer, **Concurrency** — asyncio/thread/subprocess/multiprocess coverage와 제약. <https://viztracer.readthedocs.io/en/stable/concurrency.html>
24. VizTracer, **Limitations** — `sys.setprofile`/`sys.monitoring` conflict, WSL1, exit loss. <https://viztracer.readthedocs.io/en/stable/limitations.html>
25. VizTracer, **Remote attach** — no Windows attach, gdb/lldb, injection/signals. <https://viztracer.readthedocs.io/en/stable/remote_attach.html>
26. VizTracer, **Filter** — overhead와 data-loss trade-offs. <https://viztracer.readthedocs.io/en/stable/filter.html>
27. VizTracer, **Basic usage** — circular buffer RAM/disk and output behavior. <https://viztracer.readthedocs.io/en/stable/basic_usage.html>
28. PyPI, **VizTracer 1.1.1 metadata** (2025-11-11 upload). <https://pypi.org/pypi/viztracer/json>

### 논문·측정 원리

29. Berger, Stern, Altmayer Pizzorno, **Triangulating Python Performance Issues with Scalene**, USENIX OSDI 2023, pp. 51–64 — algorithm, accuracy/overhead evaluation, Table 3. 도구 저자 연구이고 current release보다 오래됐다는 한계와 함께 사용. <https://www.usenix.org/conference/osdi23/presentation/berger> / <https://www.usenix.org/system/files/osdi23-berger.pdf>
30. pyperf, **Run a benchmark** — 반복 process/value, warm-up, 불안정성, 재현 방법. <https://pyperf.readthedocs.io/en/latest/run_benchmark.html>
31. pyperf, **Tune the system for benchmarks** — CPU isolation/pinning, system noise. <https://pyperf.readthedocs.io/en/latest/system.html>
32. pyperformance, **The Python Performance Benchmark Suite** — real-world/whole-application 지향. <https://pyperformance.readthedocs.io/>
33. NIST/SEMATECH, **Randomized block designs** — nuisance factor blocking과 randomization 원리. 오래됐지만 실험설계의 공식 기준 원리로 포함. <https://www.itl.nist.gov/div898/handbook/pri/section3/pri332.htm>

모든 URL은 2026-08-29에 확인했다. 공개 원문에 없는 현재 프로젝트 성능·정확도·안전성은 의도적으로 결론 내리지 않았다.
