"""Capture deterministic mock-test evidence. Not a model/safety benchmark.

Usage: python run_conformance.py --reproduction PATH --paper PATH --out PATH
Standard library only. Run the same immutable source revision when comparing.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import unittest
import uuid
from datetime import datetime, timezone
from io import StringIO

class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []
        self._started = {}

    def startTest(self, test):
        self._started[test.id()] = time.perf_counter()
        super().startTest(test)

    def record(self, test, status, detail=None):
        self.records.append({"test_id": test.id(), "status": status,
            "duration_seconds": time.perf_counter() - self._started.get(test.id(), time.perf_counter()),
            "detail": detail})

    def addSuccess(self, test):
        super().addSuccess(test); self.record(test, "passed")

    def addFailure(self, test, err):
        super().addFailure(test, err); self.record(test, "failed", self._exc_info_to_string(err, test))

    def addError(self, test, err):
        super().addError(test, err); self.record(test, "error", self._exc_info_to_string(err, test))

    def addSkip(self, test, reason):
        super().addSkip(test, reason); self.record(test, "skipped", reason)

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err); self.record(test, "expected_failure")

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test); self.record(test, "unexpected_success")

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self.record(subtest, "subtest_failure", self._exc_info_to_string(err, test))

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def git_revision(root):
    try:
        return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"],
                                       text=True, stderr=subprocess.DEVNULL, timeout=10).strip()
    except (OSError, subprocess.SubprocessError):
        return None

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reproduction", required=True, type=Path)
    parser.add_argument("--paper", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    root = args.reproduction.resolve()
    if not (root / "tests/test_runtime_gate.py").is_file():
        parser.error("Missing tests/test_runtime_gate.py")
    args.out.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(root / "prototype"))
    started = datetime.now(timezone.utc).isoformat()
    suite = unittest.defaultTestLoader.discover(str(root / "tests"), pattern="test*.py")
    stream = StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=RecordedResult).run(suite)
    finished = datetime.now(timezone.utc).isoformat()
    print(stream.getvalue(), end="")
    (args.out / "unittest.log").write_text(stream.getvalue(), encoding="utf-8")
    paths = {str(p.relative_to(root)): sha256(p) for p in sorted(root.rglob("*.py"))}
    formats, missing = {}, []
    for extension in ("md", "html", "pdf"):
        candidates = sorted(args.paper.glob("MSAF_Working_Paper_v0.1_UA." + extension))
        if candidates:
            formats.update({p.name: sha256(p) for p in candidates})
        else:
            missing.append(extension)
    allowed_env = ("GITHUB_REPOSITORY", "GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT",
                   "GITHUB_SERVER_URL", "RUNNER_OS", "RUNNER_ARCH", "ImageOS", "ImageVersion")
    report = {"run_id": str(uuid.uuid4()), "started_utc": started, "finished_utc": finished,
        "python": sys.version, "platform": platform.platform(),
        "source_revision": git_revision(root), "runner": {k: os.getenv(k) for k in allowed_env if os.getenv(k)},
        "tests_run": result.testsRun, "successful": result.wasSuccessful() and result.testsRun > 0,
        "test_records": result.records, "code_sha256": paths,
        "manuscript_sha256": formats, "formats_not_present": missing,
        "dependencies": "Python standard library only; no external Python dependencies installed",
        "container_digest": None, "runner_is_hermetic": False,
        "llm_calls": 0, "full_evals_completed": 0,
        "limitations": ["Conformance of selected mock examples only; not independent attack trials.",
                        "This runner is authored with AI assistance; CI execution is not peer review.",
                        "Hashes identify bytes, not correctness or authorship."]}
    (args.out / "run.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if report["successful"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
