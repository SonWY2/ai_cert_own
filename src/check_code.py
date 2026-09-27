"""Scan a Git repository, request one manual approval and show a verified diagnosis."""

import argparse
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

from modules.diagnosis.model import prompt_hash, validate_model_plan, verify_responses
from modules.diagnosis.plan import prepare_analysis
from modules.evidence.authenticity import verify_git_source
from modules.evidence.final_bundle import verify_final_bundle
from modules.evidence.report import render_report
from modules.run_policy import manifest_hash
from modules.runtime_exec.docker import (validate_runtime_host, validate_runtime_plan,
                                         validate_source_workloads)
from modules.static_scan.orchestrator import git


def _save(path: Path, text: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(text)

def _private(root: Path) -> None:
    for path in (root, *root.rglob("*")):
        mode = path.lstat().st_mode
        if stat.S_ISDIR(mode):
            path.chmod(0o700)
        elif stat.S_ISREG(mode):
            path.chmod(0o600)
        else:
            raise ValueError("출력에 일반 파일이 아닌 항목이 있음")


def _child(name: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(Path(__file__).with_name(name)), *map(str, args)],
                          capture_output=True, text=True, check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path)
    parser.add_argument("--manifest", required=True, type=Path, help="Saved RunManifest template")
    parser.add_argument("--output", required=True, type=Path, help="New directory outside Git repository")
    parser.add_argument("--revision", default="HEAD")
    parser.add_argument("--symbol")
    parser.add_argument("--boundary-review", action="store_true",
                        help="Opt-in development review adding an assumptions/boundary reviewer")
    parser.add_argument("--generic-review", action="store_true",
                        help="Opt-in development run retaining five roles plus one general reviewer")
    parser.add_argument("--review-units", choices=("raw", "outline", "cards"), default="raw",
                        help="Approve unchanged source context, AST outline, or bounded local syntax cards")
    args = parser.parse_args()
    if args.boundary_review and args.generic_review:
        parser.error("Choose only one additional review mode")
    output = args.output.absolute()
    stage = "사전 확인"
    created = False
    try:
        repo = args.repository.resolve(strict=True)
        if git(repo, "rev-parse", "--is-bare-repository").strip() == b"true":
            source_root = Path(git(repo, "rev-parse", "--absolute-git-dir").decode().strip()).resolve()
        else:
            source_root = Path(git(repo, "rev-parse", "--show-toplevel").decode().strip()).resolve()
        if (output.exists() or output.is_symlink() or not output.parent.is_dir()
                or output.parent.is_symlink() or output.resolve().is_relative_to(source_root)):
            raise ValueError("새 출력 디렉터리는 저장소 밖의 기존 부모 아래에 있어야 함")
        if not sys.stdin.isatty():
            raise ValueError("대화형 단말 승인이 필요함; 모델 전송과 대상 실행 없음")
        template = json.loads(args.manifest.read_text(encoding="utf-8"))
        output.mkdir(mode=0o700)
        created = True
        print("[1/4] Git 출처 준비", flush=True)
        scanned = _child("scan_sources.py", repo, args.revision, output / "source")
        if scanned.returncode != 0:
            raise ValueError("Git 출처 스캔 거절")
        source = Path(json.loads(scanned.stdout)["source_bundle"])
        verified = verify_git_source(source)
        _private(output / "source")
        mode = "boundary" if args.boundary_review else "generic" if args.generic_review else "five"
        prompt_sha256 = prompt_hash(mode)
        analysis, _, _ = prepare_analysis(verified, mode=mode, symbol=args.symbol,
                                          scope=None if args.symbol else "full",
                                          review=args.review_units)
        manifest = {**template, "snapshot_sha": verified["run"]["commit"], "analysis": analysis,
                    "model": {**template["model"], "prompt_sha256": prompt_sha256}}
        manifest_hash(manifest)
        validate_model_plan(manifest, mode=mode)
        if manifest["nodes"]:
            validate_runtime_plan(manifest)
            validate_source_workloads(verified, manifest)
            if not {"log", "evidence"}.issubset(manifest["model"]["transmitted_data"]):
                raise ValueError("실행 로그·근거 전송 승인이 선언되지 않음")
            validate_runtime_host()
        _save(output / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        stage = "소유자 승인"
        print("[2/4] 현재 소스·모델·실행 설정 승인 (전체 RunManifest와 SHA-256 확인)",
              flush=True)
        approval = subprocess.run([sys.executable, str(Path(__file__).with_name("approve_run.py")),
                                   str(repo), str(output / "manifest.json"), str(output / "approval.json")])
        if approval.returncode:
            raise ValueError("대화형 승인이 취소되거나 거절됨")
        stage = "진단·실행"
        print("[3/4] 승인된 진단·실행", flush=True)
        command = [str(source), str(output / "manifest.json"), str(output / "approval.json"),
                   "--final-output", str(output / "final"),
                   "--response-output", str(output / "responses")]
        command += ["--symbol", args.symbol] if args.symbol else ["--scope", "full"]
        if args.boundary_review:
            command += ["--boundary-review"]
        if args.generic_review:
            command += ["--generic-review"]
        if args.review_units != "raw":
            command += ["--review-units", args.review_units]
        if manifest["nodes"]:
            command += ["--runtime-output", str(output / "runtime")]
        diagnosed = _child("diagnose_approved.py", *command)
        if diagnosed.returncode not in (0, 3):
            raise ValueError("진단 입력·승인 또는 무결성 검사 거절")
        _save(output / "result.json", diagnosed.stdout)
        result = json.loads(diagnosed.stdout)
        bundle = Path(result["final_source_only_bundle"])
        if not bundle.resolve().is_relative_to((output / "final" / "runs").resolve()):
            raise ValueError("진단 결과가 출력 디렉터리 밖을 가리킴")
        runtime_dir = output / "runtime" if manifest["nodes"] else None
        verify_responses(result["response_artifacts"], result["perspectives"])
        stage = "리포트 검증"
        report = render_report(source, bundle, runtime_trace_dir=runtime_dir)
        report += (f"\n## 승인된 모델 응답 원자료\n\n"
                   f"- 정규화 응답 {len(result['response_artifacts'])}건의 파일 해시·감사 연결 확인. "
                   "`responses/`는 소유자 전용이며 제공자 wire 원문이나 결함 확증은 아님.\n")
        _private(output)
        _save(output / "report.md", report)
        sealed = verify_final_bundle(bundle, source, runtime_trace_dir=runtime_dir)
        trace = sealed["run"]["runtime_trace"]
        failed = sum(node["status"] == "failed" for node in trace["nodes"]) if trace else 0
        state = "분석 불완전" if sealed["report"]["analysis_status"] == "incomplete" else "분석 완료"
        if failed:
            state += "·실행 명령 비정상 종료"
        print(f"[4/4] {state} · 실행 실패 {failed}건 · 후보 {len(sealed['findings'])}건")
        print(f"리포트: {output / 'report.md'}")
        print(f"모델 응답 원자료 {len(result['response_artifacts'])}건: {output / 'responses'}")
        return diagnosed.returncode
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        reason = str(error) if isinstance(error, ValueError) and stage == "사전 확인" else "해당 단계의 승인·검증이 완료되지 않음"
        print(f"{stage} 실패: {reason}", file=sys.stderr)
        if created and not (output / "report.md").exists():
            _save(output / "report.md", f"# 코드 진단 중단\n\n- 단계: {stage}\n- 원인: 해당 단계의 승인·검증이 완료되지 않음\n- 봉인된 결과: 없음\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
