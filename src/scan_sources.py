"""Freeze a Git revision, inspect Python source, and store source-stage evidence."""

import argparse
import json
import subprocess
from pathlib import Path

from modules.static_scan.cache import FactsCache
from modules.evidence.provenance import write_source_run
from modules.static_scan.code_graph import SOURCE_BYTE_BUDGET, build_graph, context
from modules.static_scan.replay import replay
from modules.static_scan.retrieval import retrieve
from modules.static_scan.orchestrator import git, graph, scan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path)
    parser.add_argument("revision")
    parser.add_argument("output_root", type=Path)
    parser.add_argument("--cache-dir", type=Path, help="External directory for validated per-file facts")
    parser.add_argument("--clean-replay", action="store_true", help="Compare cached static facts with a clean scan at the same commit")
    parser.add_argument("--node", help="Graph node ID for bounded source context")
    parser.add_argument("--frame", help="Frozen Python frame PATH:LINE (1-based physical line)")
    parser.add_argument("--symbol", help="Exact symbol name or graph node ID")
    parser.add_argument("--static-probes", action="store_true",
                        help="Show only source-located static boundary probes for --symbol, without executing code")
    parser.add_argument("--readable", action="store_true",
                        help="Print a readable static-probe summary instead of JSON (requires --static-probes)")
    parser.add_argument("--changed-file", action="append", default=[], help="Tracked Python path for lexical search")
    parser.add_argument("--query", help="Case-sensitive source substring in changed files")
    parser.add_argument("--hops", type=int, choices=(0, 1, 2), default=1)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--source-byte-budget", type=int, help="Maximum UTF-8 source slice bytes in selected context")
    args = parser.parse_args()
    try:
        if args.static_probes and (not args.symbol or args.node or args.frame or
                                   args.changed_file or args.query):
            raise ValueError("--static-probes requires only --symbol")
        if args.readable and not args.static_probes:
            raise ValueError("--readable requires --static-probes")
        if args.node and (args.frame or args.symbol or args.query or args.changed_file):
            raise ValueError("Use either --node or frame/symbol/lexical search")
        if (args.frame or args.symbol or args.query or args.changed_file) and args.hops != 1:
            raise ValueError("Search always includes up to two graph hops; --hops is for --node only")
        frame = None
        if args.frame is not None:
            path, separator, line = args.frame.rpartition(":")
            if not separator or not path or not line.isdecimal() or int(line) < 1:
                raise ValueError("--frame requires PATH:LINE with a positive line number")
            frame = (path, int(line))
        if args.clean_replay and not args.cache_dir:
            raise ValueError("--clean-replay requires --cache-dir")
        if args.source_byte_budget is not None and not (args.node or args.frame or args.symbol or args.query or args.changed_file):
            raise ValueError("--source-byte-budget requires context selection")
        if git(args.repository, "rev-parse", "--is-bare-repository").strip() == b"true":
            source_root = Path(git(args.repository, "rev-parse", "--absolute-git-dir").decode().strip())
        else:
            source_root = Path(git(args.repository, "rev-parse", "--show-toplevel").decode().strip())
        if args.output_root.resolve().is_relative_to(source_root.resolve()):
            raise ValueError("Evidence output must be outside the source repository")
        if args.cache_dir and args.cache_dir.resolve().is_relative_to(source_root.resolve()):
            raise ValueError("Facts cache must be outside the source repository")
        cache = FactsCache(args.cache_dir) if args.cache_dir else None
        replay_info = None
        if args.clean_replay:
            result, replay_info = replay(args.repository, args.revision, cache)
        if args.node or args.frame or args.symbol or args.query or args.changed_file:
            if replay_info is not None:
                db = build_graph(result, lambda oid: git(args.repository, "cat-file", "blob", oid))
            else:
                result, db = graph(args.repository, args.revision, cache=cache)
            try:
                if args.node:
                    selected = context(db, args.node, args.hops, args.limit,
                                       source_byte_budget=args.source_byte_budget if args.source_byte_budget is not None else SOURCE_BYTE_BUDGET)
                else:
                    selected = retrieve(db, frame=frame, symbol=args.symbol, changed_files=args.changed_file,
                                        query=args.query, limit=args.limit,
                                        source_byte_budget=args.source_byte_budget if args.source_byte_budget is not None else SOURCE_BYTE_BUDGET)
            finally:
                db.close()
        else:
            result = result if replay_info is not None else scan(args.repository, args.revision, cache=cache)
            selected = None
        bundle = write_source_run(args.output_root, str(args.repository.resolve()), result)
    except (subprocess.CalledProcessError, ValueError, FileExistsError) as error:
        parser.exit(2, f"source scan rejected: {error}\n")

    output = {"commit": result["commit"], "stage": "source_scanned", "source_bundle": str(bundle)}
    if cache is not None:
        output["cache_events"] = cache.events
    if replay_info is not None:
        output["clean_replay"] = replay_info
    if selected is not None:
        if args.static_probes:
            output["static_counterexamples"] = selected["static_counterexamples"]
            output["truncated"] = selected["truncated"]
        else:
            output["context"] = selected
    if args.readable:
        print("실행 없는 정적 위험 단서 (결함 확증 아님)")
        print(f"Git: {output['commit']}")
        print(f"출처 묶음: {json.dumps(output['source_bundle'], ensure_ascii=True)}")
        print(f"선택 심볼: {json.dumps(args.symbol, ensure_ascii=True)}")
        print(f"후보: {len(output['static_counterexamples'])}건 (0건도 안전 증명이 아님)")
        if output["truncated"]:
            print("주의: 분석 문맥이 잘려 후보가 누락될 수 있음")
        for index, probe in enumerate(output["static_counterexamples"], 1):
            location = f"{json.dumps(probe['path'], ensure_ascii=True)}:{probe['entry_line']}"
            entry = json.dumps(probe["entry_symbol"], ensure_ascii=True)
            sink = json.dumps(probe["sink_symbol"], ensure_ascii=True)
            parameter = json.dumps(probe["parameter"], ensure_ascii=True)
            risk = "0으로 나눌 가능성" if probe["kind"] == "zero_denominator" else "빈 목록 인덱싱 가능성"
            print(f"{index}. {location} {entry} → {sink}:{probe['sink_line']} · {risk}")
            print(f"   경계 입력: {parameter}={json.dumps(probe['input_value'])}"
                  + (f" · 호출 {probe['call_line']}행" if probe["call_line"] is not None else ""))
        print("다음 확인: 입력 계약·보호 조건 확인. 대상 코드 실행·LLM 판정은 수행하지 않음.")
        return 0
    print(json.dumps(output, sort_keys=True, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
