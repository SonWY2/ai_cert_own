# 출처 근거 저장

`src`를 `PYTHONPATH`에 추가한 뒤:

```python
from pathlib import Path
from modules.static_scan.orchestrator import scan
from modules.evidence.provenance import write_source_run
from modules.evidence.authenticity import verify_git_source

result = scan(Path("/path/to/repo"), "HEAD")
bundle = write_source_run(Path("/path/to/output"), "/path/to/repo", result)
records = verify_git_source(bundle)
```

작성기는 `output/runs/<run-id>/run.json`과 `evidence.jsonl`을 만든다. 같은 입력의 재실행은 기존 바이트를 보존하고, 다른 바이트의 덮어쓰기는 거절한다. `verify_source_run`은 저장 기록의 해시와 연결만 확인한다. `verify_git_source`는 저장소의 해당 불변 commit에서 정규 Python blob 목록·OID·바이트 해시가 일치하는지도 확인한다. 저장소와 Git 객체에 접근할 수 없으면 거절한다. Python symlink는 애초 스캔 대상이 아니며 Git 내용 일치는 결함 입증이 아니다. 이 기록은 `stage: source_scanned`인 중간 산출물이며 최종 `ScanRun`·위험 진단 결과가 아니다.

## 출처 전용 최종 보고서

```python
from modules.findings.admission import admit
from modules.evidence.final_bundle import write_final_bundle, verify_final_bundle

# candidates: 출처 evidence ID·위치·반증 가능한 next_action을 갖춘 가설 목록
findings = admit(bundle, candidates)
final_dir = write_final_bundle(bundle, findings, Path("/private/output"))
verified_final = verify_final_bundle(final_dir, bundle)
report = verified_final["report"]
```

CLI로 기존 임시 진단을 봉인하려면 `python3 src/review_hypotheses.py SOURCE_BUNDLE candidates.json > review.json` 뒤 `python3 src/seal_report.py SOURCE_BUNDLE review.json /private/output`을 실행한다. 모델 호출 기록이 포함된 경우 동일한 RunManifest를 `--run-manifest manifest.json`으로 전달한다. 두 경우 모두 출처 전용 판단 보류 보고서이며 실행 확인으로 승격하지 않는다.

`diagnose_approved.py --symbol ... --final-output`의 보고서는 `selected_symbol_only` 범위로 봉인된다. 같은 임시 검토를 `seal_report.py`로 다시 봉인할 때도 선택 심볼·Git 그래프 문맥 노드·근거 줄 범위가 일치해야 하며, 전체 저장소 진단으로 바꾸지 않는다.

`/private/output/runs/<analysis-id>/`에 `run.json`(ScanRun), `evidence.jsonl`(Evidence), `findings.jsonl`(Finding), `report.json`(Report), `actions.jsonl`(UserAction)을 만든다. analysis ID는 출처 실행 ID·선언된 manifest 해시·정규화된 가설 및 사용자 행동 이력 해시에 묶인다. 행동 기록이 없으면 `actions.jsonl`은 빈 파일이다. 동일 입력의 재작성은 기존 바이트를 보존하며 기존 파일 변경은 거절한다. 검증기는 해당 Git commit의 전체 추적 Python blob과 근거 ID·SHA-256·위치 해시·Finding→Evidence→ScanRun→출처 연결 및 정렬된 우선순위 보고서를 다시 확인한다.

신규 최종 묶음은 `evidence-contract-v2`이며 버전이 analysis ID에 포함된다. 출처 스캔 묶음은 기존 v1 그대로다. 다섯 JSON 객체를 늘리지 않고 `run.model_audit`에 원래 후보 행·순번·SHA·접수/미검증·이유·finding ID를 봉인한다. `report`에는 `candidate_counts`와 `analysis_status`를 추가한다. 과거 v1 최종 묶음은 보존한 구검증기로 확인하며 자동 승격하지 않는다.

v29에서는 최종 JSON 형식이 계속 `evidence-contract-v2`다. 달라진 것은 모델 승인 계약 `run-manifest-v3`와 **역할별 실제 지시문 집합 해시**의 검증이다. 구 v2 승인의 봉인물을 현행 검증기로 소급 재검증하지 않는다. 보존한 v28 검증기와 기존 원자료를 오프라인에서 사용한다. 같은 기본 다섯 역할은 boundary 모드에서도 동일 지시문을 받으며, 추가 역할의 비용·실패는 별도 기록한다.

P2의 `run.model_audit[*].review`는 Git/AST에서 추출한 항목 ID, 실제 전달된 항목 ID, 누락 이유·수·응답 후보의 **문법적 줄 위치** 대응을 추가로 봉인한다. 현행 검증기는 해당 Git 문맥에서 목록을 재계산한다. 항목이 없거나 잘린 경우를 검토 완료로 취급하지 않는다. 분기·가드·종료 위치는 정적 문법 정보일 뿐 도달 가능성·원인·오탐 제거의 증거가 아니다. `generic` 여섯째 역할도 각 역할의 원문·토큰·실패를 따로 기록하며 여섯 호출 전체를 같은 예산으로 계산한다. 과거 원문 모드의 감사 필드·묶음 버전은 바꾸지 않는다.

