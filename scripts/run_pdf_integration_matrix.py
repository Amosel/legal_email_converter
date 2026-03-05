#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import multiprocessing as mp
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from legal_email_converter.pdf_ingest import run_pdf_ingest


def _health_from_summary(summary: dict[str, int]) -> str:
    if summary.get("failed", 0) > 0:
        return "FAIL"
    if summary.get("low_text", 0) > 0 or summary.get("likely_bad_ocr", 0) > 0:
        return "WARN"
    return "PASS"


def _first_status(manifest_path: Path) -> str:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    results = data.get("results", [])
    if not results:
        return "unknown"
    priority = {"failed": 4, "likely_bad_ocr": 3, "low_text": 2, "good": 1}
    statuses = [str(r.get("status", "unknown")) for r in results if isinstance(r, dict)]
    if not statuses:
        return "unknown"
    return max(statuses, key=lambda s: priority.get(s, 0))


def _avg_elapsed_seconds(manifest_path: Path) -> float:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    results = data.get("results", [])
    if not isinstance(results, list) or not results:
        return 0.0
    vals: list[float] = []
    for row in results:
        if not isinstance(row, dict):
            continue
        try:
            vals.append(float(row.get("elapsed_seconds", 0.0)))
        except (TypeError, ValueError):
            continue
    if not vals:
        return 0.0
    return sum(vals) / len(vals)


def _load_config(config_path: Path) -> dict:
    if config_path.suffix.lower() not in {".yaml", ".yml"}:
        raise ValueError(f"Config must be YAML (.yaml/.yml): {config_path}")
    text = config_path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
    except Exception as exc:
        raise RuntimeError("YAML config requires PyYAML. Install with: pip install pyyaml") from exc
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML config (expected object): {config_path}")
    return data


def _ingest_worker(kwargs: dict, queue: mp.Queue) -> None:
    try:
        result = run_pdf_ingest(**kwargs)
        queue.put({"ok": result})
    except Exception as exc:  # pragma: no cover - process boundary
        queue.put({"error": str(exc)})


