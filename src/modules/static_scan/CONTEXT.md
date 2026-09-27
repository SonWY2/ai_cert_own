# Module Context: static_scan

불변 Git commit에서 추적 중인 Python 일반 파일만 읽는다. 대상 코드를 import하거나 실행하지 않는다. symlink와 추적되지 않은 작업 파일은 제외한다.

`orchestrator.scan(repo, revision, cache=None)`은 `commit`, `python_parser`, `files` JSON 계약을 유지한다. 선택적 `FactsCache`는 Git blob을 매번 해시로 확인하고 저장소·경로·분석기 버전별 AST·symtable 사실만 재사용한다. `graph(repo, revision, cache=None)`은 해당 스캔 결과와 새 메모리 SQLite 연결을 반환한다. 그래프 연결·문맥은 매번 재계산한다. SQLite에는 file/module/class/function 노드와 source text, `defines/imports/calls/inherits` edge가 있다. 노드에는 source hash·Git blob OID·줄 범위를 남긴다. edge는 `resolved`와 `unknown`을 구별하며 해석하지 못한 참조는 target 없이 reference만 기록한다.

`context(db, node_id, hops=1, limit=50, source_byte_budget=24000)`은 양방향 최대 2-hop을 거리·ID순으로 탐색한다. 노드에는 동결된 blob의 source slice·줄 범위·hash를 제공하며, 바이트 예산을 넘는 조각은 통째로 제외하고 `truncated`로 표시한다. 같은 파일의 확실한 최상위 정의만 call/inherit 대상으로 확정한다. 최상위 함수와 이미 노드로 추출한 메서드·중첩 함수의 직접 호출을 각각 해당 함수에 귀속한다. 메서드·중첩 함수의 호출 대상은 확정하지 않고 `unknown` edge로 남긴다. 이 호출은 그래프 이웃으로 탐색하지 않는다. `if`·`try` 안에서 새로 정의한 함수나 람다·컴프리헨션의 호출은 수집하지 않으므로 그래프에 없다는 이유로 안전하다고 판단할 수 없다. 메모리 SQLite는 명령 종료 시 사라지며 진단 결과가 아니다.

`retrieval.retrieve`는 Git에 고정된 Python 파일의 물리적 프레임 줄·정확 심볼을 검색 기준으로 사용한다. 프레임은 가장 안쪽의 선언 노드, 없으면 모듈에 대응하고 파싱되지 않은 파일·없는 줄을 거절한다. 이후 변경 파일의 문자열 일치와 해석된 1·2-hop 이웃을 선택한다. 범위와 정렬은 결정론적이며 `unknown` edge는 근거로 표시하되 탐색하지 않는다. 동일한 소스 조각 바이트 예산을 적용한다. source text는 Git blob에서 구성한 SQLite만 사용한다. 전체 출력 바이트나 모델 토큰을 제한하지 않으며 외부 실행 기록의 진위는 판단하지 않는다.

[`../../scan_sources.py`](../../scan_sources.py)는 정적 읽기와 그래프 문맥을 출처 근거 저장에 연결한다. 대상 코드 import·실행이나 대상 작업트리 쓰기는 하지 않는다. 외부 가설의 임시 위험표는 별도 구현했지만 고정 다섯 관점의 AI 진단, 승인형 동적 검증, 확인된 위험 보고서는 아직 구현되지 않았다.
