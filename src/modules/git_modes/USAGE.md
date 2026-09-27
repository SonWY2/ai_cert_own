# Git 점검 범위

```sh
python3 src/plan_scan.py /path/to/repo main main --previous-accepted-sha <commit-sha>
python3 src/plan_scan.py /path/to/repo candidate main <candidate-ref> --scope impact
python3 src/plan_scan.py /path/to/repo candidate main <candidate-ref> --scope full
```

Python API는 `src`를 `PYTHONPATH`에 추가한 뒤 `from modules.git_modes import plan_main, plan_candidate`로 사용한다. `plan_main(repo, main_ref, previous_accepted_sha=None)` 및 `plan_candidate(repo, main_ref, candidate_ref, scope=\"impact\")`가 base/target SHA, 대상 Python 경로, 미관측 경로와 범위 설명을 반환한다. 후보 CLI는 범위를 명시해야 한다.

`impact` 결과는 일부 소스만 선택한 계획이다. 선택 밖의 위험은 해소된 것으로 판정하지 않는다. 이 명령은 대상 코드를 실행하거나 근거 파일을 만들지 않는다.

`review_hypotheses.py SOURCE_BUNDLE CANDIDATES_JSON --main-ref main --candidate-ref candidate --scope impact`는 실제 Git 계획을 다시 계산하고 해당 commit의 source 기록과 SHA를 맞춘다. 변경 Python 파일 및 해석된 역방향 의존 파일만 현재 관찰 대상으로 받는다. 선택되지 않은 대상 파일·삭제된 파일은 `scope.omitted_unknown_paths`에 표시하며 안전하거나 해소된 위험으로 판단하지 않는다. `--scope full`은 현재 commit의 모든 일반 Python 파일을 선택하지만 모든 결함을 확인했다는 뜻은 아니다. 선택을 기록하는 `record_action.py`에도 같은 `--main-ref`, `--candidate-ref`, `--scope` 값을 넘긴다.
