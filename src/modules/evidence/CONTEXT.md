# Module Context: evidence

동결된 정적 읽기 결과의 출처만 불변 JSON으로 보존한다. `run.json`은 `stage: source_scanned`인 중간 기록이며 최종 `ScanRun`이나 수락된 진단 보고서가 아니다. `evidence.jsonl`에는 파일별 `Evidence(kind=source)`가 있다. 두 기록은 key 정렬 UTF-8 JSON에서 `content_hash`를 제외한 SHA-256으로 봉인한다.

검증기는 저장된 기록의 형식·해시·연결 관계만 확인한다. 원본 Git blob 재확인, Finding·Report·runtime 근거·사용자 행동은 제공하지 않는다.
