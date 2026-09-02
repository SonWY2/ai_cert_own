# Wayfinder 새 세션 복구 절차

이 파일은 결정 내용을 복제하지 않는다. 새 세션·컨텍스트 압축 이후 어떤 파일을 어떤 순서로 읽어야 하는지만 고정한다.

## 반드시 읽는 순서

1. [`map.md`](map.md)를 한 번 읽어 Destination, Notes, Decisions so far, Not yet specified, Out of scope를 복구한다.
2. [`field-input-manifest.yaml`](field-input-manifest.yaml)에서 현재 동결된 지원 범위, 저장소 역할, 실행 환경, 동적 도구 정책, 주장 경계를 복구한다.
3. `tickets/`에서 `status: open`, `assignee: null`, 모든 `blocked_by`가 `closed`인 첫 티켓을 frontier로 선택한다.
4. 선택한 티켓을 먼저 `assignee`로 선점한 뒤 질문 본문과 관련된 닫힌 티켓·연구 자산만 읽는다.
5. 채팅 기록이나 장기 기억에서 결정을 재구성하지 않는다. 충돌하면 저장소 파일이 기준이다.

## 파일별 책임

- [`map.md`](map.md): 유일한 Wayfinder 지도. 도착점·범위·닫힌 결정의 한 줄 색인만 보관한다.
- `tickets/*.md`: 의사결정 질문과 상세 resolution의 유일한 저장 위치다.
- [`field-input-manifest.yaml`](field-input-manifest.yaml): 현재 적용되는 기계 판독 가능한 범위와 실행 조건이다.
- `research/*.md`: 외부 사실과 후보 근거다. 프로젝트 결정이나 성과 증적을 대신하지 않는다.

## 티켓 해결 시 필수 기록

응답을 끝내기 전에 다음을 같은 작업에서 모두 반영한다.

1. 티켓에 resolution comment를 기록하고 `status: closed`로 변경한다.
2. 지도 `Decisions so far`에 티켓 링크와 한 줄 요약을 추가한다.
3. 결정이 범위·저장소·도구·평가 조건을 바꾸면 `field-input-manifest.yaml`의 schema version을 올리고 관련 닫힌 티켓의 오래된 문구를 정합화한다.
4. 새 질문이 선명해졌으면 새 티켓을 만든 뒤 두 번째 단계에서 `blocked_by`를 연결한다.
5. 범위 밖이 된 항목은 지도 `Out of scope`에 이유와 함께 기록한다.
6. 파일 구문, 링크, 티켓 상태, frontier를 실제 파일에서 다시 확인한다.

## 금지

- 채팅 요약만 남기고 파일 갱신을 생략하지 않는다.
- 같은 결정을 지도·별도 요약 문서·여러 티켓에 중복 서술하지 않는다.
- 연구 후보를 채택 결정이나 프로젝트 성과처럼 기록하지 않는다.
- 새 세션에서 모든 티켓과 연구 자산을 무차별로 읽지 않는다.
