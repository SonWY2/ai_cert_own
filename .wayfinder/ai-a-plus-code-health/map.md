---
title: "AI A+ 코드 건강검진 시스템 최종 명세 지도"
status: open
label: "wayfinder:map"
ticket_dir: "tickets"
---

## Destination

Python 백엔드 대규모 코드 건강검진 시스템을 개발자가 그대로 구현하고, AI 인증심사 전 항목 A+를 실측으로 입증할 수 있는 최종 명세를 확정한다.
정기 기준 브랜치 점검과 릴리스 후보 점검에서 정책 승인형 동적 검증을 결합해 검증된 위험 우선순위표를 제공한다.

## Notes

- Wayfinder는 계획만 수행한다. 구현·벤치마크·결과보고서 작성은 이 지도의 결정이 모두 닫힌 뒤 별도 실행 계획으로 넘긴다.
- 입력은 Python 코드가 있는 모든 저장소를 받되, 다른 언어의 의미 분석은 하지 않는다. A+ 성과 주장은 검증 자료가 대표하는 Python backend·FastAPI·asyncio 범위로 제한한다.
- 정적 읽기와 그래프 탐색은 자동화한다. import·테스트·벤치마크·프로파일러처럼 코드를 실행하는 단계는 정책 승인을 통과해야 한다.
- 핵심 경로는 독립 기여를 대조 실험으로 입증할 수 있는 기술만 포함한다.
- 최신 기법은 격리된 실험 경로로 폭넓게 조사하되, 승격 전 결과를 기본 KPI나 A+ 달성 수치에 합산하지 않는다.
- 평가 자료는 고정 공개 저장소·숨겨진 합성 결함·개발 cutoff 이후 시간 기반 공개 holdout을 분리한다. 개인 과제이므로 익명 비공개 실제 사례와 다수 전문가 평가는 포함하지 않는다.
- 최소 핵심 범위는 Python 3.14 합성 fixture, FastAPI Users·Prefect runtime 파일럿, Langflow 대규모 정적 확인이다. Langflow runtime과 py-spy·Scalene·Memray·VizTracer는 가설별 관찰 필요성, 재현 workload, 실행 예산, 정책 승인을 통과할 때만 하나씩 추가한다.
- 각 세션은 `wayfinder`, `grilling`, `domain-modeling`을 우선 적용하고, 연구 티켓은 외부 원문과 공식 문서를 우선한다.
- 새 세션이나 context compaction 뒤에는 [`SESSION-RECOVERY.md`](SESSION-RECOVERY.md)의 순서로 지도·동결 manifest·frontier 티켓을 복구한다. 채팅 기록은 결정의 기준이 아니다.
- GitHub 인증이 없어 local-markdown tracker를 사용한다. 티켓 파일의 `blocked_by`가 의존 관계이고, `status: open`, `assignee: null`, 모든 blocker가 closed인 티켓이 frontier다.

## Decisions so far

<!-- 닫힌 티켓의 결정 요약과 링크만 한 줄씩 추가한다. -->

