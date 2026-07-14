from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import cast

from v09_loop_audit import (  # pyright: ignore[reportImplicitRelativeImport]
    NETWORK_ERROR,
    audit_network_capabilities,
    tree_digest,
)
from v09_loop_contract import (  # pyright: ignore[reportImplicitRelativeImport]
    as_dict,
    manifest_payload,
    validate_manifest,
)
from v09_loop_isolation import (  # pyright: ignore[reportImplicitRelativeImport]
    environment_evidence,
    kernel_evidence,
    kernel_isolation,
    network_probe_sources,
    probe_launcher_environment,
    require_kernel_network_deny,
)
from v09_loop_runtime import (  # pyright: ignore[reportImplicitRelativeImport]
    run_case_isolated,
)

__all__ = [
    "audit_network_capabilities",
    "build_report",
    "main",
    "network_probe_sources",
    "probe_launcher_environment",
    "require_kernel_network_deny",
    "run_case",
]


def run_case(case: dict[str, object], plugin_root: Path, data_root: Path) -> dict[str, object]:
    isolation = kernel_isolation()
    try:
        return run_case_isolated(case, plugin_root, data_root, isolation)
    finally:
        isolation.close()


def build_report(manifest: Path | dict[str, object], plugin_root: Path) -> dict[str, object]:
    payload, raw_manifest = manifest_payload(manifest)
    cases = validate_manifest(payload)
    isolation = kernel_isolation()
    try:
        network = audit_network_capabilities(plugin_root)
        network.update(environment_evidence(isolation))
        plugin_digest = tree_digest(plugin_root)
        with tempfile.TemporaryDirectory(prefix="super-sol-loop-replay-") as directory:
            data_root = Path(directory)
            results = [run_case_isolated(case, plugin_root, data_root, isolation) for case in cases]
        if tree_digest(plugin_root) != plugin_digest:
            raise ValueError(NETWORK_ERROR)
    finally:
        isolation.close()
    network["kernel_network_deny"] = kernel_evidence()
    passed = sum(result["passed"] is True for result in results)
    unexpected = sum(cast("int", result["unexpected_contexts"]) for result in results)
    return {
        "schema": "super-sol-loop-replay/v1",
        "manifest_sha256": hashlib.sha256(raw_manifest).hexdigest(),
        "plugin_tree_sha256": plugin_digest,
        "network_calls": 0,
        "network_calls_semantics": "successful-network-operations",
        "successful_network_calls": 0,
        "network_isolation": network,
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "unexpected_contexts": unexpected,
        },
        "cases": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    _ = parser.add_argument("--manifest", type=Path, required=True)
    _ = parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    output = cast("Path", arguments.output)
    report = build_report(
        cast("Path", arguments.manifest),
        Path(__file__).parents[1] / "plugins" / "super-sol",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    _ = output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary = as_dict(report["summary"])
    return 0 if summary is not None and summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
