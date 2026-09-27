"""Render a human-readable view of an authenticated final bundle."""

import html
import json
import re
from pathlib import Path

from modules.evidence.final_bundle import verify_final_bundle
from modules.runtime_exec.docker import summarize_execution

_ANSI = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")
_MARKDOWN = re.compile(r"([\\`*_{}\[\]()#+.!|>~-])")


def _clean(value) -> str:
    return _CONTROL.sub("", _ANSI.sub("", str(value)))


def _text(value) -> str:
    return _MARKDOWN.sub(r"\\\1", html.escape(_clean(value), quote=True)).replace("://", ":\u200b//").replace("\n", " ")


def _code(value) -> str:
    content = html.escape(_clean(value), quote=True)
    length = max((len(match.group()) for match in re.finditer(r"`+", content)), default=0)
    fence = "`" * max(3, length + 1)
    return f"{fence}text\n{content}\n{fence}"


def _audit_rows(run):
    audit = run.get("model_audit") or []
    return [row for group in audit for row in
            (group["perspectives"] if "perspectives" in group else [group])]


def render_report(source_bundle: Path, final_bundle: Path, *,
                  runtime_trace_dir: Path | None = None) -> str:
    """Verify Git, sealed records and any runtime bytes before formatting."""
    sealed = verify_final_bundle(final_bundle, source_bundle, runtime_trace_dir=runtime_trace_dir)
    run, report = sealed["run"], sealed["report"]
    audit = _audit_rows(run)
    counts = {status: sum(row["status"] == status for row in audit)
              for status in ("completed", "failed", "deferred")}
    trace = run["runtime_trace"]
    execution = summarize_execution(trace, runtime_trace_dir) if trace is not None else None
    nodes = execution["nodes"] if execution is not None else []
    abnormal = any(row["status"] in ("failed", "deferred") for row in nodes)
    if report["analysis_status"] == "incomplete" or not audit:
        status = "분석 불완전" + ("·실행 명령 비정상 종료" if abnormal else "")
    elif not sealed["findings"]:
        status = "분석 완료·후보 없음, 결함 부재를 보장하지 않음"
    else:
        status = "분석 완료·후보는 검증 보류"
    coverage = run.get("diagnosis_coverage") or {}
    lines = ["# 코드 진단 결과", "", "## 요약", "", f"- 상태: {status}",
             f"- 저장소: {_text(run['repository'])}", f"- Git commit: {_text(run['target_sha'])}",
             f"- 선택 범위: {_text(run['scope'])}",
             f"- 관점: 완료 {counts['completed']} · 실패 {counts['failed']} · 보류 {counts['deferred']}",
             f"- 후보: {len(sealed['findings'])}건 (확증 {report['confirmed_count']}건)",
             f"- 원문 후보 행: 접수 {report['candidate_counts']['accepted']} · 미검증 {report['candidate_counts']['unverified']}",
             f"- 실행 node 결과: {len(nodes)}건"]
    review = [row["review"] for row in audit if "review" in row]
    if review:
        extracted = {item for row in review for item in row["extracted_ids"]}
        delivered = {item for row in review for item in row["delivered_ids"]}
        located = {item for row in review for candidate in row["candidate_matches"]
                   for item in candidate["ids"]}
        omitted = {item["id"] for row in review for item in row["omitted"]}
        grouped = run["model_audit"] or []
        if grouped and "scope_id" in grouped[0]:
            unlisted = sum(next((row["review"]["unlisted_count"]
                                 for row in scope["perspectives"] if "review" in row), 0)
                           for scope in grouped)
        else:
            unlisted = review[0]["unlisted_count"]
        lines += [f"- AST 점검 항목: 열거 {len(extracted)} · 요청에 구성 {len(delivered)} · "
                  f"후보 줄 겹침 {len(located)} · 누락 표시 {len(omitted)} · 예산 초과 미열거 {unlisted}",
                  "- 항목 ID와 줄 겹침은 모델의 검토 완료나 인과·실행 증거가 아님."]
    lines += ["", "## 관측된 실행 결과", ""]
    if not nodes:
        lines += ["실행하지 않음.", ""]
    else:
        lines += ["실행 로그는 명령 결과이며 원인 가설이나 결함 확증이 아님.", "",
                  "| node / trial | 상태·이유 | 실제 명령 argv | 종료 코드 | 소요시간(초) |",
                  "| --- | --- | --- | --- | --- |"]
        for node in nodes:
            argv = " ".join(node["command_argv"]) if node["executed"] else "미실행"
            state = ("명령 비정상 종료" if node["status"] == "failed" and
                     node.get("reason") == "nonzero_exit" else node["status"])
            lines.append("| " + " | ".join(_text(field) for field in (
                f"{node['node_id']} / {node.get('trial', '-')}",
                f"{state} ({node.get('reason') or '-'})", argv,
                node.get("exit_code", "-"), node.get("wall_seconds", "-"))) + " |")
        lines.append("")
        for node in nodes:
            for kind in ("stderr", "stdout"):
                if f"{kind}_path" not in node:
                    continue
                origin = Path(runtime_trace_dir) / node[f"{kind}_path"]
                lines += [f"### {_text(node['node_id'])} / {_text(node.get('trial', '-'))} {kind}", "",
                          f"검증된 원본: {_text(origin)} · 발췌 잘림: {str(node[f'{kind}_truncated']).lower()}", "",
                          _code(node[kind]), ""]
        if execution["truncated"]:
            lines += ["로그 발췌 전체 한도에 도달해 일부 내용을 생략함.", ""]
    lines += ["## 우선 확인할 문제와 개선안", ""]
    findings = {row["id"]: row for row in sealed["findings"]}
    if not report["priority_rows"]:
        lines += ["표시할 후보 없음. 실행 결과와 분석 범위는 별도로 확인할 것.", ""]
    for index, priority in enumerate(report["priority_rows"], 1):
        row = findings[priority["id"]]
        loc = row["location"]
        place = f"{loc['path']}:{loc['line']}" + (f"-{loc['end_line']}" if "end_line" in loc else "")
        action = row["next_action"]
        lines += [f"### {index}. {_text(row['id'])} — {_text(row['root_symbol'])}", "",
                  f"- 위치: {_text(place)} · {_text(row['severity'])} · {_text(row['taxonomy'])}",
                  f"- 근거 상태: {_text(row['state'])} (소스만 확인, 결함 확증 아님)",
                  f"- 원인 가설: {_text(row['mechanism'])}",
                  f"- 발생 조건: {_text(row['condition'])} / {_text(row['trigger'])}",
                  f"- 영향: {_text(row['impact'])}",
                  f"- 수정·검증 제안: {_text(action['action'])}",
                  f"- 기대 결과·반증 조건: {_text(action['oracle'])}",
                  f"- 예상 소요: {action['time_minutes']}분 (모델 추정치)",
                  f"- 근거 ID: {_text(', '.join(row['evidence_ids']))}", ""]
    lines += ["## AI 분석 근거·사용량", ""]
    manifest = run.get("manifest")
    if manifest and manifest.get("analysis") and manifest["analysis"]["mode"] == "boundary":
        lines += ["- 개발 전용 선택 모드: 기존 다섯 관점 + 가정·경계 검토자 (`assumptions`).",
                  "- 잠정 소스 검토이며 모든 후보는 검증 보류. 최종 F 또는 품질 우월성의 증명이 아님.",
                  "- 추가 검토자는 기존 다섯 분류로 후보를 제시하며, 결함 주입이나 실행·실패 발견은 필수가 아님."]
    if manifest and manifest.get("analysis") and manifest["analysis"]["mode"] == "generic":
        lines += ["- 개발 전용 선택 모드: 기존 다섯 관점 + 독립 일반 재검토자 (`generic`).",
                  "- 앞선 후보는 추가 검토자의 입력에 전달하지 않으며, 추가 후보나 실행 확인을 보장하지 않음."]
    if manifest and manifest["model"]["name_version"]:
        lines += [f"- 모델: {_text(manifest['model']['name_version'])}"]
    lines += [f"- 총 기록 토큰: {sum(row['tokens'] for row in audit)}", "",
              "응답 SHA는 저장된 정규화 제공자 응답의 digest이며 wire bytes가 아님.",
              "봉인은 내장 행의 무결성·접수 연결만 재검증하며 외부 응답 원자료나 실제 모델 호출을 독립 증명하지 않음.", "",
              "| 관점 | 상태·이유 | 요청 SHA-256 | 응답 SHA-256 | 토큰 | 시간(초) |",
              "| --- | --- | --- | --- | --- | --- |"]
    for row in audit:
        lines.append("| " + " | ".join(_text(value) for value in (
            row["perspective"], f"{row['status']} / {row['reason'] or '-'}",
            row.get("request_sha256", "-"), row.get("response_sha256", "-"),
            row["tokens"], row.get("wall_seconds", "-"))) + " |")
    lines += ["", "## 미검증 후보 행", ""]
    rejected = False
    for group in run.get("model_audit") or []:
        rows = group["perspectives"] if "perspectives" in group else [group]
        scope = group.get("scope_id", run["manifest"]["analysis"]["contexts"][0]["scope_id"])
        for row in rows:
            for entry in row["candidates"]:
                if entry["status"] != "unverified":
                    continue
                rejected = True
                lines += [
                    f"- {_text(scope)} / {_text(row['perspective'])} / 원래 행 {entry['index']}: "
                    f"{_text(entry['reason'])}",
                    f"  - 행 SHA-256: {_text(entry['candidate_sha256'])}",
                    f"  - 정규화 응답 SHA-256: {_text(row['response_sha256'])}",
                    f"  - 미검증 원문: {_text(json.dumps(entry['candidate'], ensure_ascii=False, sort_keys=True))}",
                ]
    if not rejected:
        lines.append("미검증 후보 행 없음. 후보나 결함의 부재를 증명하지 않음.")
    lines += ["", "## 분석 범위·실패", "", f"- 소스 바이트: {_text(coverage.get('source_bytes', '-'))}"]
    for key, label in (("symbol", "심볼"), ("context_node_ids", "선택 node ID"),
                       ("truncated", "문맥 잘림"), ("selected_paths", "선택 파일"),
                       ("analyzed_paths", "모든 관점 응답 완료 파일 (검토·진실 입증 아님)"),
                       ("omitted_unknown_paths", "미확인 파일")):
        if key in coverage:
            value = ", ".join(map(str, coverage[key])) if isinstance(coverage[key], list) else coverage[key]
            lines.append(f"- {label}: {_text(value)}")
    for row in audit:
        if row["status"] != "completed":
            lines.append(f"- {_text(row['perspective'])}: {_text(row['status'])} / {_text(row['reason'])}")
    lines += ["", "## 근거 파일", "", f"- 봉인된 5종 JSON: {_text(final_bundle)}",
              f"- Git 출처 묶음: {_text(source_bundle)}"]
    if runtime_trace_dir is not None:
        lines.append(f"- 실행 기록: {_text(Path(runtime_trace_dir) / 'execution.json')}")
    lines += ["", "이 문서는 검증된 JSON의 파생 표현이며 독립 증거 객체가 아님.", ""]
    return "\n".join(lines)
