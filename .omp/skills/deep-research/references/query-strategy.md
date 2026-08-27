# 질의 전략

## 1. 의도와 최신성 분류

먼저 질문을 factual, explainer, comparison, recommendation, landscape 중 하나 이상으로 분류한다. 실제 의사결정·대상 범위·확인 가능한 가설을 정한다.

`latest`, `recent`, `today`, `currently`, `new`, `state of the art`, 연도, `요즘`, `최신`, `최근`, `현재` 또는 내용상 빠르게 변하는 주제는 freshness-sensitive다. 세션의 현재 날짜를 기준으로 다음을 적용한다.

- 최신성 수준이 오늘·이번 주·이번 달이면 날짜 단위·주 단위·월 단위 질의와 `recency`를 함께 쓴다.
- 연간 최신성이면 현재 연도와 현재 월을 질의에 넣는다. 예: `agent memory August 2026`, `agent memory 2026`.
- 결과의 실제 publication/update date를 읽어 확인한다. event date와 게시일은 별도 기록한다.
- 최신성 질문의 상위 결과가 대부분 과거 연도라면 현재 연도·월, 공식 사이트, GitHub release/update, 최신 논문, 대체 용어로 질의를 다시 만든다.
- 최신 문서가 없으면 “최신 확인 가능한 근거는 YYYY-MM-DD까지”라고 한계를 적는다.

## 2. 각도와 질의군

질문을 겹치지 않는 3–5개 조사 각도로 나눈다. 필요할 때 시간 흐름, 현재 상태, 이해관계자, 정량/정성, 비교, 위험, 대안 관점을 포함한다.

각도마다 같은 표현을 반복하지 말고 아래 중 필요한 질의군을 선택한다.

- Broad: 주제의 범위와 용어 찾기
- Primary / Official: 원출처, 공식 문서, release, 규제 문서
- Recent: 현재 연도·월·기간
- Implementation: 실제 repository, documentation, release, commit
- Academic: 논문, benchmark, 재현
- Comparison / Alternative terminology: 비교 대상과 다른 이름
- Criticism / Failure / Contradiction: 한계, 실패, 반대 증거

처음에는 넓게 용어·관점을 탐색하고, 다음에는 핵심 하위 주제와 공백을 깊게 조사한다. 한 번의 검색으로 충분하다고 가정하지 않는다.

## 3. 반복과 종료

각 검색 라운드 뒤에 다음 공백을 확인한다.

- 핵심 주장을 뒷받침하거나 반박할 독립 근거가 부족한가?
- 최신성이 부족하거나 날짜가 모호한가?
- 공식·구현·학술·실사용 중 질문에 맞는 출처 유형이 빠졌는가?
- 대체 용어, 반대 관점, 실패 사례가 빠졌는가?

공백 하나마다 그 공백만 겨냥하는 새 질의를 만든다. 단순 동의 자료를 더 찾지 않는다. 추가 라운드가 새 독립 근거를 거의 더하지 못하면 종료하고 부족한 근거를 표시한다.
