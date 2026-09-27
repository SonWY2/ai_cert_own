# Module Context: run_policy

이 모듈은 실행할 명령이 아니라 **RunManifest 선언과 해시**를 검증한다. Git commit SHA-1/256, 고정 Docker 이미지 digest, node별 명령·workload·trigger·도구, 총량·node별 예산, dependency·모델·workload 네트워크, `/work`·`/tmp` 쓰기 경로와 모델 이름·version·prompt hash·전송 자료를 검증한다.

영수증이나 사용자 승인은 발급·검사하지 않는다. Git 원본·이미지의 실제 존재, 명령 부작용·자원 제한·쓰기·네트워크 격리는 이 모듈만으로 증명하지 못한다. 실행기는 고정 원본과 선언된 한도를 검사하고 Docker 격리 안에서만 대상 코드를 실행한다.
