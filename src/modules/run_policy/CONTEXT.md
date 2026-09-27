# Module Context: run_policy

이 모듈은 실행할 명령이 아니라 **한 번 승인한 RunManifest의 선언과 해시**를 기록한다. Git commit SHA-1/256, 고정된 Docker 이미지 digest, node별 명령·workload·trigger·도구, 총량·node별 예산, dependency·모델·workload 네트워크, `/work`·`/tmp` 쓰기 경로와 모델 이름·version·prompt hash·전송 자료를 검증한다. 모델 전송은 HTTPS와 명시 승인 조건에서만 선언할 수 있다.

승인 영수증은 로컬 소유자의 전용 디렉터리에 배타적으로 저장하고, `.used` 파일로 중복 소비를 막는다. Git 원본·이미지의 실제 존재, 명령 부작용·자원 제한·쓰기·네트워크 격리, 사용자 신원은 이 모듈이 증명하지 않는다. Docker·모델·대상 코드를 실행하지 않으며, 실행기는 승인받은 선언을 격리 환경에 별도로 강제해야 한다.