def _run_ingest_with_timeout(kwargs: dict, timeout_seconds: int) -> tuple[dict | None, str | None]:
    queue: mp.Queue = mp.Queue()
    proc = mp.Process(target=_ingest_worker, args=(kwargs, queue))
    proc.start()
    proc.join(timeout_seconds)
    if proc.is_alive():
        proc.terminate()
        proc.join(5)
        return None, f"Timed out after {timeout_seconds}s"
    if not queue.empty():
        msg = queue.get()
        if "ok" in msg:
            return msg["ok"], None
        return None, msg.get("error", "unknown worker error")
    if proc.exitcode not in (0, None):
        return None, f"Worker exited with code {proc.exitcode}"
    return None, "No result returned from worker"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run PDF ingest integration matrix from YAML config."
    )
    parser.add_argument("--config", required=True, help="Path to matrix YAML config")
    parser.add_argument(
        "--bench",
        action="store_true",
        help="Print concise benchmark table after matrix execution.",
    )
    parser.add_argument(
        "--bench-csv",
        help="Optional path to write benchmark rows as CSV.",
    )
    args = parser.parse_args()

    config_path = Path(args.config).expanduser().resolve()
    if not config_path.exists():
        print(f"Config not found: {config_path}", file=sys.stderr)
        return 2

    try:
        cfg = _load_config(config_path)
    except Exception as exc:
        print(f"Failed to load config: {exc}", file=sys.stderr)
        return 2
    defaults = cfg.get("defaults", {})
    cases = cfg.get("cases", [])
    failures = 0
    bench_rows: list[dict[str, str]] = []
    run_started = datetime.now().strftime("run_%Y%m%d_%H%M%S")
    base_out_dir = Path(defaults.get("out_dir", "/tmp/lec_integration_matrix"))
    run_root = base_out_dir / run_started
    print(f"Run root: {run_root}")

    unresolved: list[str] = []
    missing_inputs: list[str] = []
    for case in cases:
        if not isinstance(case, dict):
            continue
        input_path = str(case.get("input", ""))
        case_id = str(case.get("id", "case"))
        if "/ABS/PATH/TO/" in input_path:
            unresolved.append(f"{case_id}: {input_path}")
        in_path = Path(input_path).expanduser()
        if not in_path.exists():
            missing_inputs.append(f"{case_id}: {input_path}")
    if unresolved:
        print("Config has unresolved placeholder paths. Edit your matrix config first.", file=sys.stderr)
        for row in unresolved:
            print(f"- {row}", file=sys.stderr)
        print("Example: replace /ABS/PATH/TO/... with real local PDF paths.", file=sys.stderr)
        return 2
    if missing_inputs:
        print("Config references missing input paths.", file=sys.stderr)
        for row in missing_inputs:
            print(f"- {row}", file=sys.stderr)
        print("Fix the file paths in your matrix config and rerun.", file=sys.stderr)
        return 2

    for case in cases:
        case_id = case.get("id", "case")
        input_path = str(case.get("input", ""))
        print(f"\n=== CASE: {case_id} ===")
        for run in case.get("runs", []):
            name = run.get("name", "run")
            out_dir = run_root / str(case_id) / str(name)
            out_dir.mkdir(parents=True, exist_ok=True)
            timeout_seconds = int(run.get("run_timeout_seconds", defaults.get("run_timeout_seconds", 1800)))
            try:
                kwargs = dict(
                    input_path=input_path,
                    profile=run.get("profile", "balanced"),
                    out_dir=str(out_dir),
                    workers=1,
                    ocr_jobs=int(run.get("ocr_jobs", defaults.get("ocr_jobs", 2))),
                    ocr_timeout=int(run.get("ocr_timeout", defaults.get("ocr_timeout", 1800))),
                    max_pages=run.get("max_pages"),
                    progress_style=str(defaults.get("progress_style", "plain")),
                    quiet=bool(defaults.get("quiet", True)),
                    no_color=bool(defaults.get("no_color", True)),
                )
                result, run_err = _run_ingest_with_timeout(kwargs, timeout_seconds)
            except Exception as exc:
                result, run_err = None, str(exc)
            if run_err:
                failures += 1
                print(f"{name}: ERROR {run_err}")
                bench_rows.append(
                    {
                        "case_id": str(case_id),
                        "run": str(name),
                        "profile": str(run.get("profile", "balanced")),
                        "max_pages": str(run.get("max_pages", "")),
                        "health": "ERROR",
                        "status": "error",
                        "avg_elapsed_seconds": "0.0",
                        "expectation": "FAIL",
                    }
                )
                continue
            if result is None:
                failures += 1
                print(f"{name}: ERROR no result")
                continue
            summary = result.get("summary", {})
            health = _health_from_summary(summary if isinstance(summary, dict) else {})
            manifest = Path(str(result.get("manifest", out_dir / "manifest.json")))
            status = _first_status(manifest) if manifest.exists() else "unknown"
            avg_elapsed = _avg_elapsed_seconds(manifest) if manifest.exists() else 0.0
            expect = run.get("expect", {})
            ok_health = health in expect.get("run_health_in", [health])
            ok_status = status in expect.get("status_in", [status])
            ok = ok_health and ok_status
            bench_rows.append(
                {
                    "case_id": str(case_id),
                    "run": str(name),
                    "profile": str(run.get("profile", "balanced")),
                    "max_pages": str(run.get("max_pages", "")),
                    "health": health,
                    "status": status,
                    "avg_elapsed_seconds": f"{avg_elapsed:.1f}",
                    "expectation": "PASS" if ok else "FAIL",
                }
            )
            print(
                f"{name}: health={health} status={status} "
                f"expected_health={expect.get('run_health_in', [])} "
                f"expected_status={expect.get('status_in', [])} "
                f"{'PASS' if ok else 'FAIL'}"
            )
            if not ok:
                failures += 1

    if args.bench:
        print("\nBENCHMARK")
        print("case_id | run | profile | max_pages | health | status | avg_elapsed_s | expectation")
        for row in bench_rows:
            print(
                f"{row['case_id']} | {row['run']} | {row['profile']} | {row['max_pages']} | "
                f"{row['health']} | {row['status']} | {row['avg_elapsed_seconds']} | {row['expectation']}"
            )
    if args.bench_csv:
        csv_path = Path(args.bench_csv).expanduser()
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "case_id",
                    "run",
                    "profile",
                    "max_pages",
                    "health",
                    "status",
                    "avg_elapsed_seconds",
                    "expectation",
                ],
            )
            writer.writeheader()
            writer.writerows(bench_rows)
        print(f"\nBenchmark CSV: {csv_path}")

    if failures:
        print(f"\nMatrix completed with {failures} failing expectation(s).", file=sys.stderr)
        return 1
    print("\nMatrix completed with all expectations passing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
