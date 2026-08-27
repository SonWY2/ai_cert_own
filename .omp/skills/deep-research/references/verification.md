# 근거 검증과 결론

## Evidence Ledger와 confidence

핵심 주장별로 최소한 다음을 내부적으로 대조한다.

| 항목 | 확인 내용 |
| --- | --- |
| Claim | 검증하려는 원자적 주장 |
| Source | URL, 발행자, 출처 계보 |
| Date | publication/update date와 event date |
| Source type | 공식, 논문, 구현, 독립 보도, 실사용 신호 등 |
| Primary | 1차 또는 2차 |
| Quality | Authority, Recency, Directness, Independence |
| Direction | 지지 또는 반박 |
| Confidence | High, Medium, Low와 이유 |

일반 factual claim은 가능한 한 독립 출처 2개 이상을 목표로 한다. 중요한 핵심 claim은 가능한 한 독립 계보 3개 이상, 출처 유형 2개 이상, 1차 출처 1개 이상, 반대 검색 수행을 목표로 한다. 숫자를 채우려고 서로 종속된 자료를 독립 근거로 세지 않는다.

근거가 목표보다 부족하면 Low confidence 또는 Evidence insufficient다. 빈 검색·접근 불가 원문은 근거가 아니다. 수치 점수나 가중치를 만들어 confidence를 과장하지 않는다.

## 필수 반대 검색

예비 근거를 모은 뒤 각 핵심 가설에 대해 최소 한 번 적극적으로 반대 검색한다.

- `limitations`, `failure`, `benchmark problems`, `production problems`, `unnecessary`
- 경쟁 접근이 더 낫다는 비교
- 반대되는 결과, 재현 실패, 반론

반대 증거는 삭제하거나 각주로 숨기지 않는다. 가설을 지지, 반박, 혼합, 판단 불가 중 하나로 조정하고 핵심 결론에 반영한다.

## 종료 조건

다음을 모두 확인하면 종합한다.

1. 질문의 주요 각도와 최신성 요구를 다뤘다.
2. 중요한 출처는 원문을 읽었고 snippet만 근거로 쓰지 않았다.
3. 핵심 주장마다 출처 계보와 독립성을 확인했다.
4. 반대 검색을 수행했고 발견한 반론을 반영했다.
5. 남은 공백을 명시했다.
6. 추가 질의가 새 독립 근거를 거의 늘리지 않는다.

## 최종 답변

1. **핵심 결론** — 결론과 claim별 confidence.
2. **조사에서 확인된 주요 사실** — 주장별로 날짜·범위를 포함.
3. **근거와 출처** — 원문 URL, 출처 유형, 직접 뒷받침하는 내용.
4. **반대 근거 / 논쟁점** — 결론을 제한하거나 반박하는 근거.
5. **불확실한 부분** — 독립 검증 실패, 최신성 한계, 접근 제한.
6. **최종 confidence** — High / Medium / Low와 근거 수준.
