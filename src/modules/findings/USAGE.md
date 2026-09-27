# 임시 위험 가설 판정

`src`를 Python 경로에 추가한 뒤:
```python
from modules.findings import admit, compare, priority_rows

candidates = [{
    "root_symbol": "pkg.worker.run", "mechanism": "shared counter is updated without a lock",
    "condition": "two workers update the same instance", "impact": "updates may be lost",
    "trigger": "concurrent requests on one instance", "taxonomy": "concurrency",
    "severity": "High", "location": {"path": "pkg/worker.py", "line": 42},
    "evidence_ids": [source_evidence_id], "perspective": "reviewer A",
    "next_action": {"action": "run concurrent updates on a shared instance",
                    "oracle": "compare final count to the number of successful updates",
                    "time_minutes": 8},
}]
findings = admit(bundle_path, candidates, previous=previous_findings)
changes = compare(previous_findings, findings, complete=False)
rows = priority_rows(findings, actions={findings[0]["id"]: "verify"})
```

`bundle_path`는 검증 가능한 source 단계 `run.json`·`evidence.jsonl` 디렉터리다. Python API `admit`은 저장 기록의 자체 연결·위치 경로를 확인하고, 두 CLI는 추가로 실제 Git commit의 전체 일반 Python 파일·blob 해시를 확인한다. 다음 행동은 `action`, 반증 가능한 `oracle`, 양의 정수 `time_minutes`가 필요하다. 같은 원인·조건·영향의 관점별 주장을 한 위험으로 병합하지만 모두 `deferred`다. 실제 실패와 영향 심각도는 독립적으로 확인하지 않는다.

`compare(base, target, complete=False)`는 같은 ID라도 정체성이 바뀌면 `unknown`이다. 누락 위험은 완전한 범위일 때만 `resolved`로 표시한다. `priority_rows(findings, changes={}, actions={})`는 심각도→변화→근거→예상 검증 시간→ID로 정렬하고 네 가지 사용자 행동(`verify | fix | accept_risk | dismiss`) 또는 `null`만 받는다. `src/review_hypotheses.py SOURCE_BUNDLE CANDIDATES_JSON`은 외부 제공 가설의 위치·줄 범위를 해당 commit의 Git blob에 대조하고, `location_proofs`에 물리적 소스 조각의 SHA-256을 넣어 임시 표를 출력한다. 줄이 실제 존재한다는 증거일 뿐 가설의 참 여부는 입증하지 않는다. 최종 진단 보고서가 아니다.

```sh
python3 src/review_hypotheses.py SOURCE_BUNDLE CANDIDATES_JSON
python3 src/record_action.py SOURCE_BUNDLE CANDIDATES_JSON /private/outside/repository/actions FINDING_ID verify
python3 src/review_hypotheses.py SOURCE_BUNDLE CANDIDATES_JSON --actions /private/outside/repository/actions
python3 src/review_hypotheses.py SOURCE_BUNDLE CANDIDATES_JSON --main-ref main --candidate-ref candidate --scope impact
mkdir -m 700 /private/outside/repository/reviews
python3 src/review_hypotheses.py SOURCE_BUNDLE CANDIDATES_JSON --save-snapshot /private/outside/repository/reviews/first.json
python3 src/review_hypotheses.py NEW_SOURCE_BUNDLE NEW_CANDIDATES_JSON --previous /private/outside/repository/reviews/first.json --previous-bundle SOURCE_BUNDLE
python3 src/record_action.py NEW_SOURCE_BUNDLE NEW_CANDIDATES_JSON /private/outside/repository/actions FINDING_ID verify --previous /private/outside/repository/reviews/first.json --previous-bundle SOURCE_BUNDLE
```

행동 기록 디렉터리는 사용자가 미리 `0700` 권한으로 만들고 저장소 밖에 둔다. `record_action.py`는 대화형 터미널에서 위험 ID와 행동을 다시 입력받는다. 선택지는 `verify | fix | accept_risk | dismiss`; 실행 전에는 `null`이다. 기록은 동일 source 점검 ID별 owner-only 추가 전용 JSONL에 해시와 시각을 남긴다. 최신 선택만 위험표에 보이며 과거 기록을 덮어쓰지 않는다. 기록은 위험의 근거 상태를 `confirmed`로 바꾸거나 테스트·수정을 실행하지 않는다. 이전 위험과 비교할 때 두 명령 모두 `--previous`와 원래 점검의 `--previous-bundle`을 함께 전달한다.

`--save-snapshot`은 기존 파일을 덮어쓰지 않고 저장소·source 묶음 밖의 `0700` 디렉터리에 임시 위험을 `0600` 파일로 기록한다. 다음 점검은 이전 묶음을 실제 Git commit과 대조하고 저장된 해시·위험 ID·위치를 재검사한다. FIFO 같은 특수 파일은 읽지 않는다. 자체 해시는 제3자의 서명이나 무단 수정 방지 수단이 아니다. `--scope full`도 가설 수집의 완전성을 증명하지 않아 사라진 위험은 자동으로 해결 처리하지 않는다.

후보 점검 시 `--main-ref`와 `--candidate-ref`를 주면 Git에서 계획을 다시 계산해 해당 commit SHA와 일치하는 경우에만 관찰 파일의 가설을 받는다. `--previous`는 후보 점검에서는 main·후보의 merge-base SHA와 일치해야 한다. 정기 main 점검에서는 사용자가 전달한 이전 결과의 SHA를 비교 기준으로 사용하며, 실제로 직전 승인 점검인지는 확인하지 못한다. 모드 지정 없이 비교할 때도 이전 commit이 대상의 조상이어야 한다. 정기 main에서 동일 SHA의 이전 결과를 지정하면 중복 점검을 거절한다. 선택되지 않은 대상 파일과 삭제 파일은 `scope.omitted_unknown_paths`로 표시하고, 기존 위험을 `resolved`로 추측하지 않는다. `--scope full`이어도 가설 수집이나 미해결 그래프 경계가 완전하다는 뜻은 아니다. 저장된 행동을 다시 보려면 조회 시 기록할 때와 같은 점검 범위 옵션을 사용한다.
