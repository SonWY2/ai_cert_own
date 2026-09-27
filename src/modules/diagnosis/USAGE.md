# 승인형 다섯 관점 진단

모든 신규 승인은 `run-manifest-v3`를 사용한다. 모델 활성 설정은 `analysis`에 모드·역할 순서·범위·심볼·기준 SHA·전달 문맥별 SHA를 포함한다. `model.prompt_sha256`은 선택 모드의 **순서 있는 역할별 실제 지시문 집합** 해시다. 준비용 템플릿은 `analysis: null`로 두고, **실행할 때와 같은 선택 옵션**으로 먼저 생성한다. 모델 전송·대상 실행·승인은 발생하지 않는다.

```sh
python3 src/diagnose_approved.py SOURCE_BUNDLE V3_TEMPLATE --symbol page \
  --prepare-manifest /private/prepared-manifest.json
python3 src/approve_run.py REPOSITORY /private/prepared-manifest.json /private/approval.json
python3 src/diagnose_approved.py SOURCE_BUNDLE /private/prepared-manifest.json /private/approval.json \
  --symbol page --response-output /private/new-responses
```

`single`·`plain`·`boundary`나 `full`·`impact`를 쓰면 준비 단계에도 해당 옵션을 그대로 지정한다. 과거 v1/v2 승인과 모드·역할·범위·문맥·지침이 다른 승인은 영수증 소진 전에 거절한다. `check_code.py`는 이 준비를 자동으로 수행한 뒤 소유자에게 새 해시 승인을 요청한다.

`--response-output`은 필수다. 정규화된 응답 JSON을 후보 해석 전에 저장한다(새 디렉터리 0700·파일 0600). HTTP 원시 바이트나 제공자 신원 증명이 아니다. 저장 실패 후 이미 보낸 요청의 승인은 재사용하지 않는다.

