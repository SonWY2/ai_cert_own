# Module Context: git_modes

Git ref를 commit SHA로 동결한 뒤 추적 중인 Python 일반 파일만 점검 범위로 선택한다. 정기 main은 이전 수락 SHA와 같을 때만 건너뛴다. 후보는 main과의 merge-base를 기준으로 `full` 또는 `impact` 범위를 계산한다.

`impact`는 Git 변경 파일(이동 전후·삭제 포함)과 기준·대상 양쪽 그래프의 해석된 역방향 의존 파일을 선택한다. 선택 밖의 대상 파일과 삭제된 파일은 `omitted_unknown_paths`에 남긴다. 동적 참조·Python 외 설정 변경은 그래프만으로 완전하게 판단할 수 없다. 이 기능은 위험 변화 판정이나 보고서를 만들지 않는다.
