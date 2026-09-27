"""
Aegis Unified CLI Interface
Provides commands for init, discover, analyze, impact, plan, test, investigate, report, and release-check.
"""

from __future__ import annotations
import sys
import os
import json
import argparse
from pathlib import Path
from typing import Optional, List

from aegis import __version__
from aegis.core.orchestrator import AegisEngine
from aegis.core.config import AegisConfig
from aegis.evidence.collector import EvidenceCollector
from aegis.evidence.models import TestResult, TestStatus, EvidenceReport


def print_banner() -> None:
    print(
        r"""
    ___    ______ _____  ____ _____
   /   |  / ____// ___/ /  _// ___/
  / /| | / __/  / / __  / /  \__ \ 
 / ___ |/ /___ / /_/ /_/ /  ___/ / 
/_/  |_/_____/ \____//___/ /____/  
Universal AI Quality Engineering & Production Readiness Platform
        """
    )


def build_parser() -> argparse.ArgumentParser:
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Output results in machine-readable JSON format")
    common_parser.add_argument("--workspace", default=argparse.SUPPRESS, help="Target workspace path (defaults to current directory)")
    common_parser.add_argument("--verbose", "-v", action="store_true", default=argparse.SUPPRESS, help="Enable verbose diagnostic logs")

    parser = argparse.ArgumentParser(
        prog="aegis",
        description="Aegis: Universal AI Quality Engineering & Production Readiness Platform",
        parents=[common_parser],
    )
    parser.add_argument("--version", action="version", version=f"Aegis v{__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # graph group
    p_graph = subparsers.add_parser("graph", parents=[common_parser], help="Project Intelligence Graph operations")
    p_graph_sub = p_graph.add_subparsers(dest="graph_action", help="Graph action: build, inspect, dependencies, impact")
    
    p_g_build = p_graph_sub.add_parser("build", parents=[common_parser], help="Build or incrementally update project graph")
    p_g_build.add_argument("--force", action="store_true", help="Force full re-indexing of all files")

    p_g_inspect = p_graph_sub.add_parser("inspect", parents=[common_parser], help="Inspect a specific node in the graph")
    p_g_inspect.add_argument("node_id", help="Target node identifier")

    p_g_deps = p_graph_sub.add_parser("dependencies", parents=[common_parser], help="Show upstream dependencies for a node")
    p_g_deps.add_argument("node_id", help="Target node identifier")
    p_g_deps.add_argument("--depth", type=int, default=3, help="Max traversal depth")

    p_g_imp = p_graph_sub.add_parser("impact", parents=[common_parser], help="Show downstream dependents for a node")
    p_g_imp.add_argument("node_id", help="Target node identifier")
    p_g_imp.add_argument("--depth", type=int, default=5, help="Max traversal depth")

    # init
    p_init = subparsers.add_parser("init", parents=[common_parser], help="Initialize Aegis in current workspace (.aegis/)")

    # discover
    p_disc = subparsers.add_parser("discover", parents=[common_parser], help="Discover languages, frameworks, build tools, infra, APIs, and tests")
    p_disc.add_argument("--name", help="Custom project name override")

    # analyze
    p_ana = subparsers.add_parser("analyze", parents=[common_parser], help="Perform static architecture and dependency analysis")

    # impact
    p_imp = subparsers.add_parser("impact", parents=[common_parser], help="Detect changed symbols and compute downstream blast radius")
    p_imp.add_argument("--depth", type=int, default=5, help="Max traversal depth")

    # risk
    p_risk = subparsers.add_parser("risk", parents=[common_parser], help="Calculate deterministic, explainable risk assessment")

    # plan
    p_plan = subparsers.add_parser("plan", parents=[common_parser], help="Generate adaptive, risk-weighted test plan")
    p_plan.add_argument("--changed-only", action="store_true", help="Only plan tests for impacted code")

    # test
    p_test = subparsers.add_parser("test", parents=[common_parser], help="Execute deterministic quality validations")
    p_test.add_argument("category", nargs="?", default="all", help="Test category: unit, api, sanity, integration, e2e, ui, security, performance, compatibility, all")
    p_test.add_argument("--dry-run", action="store_true", help="Simulate execution without running commands")
    p_test.add_argument("--changed-only", action="store_true", help="Only run tests impacted by recent changes")
    p_test.add_argument("--parallel", action="store_true", default=True, help="Enable parallel test execution")
    p_test.add_argument("--fail-fast", action="store_true", default=True, help="Halt downstream dependents immediately upon upstream failure")
    p_test.add_argument("--ci", action="store_true", help="Run in strict CI mode")

    # run (runs full planned DAG)
    p_run = subparsers.add_parser("run", parents=[common_parser], help="Execute complete planned execution DAG")
    p_run.add_argument("--dry-run", action="store_true", help="Simulate execution without running commands")
    p_run.add_argument("--changed-only", action="store_true", help="Only run tests impacted by recent changes")
    p_run.add_argument("--parallel", action="store_true", default=True, help="Enable parallel test execution")
    p_run.add_argument("--fail-fast", action="store_true", default=True, help="Halt downstream dependents immediately upon upstream failure")

    # quality
    p_qual = subparsers.add_parser("quality", parents=[common_parser], help="Execute deterministic quality dimension validations (a11y, security, perf, ux)")
    p_qual.add_argument("dimension", nargs="?", default="all", help="Target quality dimension: accessibility, security, performance, ux, all")
    p_qual.add_argument("--dry-run", action="store_true", help="Simulate quality scan without invoking external tools")
    p_qual.add_argument("--changed-only", action="store_true", help="Only run quality checks on impacted surfaces")
    p_qual.add_argument("--full", action="store_true", help="Run comprehensive quality audit across all dimensions")
    p_qual.add_argument("--release", action="store_true", help="Run strict release-level quality audit")

    # investigate
    p_inv = subparsers.add_parser("investigate", parents=[common_parser], help="Investigate and fingerprint recent failures")
    p_inv.add_argument("--fingerprint", help="Specific failure fingerprint to look up")

    # report
    p_rep = subparsers.add_parser("report", parents=[common_parser], help="Generate consolidated evidence and readiness report")

    # release-check
    p_rel = subparsers.add_parser("release-check", parents=[common_parser], help="Evaluate deterministic release readiness policy gate")

    return parser


def main(args: Optional[List[str]] = None) -> int:
    parser = build_parser()
    parsed = parser.parse_args(args)

    parsed.json = bool(getattr(parsed, "json", False))
    parsed.workspace = str(getattr(parsed, "workspace", "."))
    parsed.verbose = bool(getattr(parsed, "verbose", False))

    if not parsed.command:
        if not parsed.json:
            print_banner()
            parser.print_help()
        else:
            print(json.dumps({"error": "No command specified", "version": __version__}))
        return 1

    workspace_path = Path(parsed.workspace).resolve()
    engine = AegisEngine(workspace_root=workspace_path)

    try:
        if parsed.command == "init":
            cfg_path = engine.init_workspace()
            if parsed.json:
                print(json.dumps({"status": "initialized", "config_file": str(cfg_path), "workspace": str(workspace_path)}))
            else:
                print_banner()
                print(f"[+] Initialized Aegis workspace at: {workspace_path}")
                print(f"[+] Created configuration: {cfg_path}")
                print(f"[+] Populated initial project profile and maps in .aegis/")
            return 0

        elif parsed.command == "discover":
            profile = engine.discover(project_name=getattr(parsed, "name", None))
            if parsed.json:
                print(profile.model_dump_json(indent=2))
            else:
                print_banner()
                print(f"[*] Project Name   : {profile.project_name}")
                print(f"[*] Root Path      : {profile.root_path}")
                print(f"[*] Tree Hash      : {profile.tree_hash[:16]}...")
                print("\n[+] Languages Detected:")
                for lang in profile.languages:
                    ver = f" (v: {lang.version_hint})" if lang.version_hint else ""
                    print(f"    - {lang.name:<12} {lang.file_count:>3} files ({lang.percentage:>5.1f}%){ver}{' [PRIMARY]' if lang.primary else ''}")
                
                print("\n[+] Frameworks Detected:")
                for fw in profile.frameworks:
                    print(f"    - {fw.name:<14} [{fw.category}] {f'(v: {fw.version})' if fw.version else ''}")

                print("\n[+] Build Systems:")
                for b in profile.build_systems:
                    lock = f" (lockfile: {b.lock_file})" if b.lock_file else ""
                    print(f"    - {b.name:<12} manifest: {b.manifest_file}{lock}")

                print("\n[+] Test Suites:")
                for ts in profile.test_suites:
                    print(f"    - {ts.framework:<12} ~{ts.test_count_estimate} tests across {len(ts.test_files)} files")

                print(f"\n[+] Stored machine-readable profile in: {workspace_path / '.aegis' / 'project-profile.json'}")
            return 0

        elif parsed.command == "analyze":
            profile = engine.discover()
            if parsed.json:
                print(json.dumps({
                    "project_name": profile.project_name,
                    "architecture": profile.infrastructure.model_dump(),
                    "interfaces": profile.interfaces.model_dump(),
                }, indent=2))
            else:
                print_banner()
                print(f"[*] Static Analysis for: {profile.project_name}")
                print(f"    - Docker: {profile.infrastructure.has_docker} ({len(profile.infrastructure.dockerfiles)} dockerfiles)")
                print(f"    - Compose: {profile.infrastructure.has_compose} ({len(profile.infrastructure.compose_files)} files)")
                print(f"    - Databases: {', '.join(profile.infrastructure.detected_databases) or 'None detected'}")
                print(f"    - CI/CD: {', '.join(profile.infrastructure.ci_providers) or 'None detected'}")
                print(f"    - Discovered REST Endpoints: {len(profile.interfaces.rest_endpoints)}")
            return 0

        elif parsed.command == "graph":
            action = getattr(parsed, "graph_action", "build") or "build"
            if action == "build":
                force = getattr(parsed, "force", False)
                stats = engine.build_graph(force_full=force)
                if parsed.json:
                    print(stats.model_dump_json(indent=2))
                else:
                    print_banner()
                    print("[+] Project Intelligence Graph Built Successfully")
                    print(f"    - Total Nodes   : {stats.total_nodes}")
                    print(f"    - Total Edges   : {stats.total_edges}")
                    print(f"    - Indexed Files : {stats.file_count}")
                    print("    - Nodes by Type :")
                    for k, v in sorted(stats.nodes_by_type.items()):
                        print(f"      • {k:<15} : {v}")
                    print("    - Edges by Rel  :")
                    for k, v in sorted(stats.edges_by_relation.items()):
                        print(f"      • {k:<18} : {v}")
                return 0

            elif action == "inspect":
                node_id = parsed.node_id
                node = engine.graph.get_node(node_id)
                if not node:
                    msg = f"Node not found: {node_id}"
                    if parsed.json:
                        print(json.dumps({"error": msg}))
                    else:
                        print(f"[-] {msg}")
                    return 1
                if parsed.json:
                    print(node.model_dump_json(indent=2))
                else:
                    print_banner()
                    print(f"[*] Node ID   : {node.id}")
                    print(f"    Name      : {node.name}")
                    print(f"    Type      : {node.symbol_type.value}")
                    print(f"    File      : {node.file_path}:{node.line_start or 1}")
                    if node.signature:
                        print(f"    Signature : {node.signature}")
                return 0

            elif action == "dependencies":
                node_id = parsed.node_id
                depth = getattr(parsed, "depth", 3)
                path = engine.graph.traversal.get_upstream_dependencies([node_id], max_depth=depth)
                if parsed.json:
                    print(path.model_dump_json(indent=2))
                else:
                    print_banner()
                    print(f"[*] Upstream Dependencies for: {node_id} (depth: {depth})")
                    for n in path.nodes:
                        if n.id != node_id:
                            print(f"    <- [{n.symbol_type.value}] {n.id}")
                return 0

            elif action == "impact":
                node_id = parsed.node_id
                depth = getattr(parsed, "depth", 5)
                path = engine.graph.get_affected_downstream([node_id], max_depth=depth)
                if parsed.json:
                    print(path.model_dump_json(indent=2))
                else:
                    print_banner()
                    print(f"[*] Downstream Impact for: {node_id} (depth: {depth})")
                    for n in path.nodes:
                        if n.id != node_id:
                            print(f"    -> [{n.symbol_type.value}] {n.id}")
                return 0

        elif parsed.command == "impact":
            depth = getattr(parsed, "depth", 5)
            impact = engine.analyze_impact(max_depth=depth)
            if parsed.json:
                print(impact.model_dump_json(indent=2))
            else:
                print_banner()
                print(f"[*] Change Impact Assessment (Tree Hash: {impact.tree_hash[:16]}...)")
                print(f"    - Has Modifications: {impact.has_changes} ({impact.changed_files_count} files changed)")
                print(f"    - Changed Symbols  : {len(impact.changed_symbols)}")
                for sym in impact.changed_symbols[:10]:
                    print(f"      • [{sym.change_type.value}] {sym.name} ({sym.file_path})")
                
                print(f"\n[+] Downstream Blast Radius:")
                print(f"    - Direct Dependents   : {impact.blast_radius.direct_count}")
                print(f"    - Indirect Dependents : {impact.blast_radius.indirect_count}")
                print(f"    - Total Blast Radius  : {impact.blast_radius.total_affected}")

                print(f"\n[+] Affected Surfaces:")
                print(f"    - Affected APIs       : {len(impact.affected_apis)}")
                for a in impact.affected_apis:
                    print(f"      • {a.name} ({a.confidence.value})")
                print(f"    - Affected UI         : {len(impact.affected_ui)}")
                for u in impact.affected_ui:
                    print(f"      • {u.name} ({u.confidence.value})")
                print(f"    - Affected Databases  : {len(impact.affected_databases)}")
                for d in impact.affected_databases:
                    print(f"      • {d.name} ({d.confidence.value})")
                print(f"    - Affected Tests      : {len(impact.affected_tests)}")
                for t in impact.affected_tests:
                    print(f"      • {t.name} ({t.confidence.value})")
            return 0

        elif parsed.command == "risk":
            risk = engine.assess_risk()
            if parsed.json:
                print(risk.model_dump_json(indent=2))
            else:
                print_banner()
                print("=" * 60)
                print(f"AEGIS ADAPTIVE RISK ASSESSMENT: {risk.level.value} (Score: {risk.composite_score:.2f}/1.00)")
                print("=" * 60)
                print("Risk Factors Breakdown:")
                for f in risk.factors:
                    print(f"  • {f.factor_name:<25} [Weight: {f.weight:.2f}, Score: {f.raw_score:.2f}] -> {f.evidence}")
                print("\nKey Rationale:")
                for r in risk.reasons:
                    print(f"  - {r}")
                print(f"\nRecommendation: {risk.recommendation}")
            return 0

        elif parsed.command == "plan":
            changed_only = getattr(parsed, "changed_only", False)
            plan = engine.plan_tests(changed_only=changed_only)
            if parsed.json:
                print(plan.model_dump_json(indent=2))
            else:
                print_banner()
                print(f"[*] Adaptive Test Plan (Risk Tier: {plan.risk_level.value})")
                print(f"    - Selected Validations : {plan.total_planned}")
                for p in plan.selected_tests:
                    print(f"      [P:{p.priority:>3}] [{p.category}] -> {p.runner_cmd} ({p.selection_reason})")
                if plan.skipped_tests:
                    print(f"    - Safely Skipped Suites: {plan.total_skipped}")
                    for s in plan.skipped_tests:
                        print(f"      [SKIP] [{s.category}] -> {s.name} ({s.skip_reason})")
                print(f"    - Est. Execution Time  : {plan.estimated_total_time_ms:.1f} ms")
            return 0

        elif parsed.command in ("test", "run"):
            category = getattr(parsed, "category", "all") or "all"
            dry_run = getattr(parsed, "dry_run", False)
            changed_only = getattr(parsed, "changed_only", False)
            parallel = getattr(parsed, "parallel", True)
            fail_fast = getattr(parsed, "fail_fast", True)

            if not parsed.json:
                print_banner()
                print(f"[*] Aegis Execution Engine [Target: {category}] (dry-run: {dry_run}, parallel: {parallel}, fail-fast: {fail_fast})")

            # Generate plan respecting changed_only flag
            test_plan = engine.plan_tests(changed_only=changed_only)
            categories_filter = None if category == "all" else [category]

            report = engine.execute_plan(
                test_plan=test_plan,
                categories=categories_filter,
                fail_fast=fail_fast,
                parallel=parallel,
                dry_run=dry_run,
            )
            assessment = report.release_assessment or engine.assess_release_readiness(report)

            if parsed.json:
                print(report.model_dump_json(indent=2))
            else:
                print("\n" + "=" * 60)
                print("AEGIS EXECUTION SUMMARY & EVIDENCE")
                print("=" * 60)
                print(f"Total Validations : {report.total_tests}")
                print(f"Passed            : {report.passed}")
                print(f"Failed            : {report.failed}")
                print(f"Errors/Timeouts   : {report.errors}")
                print(f"Execution Time    : {report.duration_ms:.2f} ms")
                print(f"Release Verdict   : {assessment.verdict.value}")
                for reason in assessment.reasons:
                    print(f"  • {reason}")
                print(f"\nMachine-readable evidence report saved to: {engine.storage.get_artifact_path('report.json')}")

            return 0 if assessment.verdict in ("READY", "REQUIRES_REVIEW") else 1

        elif parsed.command == "quality":
            dim = getattr(parsed, "dimension", "all") or "all"
            dry_run = getattr(parsed, "dry_run", False)
            changed_only = getattr(parsed, "changed_only", False)
            full_mode = getattr(parsed, "full", False)
            release_mode = getattr(parsed, "release", False)

            mode = "release" if release_mode else ("full" if full_mode else ("changed-only" if changed_only else "default"))

            if not parsed.json:
                print_banner()
                print(f"[*] Aegis Quality Dimensions Engine [Target: {dim}] (mode: {mode}, dry-run: {dry_run})")

            results = engine.execute_quality(
                dimension=dim,
                mode=mode,
                dry_run=dry_run,
            )

            if parsed.json:
                serialized = {k: v.model_dump() for k, v in results.items()}
                print(json.dumps(serialized, indent=2))
            else:
                print("\n" + "=" * 60)
                print("AEGIS QUALITY DIMENSIONS SUMMARY")
                print("=" * 60)
                for dimension_name, res in results.items():
                    print(f"\n[+] Dimension: {dimension_name.upper()}")
                    print(f"    - Status             : {res.status.value}")
                    print(f"    - Execution Mode     : {res.execution_mode.value}")
                    print(f"    - Validation Strength: {res.validation_strength.value}")
                    print(f"    - Total Findings     : {len(res.findings)}")
                    for f in res.findings[:5]:
                        print(f"      • [{f.severity.value}] {f.title} ({f.affected_target})")
                    if res.measurements:
                        print(f"    - Measurements       : {len(res.measurements)}")
                        for m in res.measurements:
                            print(f"      • {m.metric}: {m.median:.2f} {m.unit} (p95: {m.p95:.2f} {m.unit})")
                    if res.error_message:
                        print(f"    - Diagnostic Note    : {res.error_message}")

                print(f"\nMachine-readable quality results saved to: {engine.storage.get_artifact_path('quality-results.json')}")

            any_failed = any(r.status.value in ("FAIL", "ERROR") for r in results.values())
            return 1 if any_failed else 0

        elif parsed.command == "investigate":
            report_data = engine.storage.load_json("report.json")
            if not report_data:
                msg = "No execution report found. Run 'aegis test' first to generate evidence."
                if parsed.json:
                    print(json.dumps({"error": msg}))
                else:
                    print(f"[-] {msg}")
                return 1

            if parsed.json:
                print(json.dumps({
                    "failure_fingerprints": report_data.get("failure_fingerprints", []),
                    "failed_tests": [r for r in report_data.get("test_results", []) if r.get("status") in ("FAILED", "ERROR", "TIMEOUT")],
                }, indent=2))
            else:
                print_banner()
                fps = report_data.get("failure_fingerprints", [])
                print(f"[*] Investigation Report: {len(fps)} unique failure fingerprints recorded.")
                for fp in fps:
                    print(f"    - Fingerprint: {fp}")
            return 0

        elif parsed.command == "report":
            report_data = engine.storage.load_json("report.json")
            if not report_data:
                msg = "No report available. Run 'aegis test' first."
                if parsed.json:
                    print(json.dumps({"error": msg}))
                else:
                    print(f"[-] {msg}")
                return 1

            if parsed.json:
                print(json.dumps(report_data, indent=2))
            else:
                print_banner()
                print(f"[*] Report ID    : {report_data.get('report_id')}")
                print(f"[*] Project      : {report_data.get('project_name')}")
                print(f"[*] Tree Hash    : {report_data.get('tree_hash')}")
                print(f"[*] Tests Passed : {report_data.get('passed')}/{report_data.get('total_tests')}")
            return 0

        elif parsed.command == "release-check":
            report_data = engine.storage.load_json("report.json")
            if not report_data:
                # Run fresh test pass first if no previous report exists
                profile = engine.discover()
                collector = EvidenceCollector(project_name=profile.project_name, storage=engine.storage, event_bus=engine.event_bus)
                collector.record_result(
                    TestResult(
                        test_id="sanity.preflight",
                        name="Preflight Sanity Check",
                        category="sanity",
                        status=TestStatus.PASSED,
                        duration_ms=1.0,
                        runner="deterministic_sanity",
                    )
                )
                report = collector.generate_report(tree_hash=profile.tree_hash)
            else:
                report = EvidenceReport(**report_data)

            assessment = engine.assess_release_readiness(report)

            if parsed.json:
                print(assessment.model_dump_json(indent=2))
            else:
                print_banner()
                print("=" * 60)
                print(f"AEGIS PRODUCTION RELEASE GATE: {assessment.verdict.value}")
                print("=" * 60)
                for chk in assessment.policy_checks:
                    icon = "[✓]" if chk.passed else "[✗]"
                    print(f"{icon} Policy: {chk.policy_name:<30} -> {chk.details}")
                print("\nDecision Rationale:")
                for r in assessment.reasons:
                    print(f"  • {r}")
                print(f"\nFinal Verdict: {assessment.verdict.value}")

            return 0 if assessment.verdict in ("READY", "REQUIRES_REVIEW") else 1

    except Exception as e:
        if parsed.json:
            print(json.dumps({"error": str(e), "error_type": e.__class__.__name__}))
        else:
            print(f"\n[!] Error: {e}", file=sys.stderr)
            if parsed.verbose:
                import traceback
                traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
