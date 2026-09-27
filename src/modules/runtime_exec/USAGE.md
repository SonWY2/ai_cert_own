# 승인형 Docker 실행

```sh
python3 src/approve_run.py /path/to/repository /path/to/manifest.json /private/approval.json
python3 src/run_approved.py /path/to/source-bundle /path/to/manifest.json /private/approval.json /private/evidence
python3 src/run_approved.py --verify /path/to/source-bundle /path/to/manifest.json /private/evidence
```

`승인 영수증`은 소유자가 위 첫 명령을 **대화형 단말에서** 실행해, 화면에 표시된 정확한 RunManifest(대상 Git SHA, 명령, 이미지 digest, 자원 한도, 네트워크·전송 범위)를 읽고 SHA-256을 직접 입력할 때 저장소 밖에 생성되는 **일회용 승인 파일**이다. 오픈소스를 선택했다는 말이나 프로그램이 만든 시험용 영수증은 실제 승인으로 대신할 수 없다. RunManifest가 바뀌면 다시 확인·발급해야 한다.

`RunManifest`는 대상 Git commit, 로컬에 이미 있는 이미지 `sha256:...`, 정확한 node별 명령·제한·출력 위치를 지정한다. 이 Docker 실행기는 동결 Git 소스의 Python 스크립트, focused `pytest`/`unittest`, 선택형 `coverage run`과 cProfile을 지원한다. 테스트 node는 Git commit에 추적된 Python 파일 하나를 명시해야 한다(예: `pytest -q --asyncio-mode=auto tests/test_async.py::test_cancel`). 파일 없는 전체 discovery, 외부 경로, 임의 pytest 옵션과 모듈 dispatch는 허용하지 않는다. `coverage`는 `coverage run --data-file=/work/evidence/coverage.data -m pytest -q tests/test_async.py::test_cancel` 또는 같은 형식의 Python 테스트 파일을 사용하며 지정한 writable 출력 원본의 해시도 보존한다. `unittest`/`coverage` 실행 파일과 비동기 pytest plugin은 승인된 고정 이미지에 실제로 있어야 하며, 없으면 node는 실패 기록으로 남는다. 각 node의 `trigger`는 `always`(집중 테스트·Python 실행), `repeat3`(계측 없는 Python workload 3회), `slowdown:<앞선 repeat3 node ID>:<양의 밀리초 기준>`(재현됐을 때만 cProfile) 중 하나다. cProfile 명령은 `python -m cProfile -o /work/evidence/<이름>.pstats <workload>`처럼 선언된 쓰기 경로에 원본을 남겨야 한다. 프로파일러 명령·작업 디렉터리는 반복 제어 명령과 같아야 하며 출력 파일은 node별로 달라야 한다. 반복 제어 명령이 실패하거나 기준 미달이면 프로파일러를 실행하지 않는다.

승인 영수증은 정확한 manifest에 한 번만 쓸 수 있다. 실제 동적 명령은 승인된 Docker 호스트에서만 실행한다. Git 불변 원본에서 일반 파일만 복원하며 symlink·submodule은 거절한다. 작업 디렉터리는 읽기 전용으로 마운트하고 컨테이너 네트워크·권한을 제한한다. 종속성은 사전에 고정 이미지에 포함돼야 한다. 외부 네트워크가 필요한 workload는 지원하지 않는다. Docker 실행의 총 `wall_seconds`·`tool_seconds`, node별 동일한 시간 한도, 상위 호출자가 제공하는 공통 승인 deadline 중 가장 짧은 제한을 적용한다. node별 stdout/stderr 원본과 해시, 생성된 cProfile·coverage 원본과 해시를 `/private/evidence/execution.json`에 manifest·Git commit·명령·이미지·실행 순서와 함께 기록한다. 실패·timeout 노드는 성공 기록으로 취급하지 않고 후속 profiler 실행을 보류한다.

`docker info`로 daemon 연결을 확인한다. CPU·메모리·PID 제한이 강제되지 않는 Docker에서도 소유자가 정확한 RunManifest를 직접 승인한 **개발용 실행**은 허용하며, 승인 전·실행 전에 경고한다. `wall_seconds`·`tool_seconds`와 네트워크 차단·읽기 전용 마운트는 유지하지만 자원 한도 요청값은 강제됐다고 주장하지 않는다. 이런 실행은 동결된 최종 평가 호스트의 격리·A+ 실증을 대신하지 않는다.

`--verify`는 승인 영수증을 소비하거나 Docker를 실행하지 않고 동결 Git 소스, manifest, trace, 원본 로그·프로파일러 파일의 해시 및 DAG 순서를 대조한다. 일관된 로컬 trace는 **caller_declared_unattested**이며 Docker 실행 사실의 독립 증명이나 결함 oracle이 아니다. 위조자가 trace와 아티팩트를 함께 생성할 수 있으므로 어떤 발견도 이 검사만으로 confirmed로 승격하지 않는다. 승인된 대상 코드의 실제 격리·timeout·종료 처리는 아직 실측되지 않았다.
