---
name: deep-research
description: 최신성·출처 독립성·반대 근거가 중요한 질문을 심층 조사할 때 사용한다. 단순 검색 요약 대신 여러 관점, 원문 확인, 근거 검증을 거친 결론이 필요할 때 적용한다.
---

# OMP Deep Research

## 적용 기준

다음 요청에는 이 Skill을 적용한다.

- “심층 조사”, “깊게 조사”, “찬반 근거”, “최신 동향”, “정확히 검증”처럼 근거 수준이 중요한 질문
- 비교·추천·기술 동향·시장 주장처럼 한 번의 검색으로 결론내리면 위험한 질문

단순 사실 확인은 필요한 원문만 읽고 짧게 답한다.

## 시작 전

1. `references/query-strategy.md`를 읽고 질문의 의도·최신성·조사 각도·질의군을 정한다.
2. `references/source-policy.md`를 읽고 출처를 평가하고 원출처를 추적한다.
3. `references/verification.md`를 읽고 근거 장부·반대 근거·종료 조건·결론 형식을 적용한다.
4. 출처 접근이 막히면 `references/access-fallback.md`를 읽고 공개 원출처 또는 독립 원문으로만 대체한다.

검색은 구성된 OMP `web_search`만 사용한다. 이 workspace에서는 `public`이 우선이며, 별도 검색 API·키·크롤러·MCP를 추가하거나 사용하지 않는다. `web_search` 결과의 snippet은 후보 발견용이며 근거가 아니다. 중요한 출처는 반드시 `read`로 원문을 확인한다.

검색이 실패하거나 `references/access-fallback.md`에도 공개 원문이 없으면 조사 결과를 지식·추측으로 보완하지 않는다. 실패한 제공자와 확인하지 못한 공백을 보고하고, 로그인·유료벽·CAPTCHA·TLS 위장·프록시·자동 의존성 설치로 우회하지 않는다. 확인하지 않은 URL·인용·성능 수치를 만들지 않는다.

## 조사 상태

다음 상태를 건너뛰지 않는다.

```text
User Question
→ Research Intent Classification
→ Freshness Requirement
→ Question Decomposition
→ 3–5 Research Angles
→ Query Families
→ OMP public search
→ Candidate Sources
→ Primary Source Promotion
→ Important Sources Full Read
→ Evidence Ledger
→ Contradiction Search
→ Gap Analysis
   ├─ evidence 부족 → 새로운 query 생성 → OMP public search로 반복
→ Confidence Assignment
→ Synthesis
```

## 핵심 실행 규칙

- 질문이 실제로 결정하려는 대상과 2–4개의 반증 가능한 가설을 먼저 적는다. 가설은 지지·반박·혼합·판단 불가 중 하나로 끝낸다.
- 질문을 서로 겹치지 않는 3–5개 조사 각도로 나눈다. 각도마다 다른 종류의 질의와 출처를 사용한다.
- 최신성이 필요하면 현재 날짜와 실제 게시·수정일을 구분한다. 오래된 결과가 치우치면 날짜·공식 출처·구현·대체 용어를 바꿔 재검색한다.
- 중요한 주장마다 내부 Evidence Ledger를 유지한다. Claim, URL/출처, 게시·수정일, 출처 유형, 1차/2차, Authority, Recency, Directness, Independence, 지지/반박, confidence를 기록한다.
- 검색엔진 여러 곳에 같은 URL이 나온 것은 발견 신뢰도만 높인다. 독립 근거 수로 계산하지 않는다.
- 주요 결론 전에는 반드시 “이 주장이 왜 틀릴 수 있는가?”를 겨냥한 반대 검색을 최소 한 번 수행한다. 불리한 근거도 결론에 반영한다.
- 반복 검색은 근거 공백을 메우는 경우에만 한다. 새 독립 근거가 거의 늘지 않으면 멈추고 부족함을 명시한다.
- 충분한 근거가 없으면 추정으로 채우지 않는다. `Low confidence`, `Evidence insufficient`, `Unable to verify independently`를 사용한다.

## 결과 형식

기본 응답은 아래 순서로 작성한다.

1. 핵심 결론
2. 조사에서 확인된 주요 사실
3. 근거와 출처
4. 반대 근거 / 논쟁점
5. 불확실한 부분
6. 최종 confidence

각 핵심 주장에는 High, Medium, Low 중 confidence를 붙인다. 최신 조사에서는 event date와 publication/update date를 명확히 구분한다.
