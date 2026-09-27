# RunManifest 자동 실행 경계

신규 실행은 `schema_version: run-manifest-v3`만 받는다. 모델을 쓰지 않으면 `analysis: null`이다. 모델을 쓰면 `analysis`에 `mode`, 순서 있는 `roles`, `scope`, `symbol`, `base_sha`, `context_policy`, `contexts[{scope_id,sha256}]`를 넣고 `model.prompt_sha256`에 모드별 실제 지시문 집합 해시를 넣는다. 선택 옵션·Git 문맥·지침이 선언과 다르면 전송 전에 거절한다.

`check_code.py`는 Git 출처를 읽고 제공한 템플릿에서 해당 실행의 정확한 RunManifest를 자동 구성한다. 별도 CLI는 [진단 준비 명령](../diagnosis/USAGE.md)의 `--prepare-manifest`로 파일을 만든 후 진단한다. v1/v2 파일의 버전 문자열만 바꿔서는 통과하지 않는다. 과거 v28 검증기는 [오프라인 보존 기록](../../../docs/evidence/04-public-as-is-to-be-comparison.md#v29-p1-역할별-지침과-승인-경계-구현)에서만 사용한다.

P2의 `context_policy`는 원문 `git-ast-context-v1`, AST 목록 `git-ast-outline-v1`, 국소 카드 `git-ast-cards-v1` 중 하나다. `--review-units`가 준비와 실행에서 다르거나 Git 내용이 변하면 거절한다. single/plain은 원문만 사용한다. 일반 여섯째 역할은 `analysis.mode=generic`이며 boundary와 별도 문맥·지침 해시를 사용한다.

모델 전용 RunManifest는 `tools=[]`, `nodes=[]`, `limits.per_node={}`, `network.model=true`와 정확한 모델 주소·이름·프롬프트 해시·`transmitted_data`를 요구한다. 대상 실행은 선언된 node가 있을 때만 수행한다. 영수증·대화형 입력은 없다. `manifest_hash(manifest)`는 설정의 식별자로 보고서와 실행 trace에 남으며 사용자 승인의 증거가 아니다.