사용자 결정은 별도 소유자 전용 디렉터리(`chmod 700 /private/actions`)에 `python3 src/record_final_action.py SOURCE_BUNDLE FINAL_BUNDLE /private/actions FINDING_ID verify`로 남긴다. 실제 단말에서 위험 ID와 행동을 다시 입력해야 한다. 뒤이어 `python3 src/seal_report.py SOURCE_BUNDLE review.json /private/output --actions /private/actions`를 실행하면 검증한 행동 이력을 별도 ID의 새 불변 묶음에 봉인한다. 처음 만든 보고서와 `actions.jsonl`은 바꾸지 않는다. 별도 로컬 행동 로그는 제3자 서명이 아니며 `verify` 선택은 실행 검증 성공이나 결함 확증이 아니다.

`manifest=`에는 선택적으로 유효한 RunManifest 선언을 넣을 수 있으나, 해시를 기록하는 일은 승인·실행 증명이 아니다. 출처 코드만으로 결함·검사 완전성·실행 결과를 확인할 수 없어 모든 Finding은 `source_only`/`deferred`, 변경 상태는 `unknown`, runtime·oracle은 `not_observed`다. 독립 실행 증거·승인·oracle을 검증할 계약이 아직 없어 `runtime_records=`는 빈 목록까지 모두 거절한다. 임의 pstats·모델 출력을 근거로 `confirmed`를 만들지 않으며 사용자 행동은 결함 사실과 독립적으로만 봉인한다.

승인된 five/boundary CLI의 `audit`는 `write_final_bundle(bundle, findings, output_root, manifest=approved_manifest, model_audit=audit)`로 전달한다. 승인된 역할 순서·Git 문맥을 재구성하고 원래 후보 행의 SHA·접수 결과·Finding 연결을 대조한다. 호출이 완료돼도 미검증 행은 남을 수 있으며 이때 보고서는 불완전, CLI는 종료 3이다. single/plain의 최종 봉인은 허용하지 않는다. 정규화된 응답 **전체** 파일은 봉인 밖의 소유자 전용 경로에 둔다. `modules.diagnosis.model.verify_responses(references, audit)`는 실제 파일 권한·해시·후보 순번·사용량을 별도로 검사한다. 봉인만으로 외부 원자료·실제 모델 호출·승인을 증명하지 않으며 `model_provenance: caller_declared_unattested`와 `source_only/deferred`를 유지한다.

## 신뢰한 기존 cProfile 파일 요약

```sh
python3 src/summarize_profile.py /path/to/source-bundle /path/to/manifest.json profile /trusted/output/profile.pstats --trusted-local-artifact
python3 src/summarize_profile.py /path/to/source-bundle /path/to/manifest.json profile /trusted/output/profile.pstats --trusted-local-artifact --hotspot-index 0
```

```python
from modules.evidence.profile import normalize_trusted_pstats

summary = normalize_trusted_pstats(
    artifact=Path("/trusted/output/profile.pstats"),
    source_bundle=bundle,
    snapshot_sha=records["run"]["commit"],
    command_argv=["python", "-m", "cProfile", "sample.py"],
    manifest_hash=run_manifest_sha256,
    node_id="profile",
    trusted_artifact=True,
)
```

Python `cProfile`의 pstats는 `marshal` 형식이다. `run_manifest_sha256`은 호출자가 가진 실제 계획 해시로 교체한다. 검증되지 않은 저장소·외부 입력에는 명령이나 함수를 호출하지 않는다. CLI는 선언된 `cprofile` node만 받는다. 함수는 신뢰한 로컬 파일의 바이트 해시와 상위 hotspot을 요약하지만 명령·실행 환경·승인·성능 저하 재현 여부는 확인하지 못한다. 절대 경로나 불명확한 파일명은 source 파일에 억지로 연결하지 않고 `unknown`으로 남긴다. 이 요약은 `caller_declared_unattested`이며 `confirmed` 근거나 최종 보고서가 아니다.

`--hotspot-index`는 요약의 0부터 시작하는 순위 하나를 불변 Git 소스의 함수 문맥에 연결한다. 정확한 저장소 상대 경로·함수 시작 줄(데코레이터가 있으면 첫 데코레이터 줄)·함수 이름이 모두 일치하고 source 묶음이 실제 Git commit과 같을 때만 `hotspot_context`를 출력한다. 함수 내부의 다른 줄, 절대 경로, 파싱되지 않은 파일, 다른 함수, 범위 밖 줄은 거절한다. 이 연결은 **출처 코드의 위치 확인**이지 profiler가 해당 commit을 실행했다는 증명은 아니다. 기본 요약은 그대로 가능하며 Git 원본 대조는 `--hotspot-index`를 지정한 경우에만 수행한다.
