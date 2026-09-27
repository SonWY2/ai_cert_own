# static_scan 사용법

```sh
python3 src/modules/static_scan/orchestrator.py /path/to/git/repository HEAD
python3 src/modules/static_scan/orchestrator.py /path/to/git/repository HEAD --node 'module:src/example.py' --hops 2 --limit 50
python3 src/modules/static_scan/orchestrator.py /path/to/git/repository HEAD --node 'module:src/example.py' --source-byte-budget 24000
python3 src/scan_sources.py /path/to/git/repository HEAD /path/outside/repository/evidence --node 'module:src/example.py' --hops 2
python3 src/scan_sources.py /path/to/git/repository HEAD /path/outside/repository/evidence --symbol 'example' --changed-file src/example.py --query 'await '
python3 src/scan_sources.py /path/to/git/repository HEAD /path/outside/repository/evidence --frame src/example.py:42
python3 src/scan_sources.py /path/to/git/repository HEAD /path/outside/repository/evidence --cache-dir /path/outside/repository/facts-cache
python3 src/scan_sources.py /path/to/git/repository HEAD /path/outside/repository/evidence --cache-dir /path/outside/repository/facts-cache --clean-replay
python3 src/scan_sources.py /path/to/git/repository HEAD /path/outside/repository/evidence --symbol 'example' --source-byte-budget 24000
```

`orchestrator.py`는 commit의 정적 사실 또는 선택 노드의 그래프 문맥을 출력한다. `scan_sources.py`는 같은 Git 동결 소스를 읽고 출처 근거를 저장하며, 선택적으로 심볼·외부에서 제공한 스택 프레임 위치(`--frame PATH:LINE`)·변경 파일 내 문자열·해석된 최대 2-hop 이웃 문맥을 반환한다. `--cache-dir`은 파일별 AST·심볼 사실만 재사용하고 출력 JSON의 `cache_events`에 key·적중/실패·무효화 이유·자료 해시를 표시한다. `--clean-replay`는 캐시와 clean 정적 사실을 비교한다. 매번 Git blob을 다시 읽어 source hash를 확인하며 그래프 연결·문맥·근거는 재계산한다. `stage: source_scanned`는 진단 보고서나 최종 `ScanRun`이 아니다.

Git `refs/replace` 객체는 사용하지 않는다. 교체 객체가 commit의 원본 소스로 둔갑하지 않도록 트리와 blob을 교체 해제 상태에서 읽고 출처를 재인증한다. Git이 추적하는 Python 파일명에 UTF-8이 아닌 바이트가 있으면 전체 스캔을 명시적으로 거절한다. 이 파일은 아직 증적 파일명·SQLite 문맥·승인 실행에 일관되게 표현할 수 없으므로 일부만 조용히 분석하지 않는다.

`--frame`은 불변 commit에서 실제 존재하는 물리적 줄을 가장 안쪽 함수·메서드·클래스에 대응시킨다. 범위 밖 줄·파싱되지 않은 파일은 거절한다. 선택된 노드가 바이트 예산으로 제외되어도 `context.frame`에는 대응 노드 ID와 원본 파일 해시를 남기며 `truncated`로 누락을 알린다. 실행 기록 자체의 신뢰성이나 호출의 실제 도달 여부는 검증하지 않는다.

노드 ID는 `file:<path>`, `module:<path>`, `class:<path>:<qualified-name>:<def-line>`, `function:<path>:<qualified-name>:<def-line>` 형식이다. 데코레이터가 있으면 문맥의 줄 범위와 `source_slice`는 첫 데코레이터부터 포함하지만 노드 ID의 줄은 `def`·`class` 선언 줄이다. 문맥에는 거리·정확 심볼 우선 노드별 `source_slice`, 줄 범위·hash, 선택 노드의 edge(`resolved | unknown`), `truncated`, `source_bytes`가 있다. `--node` 검색의 `--hops`는 0~2, 공통 `--limit`은 1~500만 허용한다. API는 `src/modules`을 Python 경로에 추가해 `static_scan.orchestrator.graph`와 `static_scan.retrieval.retrieve`를 사용한다. 연결은 호출자가 닫는다. 대상 코드는 실행하지 않으며 Python 3.14 문법을 완전히 분석하려면 분석기도 Python 3.14여야 한다.

메서드·중첩 함수의 직접 호출은 해당 함수의 `unknown` edge로 보여주지만 대상 함수를 추측해 연결하지 않는다. 조건문·반복문·`try`·`with`·`match` 안의 함수·클래스도 줄 위치와 정의 관계를 기록한다. 분기에 따라 정의되지 않을 수 있으므로 이 이름의 호출은 확정 연결하지 않는다. 와일드카드 import 또는 함수의 `global` 선언이 같은 이름을 바꿀 수 있으면 기존 함수 호출도 `unknown`으로 남긴다. 따라서 보이는 호출과 확정된 그래프 연결은 다르다.

`import pkg.child` 같은 다단계 import는 `pkg.child`뿐 아니라 실제 추적된 `pkg/__init__.py`에도 확정된 의존 간선을 남긴다. 따라서 패키지 초기화 파일만 바뀌어도 해당 import를 사용하는 모듈을 후보 영향 범위에 포함한다. 런타임에 동적으로 선택되는 대상은 계속 `unknown`이다.

문맥을 선택할 때 `--source-byte-budget`은 표시할 소스 조각의 UTF-8 총량을 제한하며 기본값은 24,000바이트다. 원래 줄 범위를 보존하기 위해 큰 조각을 중간에서 자르지 않고 제외하며, 뒤의 작은 이웃은 예산 안에 들면 계속 선택한다. 제외가 있으면 `truncated: true`다. 표시된 `source_bytes`는 출력 전체 크기나 모델의 토큰 수가 아니며, 제외된 심볼이 안전하거나 근거가 없다는 뜻도 아니다.

`--changed-file`과 `--query`는 함께 사용한다. 검색 결과가 없으면 빈 문맥이 반환된다. `--limit`은 1~500이다. 선택하지 않은 소스를 무위험으로 보지 않는다.

`--cache-dir`은 대상 저장소 밖에 둔다. 캐시 파일은 SHA-256으로 우발적 손상을 검사하지만 같은 사용자에 의한 위조를 막는 서명이 아니므로 신뢰할 수 없는 경로를 사용하지 않는다. `--clean-replay`는 동일한 Git SHA에서 캐시 사용 결과와 캐시 없는 전체 **정적 사실**을 비교한다. 불일치하면 깨끗한 결과로 바꾸고 캐시 디렉터리에 비활성 마커를 기록한다. 이후 일반 `--cache-dir` 실행에서도 해당 캐시는 사용하지 않는다. 원인을 조사하기 전에는 마커를 제거하지 않는다. `clean_replay.status`는 `match | mismatch | disabled`이며 그래프·Finding·Report 동등성까지 검증하지 않는다. 캐시와 재생 결과는 표준 출력에만 표시되며 최종 `ScanRun` 감사 증적은 아직 없다.

`--clean-replay`와 `--symbol`·`--frame` 등의 문맥 조회를 함께 쓰면 재검사한 동일 Git blob에서 그래프를 다시 만들고 문맥을 반환한다.