`python3 src/diagnose_approved.py --prompt-hash`는 기본 다섯 역할의 지침 집합 SHA-256을 출력한다. `--boundary-review`·`--single-baseline`·`--plain-baseline`과 함께 사용하면 **그 모드**의 해시가 나온다. `model.endpoint`는 `https://api.anthropic.com/v1/messages` 또는 **`http://127.0.0.1:10531/v1/responses`** 중 정확한 주소를 고른다. 후자는 [openai-oauth](https://github.com/EvanZhouDev/openai-oauth) 2.0.0의 계정별 OpenAI 호환 서버이며 **공식 유료 OpenAI API가 아니다**. 이 계정에서 `/v1/chat/completions`는 두 대상 모델 모두 500 오류였으므로 승인 주소로 사용할 수 없다. `model.name_version`은 모델별로 고정하고 `model.transmitted_data=["source","context"]`, `network.model=true`를 선언한다. Anthropic 키 `ANTHROPIC_API_KEY`는 저장소 밖 환경에서 제공한다.

로컬 서버 설치·기동은 별도 단말에서 수행한다. `npm install --prefix /tmp/wreckfish-openai-oauth-2.0.0 --no-save --ignore-scripts --package-lock=false openai-oauth@2.0.0`으로 설치하고, 프로젝트 소유자가 직접 `/tmp/wreckfish-openai-oauth-2.0.0/node_modules/.bin/openai-oauth login`으로 본인 계정을 인증한다. 같은 실행 파일을 `--host 127.0.0.1 --port 10531`로 기동한 뒤 `http://127.0.0.1:10531/v1/models`에서 본인 계정의 `gpt-6-sol`·`gpt-6-luna` 노출 여부를 확인한다. `--models`로 목록을 강제하면 실제 가용성을 검증할 수 없다. 로컬 서버에는 API 키 검사가 없으므로 외부 인터페이스에 바인딩하지 않고, OAuth 파일·요청 로그를 저장소에 넣거나 타인에게 전달하지 않는다. 한 모델·한 Git SHA·한 승인 영수증을 각각 별도로 사용한다. OMP의 모델 목록은 이 서버의 모델 가용성 증거가 아니다.

**개발 비교 전용:** 두 RunManifest의 `snapshot_sha`·모델 주소·문맥 심볼·전체 예산을 같게 고정하되 모델 이름과 **모드별 지침 해시**는 각각 승인한다. single과 five의 해시는 서로 다르다. 모델만 보내는 승인이라면 `tools=[]`, `nodes=[]`, `limits.per_node={}`로 실행 권한을 제외한다. 영수증 디렉터리는 소유자 전용(0700)이어야 하며 영수증 파일은 서로 달라야 한다. 소유자가 **각각** `python3 src/approve_run.py REPOSITORY MANIFEST OWNER_PRIVATE_RECEIPT`로 내용을 보고 표시된 SHA-256을 단말에 직접 입력한 뒤 다음 두 경로를 실행한다. 소스 전송은 이 승인 뒤에만 일어난다.

```sh
python3 src/diagnose_approved.py SOURCE_BUNDLE STRONG_MANIFEST STRONG_RECEIPT --symbol page --single-baseline --response-output /private/strong-responses
python3 src/diagnose_approved.py SOURCE_BUNDLE SMALL_MANIFEST SMALL_RECEIPT --symbol page --response-output /private/small-responses
```
`--single-baseline`은 **한 심볼 문맥에 강한 모델 1회**만 보내고 `stage=pilot_baseline_provisional`을 출력한다. `--final-output`·`--runtime-output`과 병용할 수 없다. 두 번째 명령은 같은 심볼 문맥을 작은 모델의 5관점에 보내지만, 실행 검증이 없으므로 최종 `F_runtime_feedback`이 아니다. 두 결과가 다르면 독립 행동 oracle로 원인과 결과를 별도로 확인해야 한다. 출력의 `findings`는 모두 보류이며, 총 토큰·소요시간만으로 USD 비용·발견률 우월성을 주장하지 않는다.

**P1 역할별 지침:** 공통으로 불변 소스의 조건부 위험을 추론하되 실행·계측 결과라고 말하지 않는다. 수정이 불명확하면 먼저 계약이나 행동을 확인하는 한 가지 순서 있는 권고를 낸다. 구조는 호출 계약과 자원 책임, 정확성은 분기·반복·예외, 성능은 규모별 반복 비용·I/O, 동시성은 외부/공유 상태·취소, 테스트는 제공된 검증식이 잘못된 동작을 구별하는지를 본다. assumptions는 가정·방어·자료 부족을 구별한다. 모든 역할은 기존 다섯 분류 중 맞는 분류를 쓸 수 있다. single은 공통 계약+짧은 일반 검토이며 다섯 역할을 하나로 합친 방식이 아니다. plain은 이전 일반 지시문을 유지하지만 새 v3 모드 해시가 필요하다.

five와 boundary의 처음 다섯 역할은 같은 입력·지시문을 사용한다. 여섯째 역할은 boundary에서만 호출된다. **후속 입력 예약**은 이전 제공자 입력(캐시 포함)에 이전/현재 역할과 지시문 바이트 길이를 더해 잡으므로 역할별 길이가 커지면 같은 전체 예산에서 후속 역할이 보류될 수 있다. 이는 보수적인 예약이지 제공자가 출력 상한을 실제 강제했다는 증거가 아니다.

**P2 개발 비교:** 기본값 `--review-units raw`는 v29와 동일하다. `--review-units outline`은 AST 구조 목록(P2a), `--review-units cards`는 같은 문맥 안의 조건·단순 대입/증감·구문상 종료 지점을 묶은 국소 카드(P2b)를 더한다. 세 방식은 **각각 다른 분석 문맥 SHA와 `context_policy`로 승인**해야 한다. 준비·실행·`check_code.py`에서 같은 옵션을 전달한다. single/plain 기준선에는 붙일 수 없다. 카드는 Git에서 인증한 이미 전달 가능한 소스 조각의 문법 사실만 보여준다. 미전달 줄·외부 호출 계약·별칭·경로 도달성은 확인하지 않으며 대상 코드를 실행하지 않는다.

```sh
python3 src/diagnose_approved.py SOURCE_BUNDLE V3_TEMPLATE --symbol page --review-units cards \
  --prepare-manifest /private/cards-manifest.json
python3 src/approve_run.py REPOSITORY /private/cards-manifest.json /private/cards-receipt.json
python3 src/diagnose_approved.py SOURCE_BUNDLE /private/cards-manifest.json /private/cards-receipt.json \
  --symbol page --review-units cards --response-output /private/cards-responses \
  --final-output /private/cards-final
```

봉인 감사의 추출/요청 구성/누락 ID와 후보 줄 겹침은 **문법 위치와 호출 결과의 연결**일 뿐 모델이 모든 경로를 검토했거나 그 줄이 인과 원인이라는 증거가 아니다. 원문 소스 조각·다섯 역할·전체 승인 예산을 유지한다. 이 비교는 카드의 고유 참양성 기여가 입증되기 전 기본 경로로 승격하지 않는다.

전체 범위를 강한 모델 **한 번**에 입력하려면 `--scope full --single-baseline`으로 별도 설정을 준비·승인하고 같은 옵션 및 `--response-output NEW_PRIVATE_DIR`로 실행한다. 그래프 이웃·검색 없이 추적된 모든 Python 모듈 원문을 보내므로 하나라도 파싱할 수 없으면 승인 전에 거절한다. 입력이 승인한 토큰/시간을 초과하면 결과는 보류된다. 전체 시스템의 실행 피드백·독립 정답·최종 비교를 대신하지 않는다.

```sh
# 아래는 각각 다른 준비 설정·미사용 영수증을 사용하는 선택 예시
python3 src/diagnose_approved.py SOURCE_BUNDLE SYMBOL_MANIFEST SYMBOL_RECEIPT --symbol 'function:src/example.py:work:12' --response-output /private/symbol-responses
python3 src/diagnose_approved.py SOURCE_BUNDLE FULL_MANIFEST FULL_RECEIPT --scope full --response-output /private/full-responses
python3 src/diagnose_approved.py CANDIDATE_BUNDLE IMPACT_MANIFEST IMPACT_RECEIPT --scope impact --main-ref <main-sha> --candidate-ref <candidate-sha> --response-output /private/impact-responses
```
`--scope full`은 해당 Git commit의 추적된 Python 파일 각각을 모듈 문맥으로 선택한다. 후보의 `--scope impact`는 merge-base 기준 양쪽 Git 그래프의 해석된 역방향 의존 범위만 선택하며, 생략된 경로(삭제 파일 포함)는 `diagnosis_coverage.omitted_unknown_paths`에 남긴다. 후보 `--scope full`에도 두 ref를 함께 전달할 수 있다. 후보 SHA는 인증된 source bundle과 일치해야 하며, 두 ref는 함께 지정해야 한다. 각 파일의 완전한 모듈 source slice가 24 KiB 문맥 한도에 들어오지 않거나 파싱할 수 없으면 해당 모듈은 보류된다.

`--symbol`은 반환 문맥에 요청한 심볼 자체가 들어갈 때만 승인 영수증을 소비한다. 심볼 조각이 문맥 바이트 한도에서 제외되면 이웃 코드만 보고 진단하지 않고 거절한다. 후보의 파일·줄이 전달 범위를 벗어나면 **그 행만** 미검증으로 남기고 정상 행은 유지한다. 봉인에는 `scope=selected_symbol_only`와 요청 심볼·Git 문맥 노드·바이트·잘림 상태가 남으며 전체 파일 진단을 뜻하지 않는다.

출처를 스캔한 Python 버전과 진단 CLI의 Python 버전은 같아야 한다. 예를 들어 Python 3.14 코드의 `scan_sources.py`를 `python3.14`로 실행했다면 `diagnose_approved.py`도 `python3.14`로 실행한다. 달라지면 Git 원문이 같더라도 AST 파싱 결과가 달라질 수 있어 영수증 소진 전에 거절한다.

한 명령에 승인 영수증 **하나**를 사용하고, 전체 모듈과 5관점이 동일한 토큰·벽시계 한도를 공유한다. 승인 전에는 source를 모델에 보내지 않는다. 모듈은 경로순, 관점은 고정된 다섯 관점순으로 호출되며 남은 예산이 부족하면 이후 호출을 보류한다. 결과의 `perspectives`에는 모듈 ID별 5개 호출 상태가 기록되고, `diagnosis_coverage`에는 선택·5관점 완료·미완료/생략 경로와 사용량을 구분한다. 관점 일부가 완료됐더라도 미완료 모듈은 unknown이며, 선택 외 파일이나 unresolved graph edge·비 Python 소스는 점검 완료로 간주하지 않는다.

호출 완료와 후보 접수는 별개다. 유효한 응답 안에 잘못된 행이 있어도 호출은 `completed`이며, 각 행에는 원래 순번·원문·행 SHA·접수 상태·거절 이유·연결 finding ID가 남는다. `taxonomy`는 호출 역할과 관계없이 기존 다섯 분류 중 하나다. `perspective`는 모델이 아닌 실제 호출 역할로 기록한다. 정확한 동일 원인·조건·영향 키에서 trigger·분류·다음 행동·파일이 충돌하면 해당 묶음 전체를 미검증으로 분리하고 독립 후보는 유지한다. 의미가 같은 다른 문장까지 병합하는 기능은 아니다.

`report.candidate_counts`는 접수/미검증 **행 수**, `findings`는 병합된 가설이다. 미검증 행·실패·보류가 하나라도 있으면 `analysis_status=incomplete`, CLI 종료 3이다. 호출 완료 모듈 수와 분석의 완전성은 같지 않다. 봉인은 원문 행과 Finding 연결을 검사하고, `check_code.py`는 `verify_responses`로 실제 응답 파일의 권한·해시·순번·사용량까지 대조한 뒤 보고서를 만든다.

영수증 소진 전에 모델 프롬프트·지원 주소·전송 항목을 확인한다. 실행 출력을 요청한 경우에는 명령이 실제 Git 추적 Python 파일을 가리키는지도 확인한다. 승인 영수증과 실행 출력은 대상 저장소와 출처 묶음 모두의 바깥에 있어야 한다. 부적합하면 모델 전송·대상 실행 없이 거절하고 영수증을 남긴다.

`--final-output /private/reports`는 먼저 감사 상태와 미관측 경로를 출처 전용 불변 보고서로 저장한다. `--runtime-output /private/runtime`을 함께 지정해 격리 실행 흔적을 기록하면, 별도의 불변 후속 보고서가 실행 파일·로그 해시를 다시 검증해 연결한다. 연결된 실행 기록도 `caller_declared_unattested`이며 결함 확증이나 독립 oracle 판정이 아니다. 실행이 실패하면 이전 출처 전용 보고서는 유지된다. `seal_report.py`로 별도 보고서를 만드는 경우 `--run-manifest`와 `--runtime-trace-dir`을 함께 전달하고, 후속 소유자 조치에는 `record_final_action.py --runtime-trace-dir`을 전달한다. 승인 명령은 실제 단말에서 소유자가 manifest 해시를 직접 입력해야 한다. CLI는 원본 Git·선택 범위·manifest를 확인하고 일회용 승인을 소진한 뒤에만 선언된 endpoint로 source 문맥을 전송하며, 프록시·HTTP 리다이렉트는 사용하지 않는다. 응답의 evidence ID와 실제 Git 줄을 다시 확인한다. 요청/응답 해시와 **총 토큰**은 호출 기록에 남지만 이 OAuth 구독 방식에서는 호출별 실제 청구액 영수증을 얻지 못한다. 요청/응답 해시는 실제 모델 호출이나 청구 증명이 아니며, 현재 명령의 두 모델별 결과는 강한 모델 **1회** 대 작은 모델 **전체 시스템**의 최종 비교가 아니다. API 성공, 실행 검증, 저장소 전체 결함 부재 또는 최종 인증 성과를 주장하지 않는다.

## 선택 추가 역할: 가정·경계조건 검토

기본 다섯 관점은 그대로다. `--boundary-review`를 명시하면 마지막에 `assumptions` 역할을 한 번 추가한다. 입력·외부 반환값·상태 유지·정리 경로의 가정이 코드와 호출 계약에서 보장되는지 살펴본다. 결함 주입·코드 실행·수정은 하지 않으며, 반드시 문제를 찾거나 반례를 만들도록 요구하지 않는다. 후보가 없다는 응답도 안전의 증거는 아니다.

```sh
python3 src/diagnose_approved.py SOURCE_BUNDLE V3_TEMPLATE --symbol page --boundary-review \
  --prepare-manifest BOUNDARY_MANIFEST
python3 src/approve_run.py REPOSITORY BOUNDARY_MANIFEST BOUNDARY_RECEIPT
python3 src/diagnose_approved.py SOURCE_BUNDLE BOUNDARY_MANIFEST BOUNDARY_RECEIPT \
  --symbol page --boundary-review --final-output /private/boundary-report \
  --response-output /private/boundary-responses
```

`--scope full`과 `--scope impact`에도 적용된다. `--single-baseline`·`--plain-baseline`과는 병용할 수 없다. 다섯 역할용 지침 집합 해시·영수증은 추가 역할을 허용하지 않는다. boundary의 처음 다섯 지시문은 기본 모드와 같지만 여섯 번째 항목 때문에 **전체 집합 해시는 다르다**. 이전 v2 해시·영수증은 신규 실행에 사용할 수 없다.

한 명령으로 승인과 리포트까지 연결하려면 다음을 사용한다. 출력은 저장소 밖의 새 디렉터리여야 하고 실제 대화형 단말 승인이 필요하다.

```sh
python3 src/check_code.py REPOSITORY --manifest MANIFEST_TEMPLATE \
  --output /private/boundary-check --symbol page --boundary-review
```

`check_code.py`는 선택한 모드·역할·범위·문맥과 지침 집합 해시를 승인 전에 RunManifest에 기록한다. 여섯 역할과 전체 모듈이 같은 총 토큰·시간 예산을 공유하며 추가 역할용 예산을 자동 증액하지 않는다. 모든 역할의 분류는 기존 structure/correctness/performance/concurrency/tests 중 하나다. 기본 다섯 지시문은 boundary 여부에 따라 바뀌지 않으며 과거 v2 승인으로 P1 진단을 호출할 수 없다.

결과는 `stage=pilot_boundary_review_provisional`이다. Markdown 보고서는 개발 전용 모드와 역할별 비용을 표시한다. 잘못된 위치·출처·형식의 후보는 기존 검사를 통과하지 못하며 다른 역할의 유효한 후보는 유지된다. 역할 일부가 실패·보류되면 종료 코드 3이고, 해당 모듈은 분석 완료로 세지 않는다. 봉인해도 모든 후보는 `source_only/deferred`이며 실제 결함 확증이 아니다. 원인이 같은 후보의 의미 중복을 새 역할이 자동 해결하지는 않는다.

새 역할은 개발 비교 경로이며 최종 F·기존 80사례·두 shadow 실험을 대체하거나 성능 향상을 입증하지 않는다. 기본 다섯 관점, 다섯 관점+일반 재검토, 다섯 관점+추가 역할을 같은 작은 모델·전체 예산으로 비교해 고유 발견·오탐·중복·전체 비용을 별도 측정해야 한다.

## 선택 추가 역할: 일반 재검토 대조

`--generic-review`는 기본 다섯 호출 뒤에 `generic` 역할을 **한 번** 더 실행하는 개발용 대조다. `--boundary-review`와 동시에 선택할 수 없다. 다섯/일반 여섯/가정 여섯 각각의 첫 다섯 역할 지침은 같고, 여섯째는 앞선 후보를 입력받지 않는다. 세 모드는 별도 지침 집합 해시·문맥 SHA·새 영수증이 필요하다. 준비·승인·실행에서 똑같은 옵션을 사용한다.

```sh
python3 src/diagnose_approved.py SOURCE_BUNDLE V3_TEMPLATE --symbol page --generic-review \
  --prepare-manifest GENERIC_MANIFEST
python3 src/approve_run.py REPOSITORY GENERIC_MANIFEST GENERIC_RECEIPT
python3 src/diagnose_approved.py SOURCE_BUNDLE GENERIC_MANIFEST GENERIC_RECEIPT \
  --symbol page --generic-review --response-output /private/generic-responses \
  --final-output /private/generic-final
```

`stage=pilot_generic_review_provisional`; 분류·위치·출처 접수 기준과 `source_only/deferred`, 예산·실패·봉인 규칙은 기본 경로와 같다. 성공한 모델 호출이나 새 후보 수를 여섯째 역할의 고유 참양성 기여로 세지 않는다. 별도 독립 판정·실제 호출 비용과 공통 처음 다섯 응답의 오프라인 재조합을 나란히 제시해야 한다.
