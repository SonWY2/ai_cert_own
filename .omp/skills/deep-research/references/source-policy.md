# 출처 정책

## 원문과 출처 유형

검색 결과의 제목·순위·snippet은 후보를 찾는 신호일 뿐 최종 근거가 아니다. 중요한 주장에 연결된 URL은 `read`로 본문을 확인하고, 확인한 문구만 근거로 쓴다.

가능하면 2차 자료에서 원출처로 승격한다.

```text
블로그 → 공식 발표
뉴스 → 회사 IR / SEC / 정부기관 / 원 논문
논문 소개 → 원 논문
GitHub 소개 → 실제 repository / release / commit / documentation
```

다만 “정확한 release date”에는 공식 자료, “실사용자가 좋아하는가”에는 issue·커뮤니티·리뷰, “benchmark가 개선됐는가”에는 논문·benchmark·재현 결과처럼 질문에 맞는 유형을 우선한다.

## 독립성

서로 다른 URL·도메인·검색엔진 순위는 자동으로 독립 근거가 아니다. 원출처 계보를 추적한다.

```text
회사 보도자료 ─ source A
Reuters 원문 ─── source B
  ├─ Yahoo 재게시
  ├─ MSN 재게시
  └─ 블로그 인용
```

위 예시는 실질적으로 A와 B 두 계보다. 보도자료 복사 기사, syndication, 같은 논문을 요약한 글, 같은 회사 발표를 재인용한 기사, 같은 upstream API 데이터는 한 계보로 묶는다.

여러 공개 검색엔진에 동일 URL이 나타나는 것은 `discovery confidence`를 높일 수 있다. `evidence confidence` 또는 독립 source 수를 높이지 않는다.

## 최소 평가 기준

핵심 출처마다 다음을 낮음·중간·높음 또는 짧은 문장으로 판단한다.

- **Authority**: 해당 주장을 말할 권한과 전문성
- **Recency**: 질문의 시간 범위에 맞는가
- **Directness**: 주장 자체를 직접 뒷받침하는가
- **Independence**: 다른 근거의 재인용·복제인가

중요 주장에는 가능한 한 1차 출처를 하나 이상 포함한다. 원문을 읽지 못했거나 원출처를 확인할 수 없으면 그 한계를 표시한다.
