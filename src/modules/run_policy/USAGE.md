# RunManifest 수동 승인

신규 실행은 `schema_version: run-manifest-v3`만 받는다. 모델을 쓰지 않으면 `analysis: null`이다. 모델을 쓰면 `analysis`에 `mode`, 순서 있는 `roles`, `scope`, `symbol`, `base_sha`, `context_policy`, `contexts[{scope_id,sha256}]`를 넣고 `model.prompt_sha256`에 모드별 **순서 있는 실제 지시문 집합** 해시를 넣는다. 선택 옵션과 Git 문맥·지침이 선언과 다르면 승인 소비·전송 전에 거절한다.

모델 설정은 [진단 준비 명령](../diagnosis/USAGE.md)의 `--prepare-manifest`로 생성하거나 `check_code.py`에서 준비한다. v1/v2 파일의 버전 문자열만 바꾸거나 기존 영수증을 재사용해서는 안 된다. 과거 v28 검증기는 [P1 오프라인 보존 기록](../../../docs/evidence/04-public-as-is-to-be-comparison.md#v29-p1-역할별-지침과-승인-경계-구현)의 별도 보관본으로만 사용하며 신규 전송을 허용하지 않는다.

P2 비교는 `context_policy`를 `git-ast-context-v1`(기존 원문), `git-ast-outline-v1`(AST 목록), `git-ast-cards-v1`(국소 근거 카드) 중 하나로 고정한다. 문맥 SHA는 추출·전달·누락 항목 목록까지 포함한다. `--review-units`가 준비와 실행에서 다르거나 Git 내용이 변하면 영수증 소진 전에 거절한다. single/plain은 기존 원문만 사용한다. P3 일반 여섯째 검토는 `analysis.mode=generic`, 역할 순서는 다섯 기본 역할 뒤 `generic`이며 boundary와 서로 다른 승인·영수증이 필요하다. 기존 v3 승인 자체를 새 모드·문맥으로 바꾸어 재사용하지 않는다.

```sh
python3 src/approve_run.py /path/to/repo /path/to/manifest.json /private/outside/repo/approval.json
```

명령은 승인 전에 RunManifest 전체와 SHA-256을 화면에 표시한다. 프로젝트 소유자가 대화형 터미널에서 해당 해시를 그대로 입력해야 새 영수증이 생긴다. 대상 저장소 안에는 기록할 수 없다.

Python API는 `src`를 Python 경로에 추가한 뒤 `from modules.run_policy import manifest_hash, issue_approval, verify_approval, consume_approval`로 사용한다. `issue_approval(manifest, snapshot_sha, receipt_path, typed_hash)`는 정확히 일치하는 SHA만 기록한다. 실제 실행 직전 `consume_approval(manifest, snapshot_sha, receipt_path)`를 호출하면 한 번만 소비된다. 실패해도 재사용되지 않는다.

소스 문맥을 모델에만 전송하는 승인은 `tools=[]`, `nodes=[]`, `limits.per_node={}`, `network.model=true`와 정확한 모델 주소·이름·프롬프트 해시·`transmitted_data`를 요구한다. 이 영수증으로 `--runtime-output`을 요청하면 실행 전에 거절한다. 영수증 파일의 부모 디렉터리는 해당 OS 사용자 소유이며 다른 사용자에게 쓰기 권한이 없어야 한다(예: 0700). 두 모델 호출은 영수증 두 개가 필요하다.

승인은 로컬 파일 상태다. 동일한 OS 사용자에게 위·변조 불가능한 서명이 아니다. 이 명령과 모듈은 Docker나 모델을 실행하거나 실행기를 대신하지 않는다.