- [대규모 Python 정적·그래프 분석 근거 조사](tickets/005.md) — 얕고 추적 가능한 다층 정적 기준선을 우선하고, 고급 그래프·검색은 독립 기여 검증 뒤 승격한다.
- [Python 동적 검증 도구의 관찰력·왜곡·운영 제약 조사](tickets/006.md) — profiler는 가설별 관찰 차원과 권한·왜곡을 기준으로 하나씩 선택하고, 결과를 benchmark로 오인하지 않는다.
- [AI 코드 진단 최신 기법의 재현 근거 조사](tickets/007.md) — typed graph+lexical 위치화와 실행 유도 진단은 기본 후보, router·critic·calibration·다중 추론은 격리 실험 후보로 분리한다.
- [코드 진단 평가 자료와 검증 방법 근거 조사](tickets/008.md) — 공개·합성 자료를 역할별 층으로 평가하고, 시간·family 오염·불완전 정답·동일 예산 비교를 통제한다.
- [FastAPI·asyncio 평가 저장소 후보 적합성 조사](tickets/024.md) — 공개 파일럿은 Langflow·Prefect·FastAPI Users·FastAPI template을 고정 후보로 삼고, framework 보정과 숨겨진 합성·시간 holdout을 분리한다.
- [현장 입력 명세 동결](tickets/001.md) — 모든 Python 저장소 정적 입력, Python backend 실증, Code Graph·동적 DAG·LLM Judge·두 shadow 실험과 다섯 JSON 근거 객체를 v18 scope로 고정했다.
- [제품 사용자·결정·성공 계약 확정](tickets/002.md) — 사람 평가 대신 80개 paired case에서 plain LLM 대비 20분 내 유효 검증 권고율 +30%p와 Critical/High 부당 기각 절대 0건을 성공 기준으로 고정했다.
- [주장 강도와 증거 판정 원칙 확정](tickets/003.md) — 기술 역할과 증명 상태를 분리하고, 현재 프로젝트 성과는 0건으로 두며, 동일 예산 final holdout 전에는 우월성·A+ 주장을 금지한다.
- [자동 읽기·승인 실행·자료 권한 경계 확정](tickets/004.md) — snapshot 정적 읽기는 자동화하고 실행·모델 전송은 RunManifest 한 번으로 승인하며, 자료는 project data와 harness credential 두 종류만 구분한다.
- [지원 대상과 위험 분류 경계 확정](tickets/009.md) — 모든 Python 저장소를 받되 scan은 수락·거절, finding은 확인·기각·판단 보류만 사용하고 위험 분류는 기존 다섯 관점으로 제한한다.
- [정기 점검과 릴리스 후보 점검의 비교 계약 확정](tickets/010.md) — main은 매주·수동 전체 점검하고 후보는 영향 범위·전체 중 선택하며, 결과는 SHA 기반 다섯 비교 상태로만 표시한다.
- [위험 식별자와 독립 상태축 확정](tickets/011.md) — 위치가 아닌 원인·조건·영향으로 위험을 식별하고, 근거·변화·사용자 행동 세 축만 독립적으로 유지한다.
- [의사결정 가능한 위험 우선순위표 시제품](tickets/012.md) — stable finding 한 행과 다섯 정보만 보여주고, 심각도 우선 tuple과 다음 행동 하나로 20분 의사결정을 지원한다.
- [최소 정적 분석·문맥 기준선 선택](tickets/013.md) — AST·symbol·SQLite Code Graph를 기본으로 두고, 함수 단위 CFG·def-use만 제한된 실험으로 추가해 동일 예산 독립 기여를 검증한다.
- [승인형 동적 검증 정책 시제품](tickets/014.md) — RunManifest를 한 번 승인하면 정확성·동시성·성능별 DAG가 test와 profiler를 조건부 자동 실행하며, 성능은 무계측 workload 재현 뒤 cProfile을 사용한다.
- [기본 경로와 독립 기여 비교 명세 선택](tickets/015.md) — 일반 LLM부터 runtime DAG까지 여섯 누적 arm을 같은 예산으로 비교하고, 5%p 품질 또는 품질 유지 10% 비용 효과가 없는 구성은 core에서 제거한다.
- [평가 자료·정답셋·오염 통제 계약 선택](tickets/016.md) — 공개 파일럿은 개발에만 쓰고 숨긴 합성·시간 holdout만 최종 수치에 사용하며, 실행 oracle 우선·독립 LLM Judge 보조 판정을 고정한다.
- [핵심 평가 지표와 주장 범위 선택](tickets/017.md) — 80개 case에서 plain LLM과 full system을 paired 평가하고, +30%p·CI 하한·중요 위험 0건을 통과해야 하며 사람 생산성 주장은 금지한다.
- [기본 경로와 실험 경로의 격리·승격 계약 확정](tickets/018.md) — 실험 결과는 별도 shadow 산출물로만 보관하고, 같은 예산 효과·안전·재현성을 통과한 다음 manifest에서만 core로 승격한다.
- [최신 실험 후보의 제한된 목록 선택](tickets/019.md) — 함수 단위 CFG·def-use와 Critical/High 근거 반증 critic만 shadow 실험하며, 새 후보는 기존 하나를 제거해야 추가할 수 있다.
- [근거 객체와 전체 추적성 계약 선택](tickets/020.md) — ScanRun·Evidence·Finding·Report·UserAction 다섯 JSON 객체만 사용하고 report에서 source·명령·artifact까지 hash로 재현한다.

## Not yet specified

- 파일럿 실측 후 고정할 scan 시간·메모리 예산과 최소 보고서 생성 전 예산 초과 거절 기준
- 모델 공급자·context 크기·가격·CI hardware에 따른 모델 및 same-budget 회계 방식
- live demo, frozen artifact 재현, 제한 열람 중 심사에서 수용되는 최종 증적 제출 형식

## Out of scope

- Wayfinder 단계에서 source·test·profiler harness·scheduler·UI를 구현하거나 benchmark를 실제 수행하는 일
- 자동 코드·테스트 수정, patch·PR 생성·적용, merge·배포 수행
- 사용자 승인 없는 test·benchmark·profiler 실행 또는 production process attach
- Python 백엔드 밖의 범용 다중 언어 분석과 APM·보안 scanner·CI/CD 전체 대체
- Ruff·type checker·test runner·profiler·graph database·issue tracker 자체 재구현
- 모든 모델·그래프·에이전트·profiler 조합의 무차별 비교와 독립 기여에 불필요한 일반 인프라 상세 설계
- 승격 전 실험 기능 결과를 기본 우선순위표·핵심 KPI·A+ 달성 수치에 합산하는 일
- 외부 논문·vendor 수치 또는 현재 설계 문서를 프로젝트 동작 성과 증거로 대체하는 일
- 시스템이 독자적으로 위험을 수용하거나 release·deployment를 자동 승인·차단하는 일
- 익명 비공개 실제 사례와 기업 비공개 저장소 일반화 — 개인 과제에 적법한 사례 custodian과 독립 전문가 패널이 없어 공개·합성 검증으로 범위를 다시 고정했다.
- GPU 기반 LLM serving·vLLM 성능 lane과 FastAPI·Starlette 자체 점수 — 핵심 코드 진단 가치보다 환경과 검증 부담이 커 복잡성 감사에서 제거했다.
