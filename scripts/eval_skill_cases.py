#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "legal-case-export"
CASES_PATH = ROOT / "skill_eval_cases.yaml"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def has_all(text: str, needles: list[str]) -> bool:
    return all(needle.lower() in text for needle in needles)


def has_any(text: str, needles: list[str]) -> bool:
    return any(needle.lower() in text for needle in needles)


def assert_check(case_id: str, assertion: str, corpus: dict[str, str]) -> tuple[str, list[str]]:
    files = corpus
    if case_id == "story-01-export-mbox-basic":
        ok = has_all(files["references/workflows.md"], ["--mbox", "review.md", "llm_corpus.jsonl", "manifest.json"])
        return ("PASS" if ok else "FAIL", ["references/workflows.md"])
    if case_id == "story-02-export-mbox-overwrite-safety":
        ok = has_all(files["references/workflows.md"], ["non-destructive", "--force"])
        return ("PASS" if ok else "FAIL", ["references/workflows.md"])
    if case_id == "story-03-export-mbox-attachments-defaults":
        ok = has_all(files["references/workflows.md"], ["raw attachments are optional", "manifest.json"])
        return ("PASS" if ok else "FAIL", ["references/workflows.md"])
    if case_id == "story-04-pdf-ingest-default":
        ok = has_all(files["references/pdf-ingest.md"], ["balanced", "quality_report.csv", "preflight", "next step"])
        return ("PASS" if ok else "FAIL", ["references/pdf-ingest.md"])
    if case_id == "story-05-pdf-retry-targeted":
        ok = has_all(files["references/workflows.md"], ["quality_report.csv", "targeted", "already-good"])
        return ("PASS" if ok else "FAIL", ["references/workflows.md"])
    if case_id == "story-06-unified-export-basic":
        ok = has_all(files["references/unified-export.md"], [".msg", ".pdf", "deterministic", "manifest"])
        return ("PASS" if ok else "FAIL", ["references/unified-export.md"])
    if case_id == "story-07-unified-export-date-query-fallback":
        ok = has_all(files["references/unified-export.md"], ["date-query", "non-strict mode", "strict mode", "manifest.date_query"])
        return ("PASS" if ok else "FAIL", ["references/unified-export.md"])
    if case_id == "story-08-large-pdf-escalation":
        ok = has_all(files["references/pdf-ingest.md"], ["max-pages", "increase the sample size", "--ocr-timeout"])
        return ("PASS" if ok else "FAIL", ["references/pdf-ingest.md"])
    if case_id == "story-09-unified-export-partial-failure":
        ok = has_all(files["references/unified-export.md"], ["one bad file does not abort", "failed_files"]) and has_all(
            files["SKILL.md"], ["preserve partial success", "do not invent rich per-file remediation"]
        )
        return ("PASS" if ok else "FAIL", ["references/unified-export.md", "SKILL.md"])
    if case_id == "story-10-unsupported-input-narrowing":
        ok = has_all(files["SKILL.md"], [".docx", ".xlsx", "unsupported in v1"]) and has_all(
            files["references/workflows.md"], ["narrow", "reject cleanly"]
        )
        return ("PASS" if ok else "FAIL", ["SKILL.md", "references/workflows.md"])
    return ("WARN", [])


def must_not_claim_check(case_id: str, claim: str, corpus: dict[str, str]) -> tuple[str, list[str]]:
    files = corpus
    safe_checks: dict[str, tuple[str, list[str]]] = {
        "mbox deduplication": ("references/workflows.md", ["do not claim:", "mailbox deduplication"]),
        "multi-mbox merge support": ("references/workflows.md", ["do not claim:", "multi-mbox merge support"]),
        "attachment redaction support": ("references/workflows.md", ["do not claim:", "attachment redaction"]),
        "parallel worker execution": ("references/pdf-ingest.md", ["do not claim:", "real parallel worker execution"]),
        "automatic merge across unrelated reports": ("references/workflows.md", ["do not claim:", "automatic merge across unrelated reports"]),
        "support for docx, xlsx, images, or audio in V1": ("references/unified-export.md", ["not supported in v1:", ".docx", ".xlsx", "images", "audio"]),
        "quality guarantees for model-derived date ranking": ("references/unified-export.md", ["do not claim:", "quality guarantees for model-derived date ranking"]),
        "rich per-file remediation guarantees beyond current V1 scope": ("references/unified-export.md", ["do not promise:", "tailored per-file remediation"]),
        "support for unsupported evidence types in V1": ("references/workflows.md", ["unsupported evidence", "reject cleanly"]),
    }
    if claim in safe_checks:
        file_name, needles = safe_checks[claim]
        return ("PASS" if has_all(files[file_name], needles) else "FAIL", [file_name])
    return ("PASS", [])


def evaluate() -> dict[str, object]:
    cases = yaml.safe_load(CASES_PATH.read_text(encoding="utf-8"))
    file_paths = {
        "SKILL.md": SKILL_DIR / "SKILL.md",
        "references/workflows.md": SKILL_DIR / "references" / "workflows.md",
        "references/pdf-ingest.md": SKILL_DIR / "references" / "pdf-ingest.md",
        "references/unified-export.md": SKILL_DIR / "references" / "unified-export.md",
    }
    corpus = {name: read_text(path) for name, path in file_paths.items()}
    results = []

    for case in cases["cases"]:
        case_id = case["id"]
        expected_refs = case.get("expected_references", [])
        reference_match = all((SKILL_DIR / ref).exists() for ref in expected_refs)
        workflow_match = True
        if case["expected_workflow"] != "narrow-or-reject":
            workflow_match = has_any(corpus["SKILL.md"], [case["expected_workflow"]])

        assertion_results = []
        statuses = []
        for assertion in case.get("assertions", []):
            status, evidence = assert_check(case_id, assertion, corpus)
            assertion_results.append({"text": assertion, "status": status, "evidence": evidence})
            statuses.append(status)

        forbidden_results = []
        for claim in case.get("must_not_claim", []):
            status, evidence = must_not_claim_check(case_id, claim, corpus)
            forbidden_results.append({"text": claim, "status": status, "evidence": evidence})
            statuses.append(status)

        if not reference_match or not workflow_match:
            statuses.append("FAIL")

        overall = "PASS"
        if "FAIL" in statuses:
            overall = "FAIL"
        elif "WARN" in statuses:
            overall = "WARN"

        results.append(
            {
                "id": case_id,
                "status": overall,
                "workflow_match": workflow_match,
                "reference_match": reference_match,
                "assertions": assertion_results,
                "must_not_claim": forbidden_results,
            }
        )

    summary_counts = {"PASS": 0, "WARN": 0, "FAIL": 0, "NOT_RUN": 0}
    for result in results:
        summary_counts[result["status"]] += 1
    overall_status = "PASS" if summary_counts["FAIL"] == 0 and summary_counts["WARN"] == 0 else (
        "FAIL" if summary_counts["FAIL"] else "WARN"
    )

    return {
        "version": "1.0",
        "skill_name": "legal-case-export",
        "mode": "read-only",
        "run_id": "local-static-eval",
        "summary": {
            "overall_status": overall_status,
            "case_counts": summary_counts,
            "notes": [],
        },
        "cases": results,
        "artifacts": {
            "skill_path": str(SKILL_DIR.relative_to(ROOT)),
            "cases_path": str(CASES_PATH.relative_to(ROOT)),
            "logs": [],
            "raw_outputs": [],
        },
    }


def main() -> int:
    result = evaluate()
    print(json.dumps(result, indent=2))
    return 0 if result["summary"]["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
