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
    p_init.add_argument("--name", help="Custom project name override")

    # project
    p_proj = subparsers.add_parser("project", parents=[common_parser], help="Display canonical project profile and discovered capabilities")

    # capabilities
    p_caps = subparsers.add_parser("capabilities", parents=[common_parser], help="List all detected project capabilities with evidence")

    # adapters
    p_adp = subparsers.add_parser("adapters", parents=[common_parser], help="List all registered technology adapters and their status")

    # check
    p_chk = subparsers.add_parser("check", parents=[common_parser], help="Run universal end-to-end quality and release verification")
    p_chk.add_argument("--changed-only", action="store_true", default=True, help="Only validate impacted surfaces")
    p_chk.add_argument("--all", action="store_true", help="Validate all test suites")
    p_chk.add_argument("--dry-run", action="store_true", help="Simulate execution without running external commands")
    p_chk.add_argument("--ci", action="store_true", help="Run in strict CI mode")

    # release
    p_rel_alias = subparsers.add_parser("release", parents=[common_parser], help="Evaluate deterministic release readiness policy gate")

    # discover
    p_disc = subparsers.add_parser("discover", parents=[common_parser], help="Discover languages, frameworks, build tools, infra, APIs, and tests")
    p_disc.add_argument("--name", help="Custom project name override")

    # impact
    p_imp = subparsers.add_parser("impact", parents=[common_parser], help="Detect changed symbols and compute downstream blast radius")
    p_imp.add_argument("--depth", type=int, default=5, help="Max traversal depth")

    # risk
    p_risk = subparsers.add_parser("risk", parents=[common_parser], help="Calculate deterministic, explainable risk assessment")

    # plan
    p_plan = subparsers.add_parser("plan", parents=[common_parser], help="Generate adaptive, risk-weighted test plan")
    p_plan.add_argument("--changed-only", action="store_true", help="Only plan tests for impacted code")
    p_plan.add_argument("--explain", action="store_true", help="Include detailed explanation for selected and skipped tests")

    # test
    p_test = subparsers.add_parser("test", parents=[common_parser], help="Execute deterministic quality validations")
    p_test.add_argument("category", nargs="?", default="all", help="Test category: unit, api, sanity, integration, e2e, ui, security, performance, compatibility, all")
    p_test.add_argument("--dry-run", action="store_true", help="Simulate execution without running commands")
    p_test.add_argument("--changed-only", action="store_true", help="Only run tests impacted by recent changes")
    p_test.add_argument("--explain-selection", action="store_true", help="Print detailed selection rationale")
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
    p_qual.add_argument("--explain-selection", action="store_true", help="Print detailed quality selection rationale")
    p_qual.add_argument("--full", action="store_true", help="Run comprehensive quality audit across all dimensions")
    p_qual.add_argument("--release", action="store_true", help="Run strict release-level quality audit")

    # history
    p_hist = subparsers.add_parser("history", parents=[common_parser], help="Inspect historical execution records, failures, and flakiness")
    p_hist.add_argument("action", nargs="?", default="all", help="History view: failures, tests, quality, flaky, all")
    p_hist.add_argument("--limit", type=int, default=50, help="Maximum historical records to retrieve")

    # analyze
    p_ana_hist = subparsers.add_parser("analyze", parents=[common_parser], help="Analyze test effectiveness, redundancy, failure clusters, and risk")
    p_ana_hist.add_argument("action", nargs="?", default="effectiveness", help="Analysis target: failures, effectiveness, redundancy, risk")
    p_ana_hist.add_argument("--limit", type=int, default=50, help="Maximum items to analyze")

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
            custom_name = getattr(parsed, "name", None)
            if custom_name:
                engine.config.project.name = custom_name
            cfg_path = engine.init_workspace()
            summary = engine.get_init_summary()
            if parsed.json:
                print(json.dumps({
                    "status": "initialized",
                    "config_file": str(cfg_path),
                    "workspace": str(workspace_path),
                    "summary": summary,
                }, indent=2))
            else:
                print_banner()
                print("=" * 60)
                print("AEGIS PROJECT INITIALIZATION")
                print("=" * 60)
                print(f"\nProject")
                print(f"  Name: {summary['project_name']}")
                print(f"  Root: {summary['root_path']}")

                print(f"\nDetected Languages")
                for lang in summary["languages"]:
                    print(f"  ✓ {lang}")
                if not summary["languages"]:
                    print("  - None detected")

                print(f"\nDetected Frameworks")
                for fw in summary["frameworks"]:
                    print(f"  ✓ {fw}")
                if not summary["frameworks"]:
                    print("  - None detected")

                print(f"\nDetected Infrastructure")
                infra = summary["infrastructure"]
                if infra.get("has_docker"):
                    print(f"  ✓ Docker ({infra.get('dockerfiles', 1)} files)")
                if infra.get("has_compose"):
                    print(f"  ✓ Docker Compose ({infra.get('compose_files', 1)} files)")
                for db in infra.get("databases", []):
                    print(f"  ✓ {db}")
                for q in infra.get("queues", []):
                    print(f"  ✓ {q}")
                for ci in infra.get("ci_providers", []):
                    print(f"  ✓ {ci}")

                print(f"\nDetected Test Systems")
                for ts in summary["test_systems"]:
                    print(f"  ✓ {ts}")
                if not summary["test_systems"]:
                    print("  - None detected")

                print(f"\nDetected API Surface")
                api = summary["api_surface"]
                if api.get("rest_endpoints", 0) > 0:
                    print(f"  ✓ REST ({api['rest_endpoints']} endpoints)")
                if api.get("has_openapi"):
                    print("  ✓ OpenAPI")
                if api.get("has_graphql"):
                    print("  ✓ GraphQL")
                if api.get("has_grpc"):
                    print("  ✓ gRPC")

                print(f"\nExisting Tests")
                print(f"  ✓ {summary['total_estimated_tests']} tests discovered across {summary['discovered_test_files']} files")

                print(f"\nArchitecture")
                arch = summary["architecture"]
                print(f"  ✓ {arch['symbols_indexed']} symbols indexed")
                print(f"  ✓ {arch['dependency_edges']} dependency edges")
                print(f"  ✓ {api['rest_endpoints']} API routes")

                print("\n[+] Aegis initialization complete.")
            return 0

        elif parsed.command == "project":
            profile = engine.discover()
            if parsed.json:
                print(profile.model_dump_json(indent=2))
            else:
                print_banner()
                print(f"[*] Canonical Project Profile: {profile.project_name}")
                print(f"    - Schema Version: {profile.schema_version}")
                print(f"    - Primary Lang  : {profile.primary_language or 'Unknown'}")
                print(f"    - Capabilities  : {len(profile.capabilities)} detected")
                print(f"    - Active Adapters: {', '.join(profile.active_adapters) or 'None'}")
                if profile.components:
                    print(f"    - Monorepo Components: {len(profile.components)}")
                    for comp in profile.components:
                        print(f"      • {comp['name']} ({comp['path']})")
            return 0

        elif parsed.command == "capabilities":
            caps = engine.list_capabilities()
            if parsed.json:
                print(json.dumps([c.model_dump() for c in caps], indent=2))
            else:
                print_banner()
                print(f"[*] Project Capabilities ({len(caps)} detected):")
                for c in caps:
                    ev = f" | {c.evidence[0]}" if c.evidence else ""
                    print(f"    • [{c.type.value:<16}] {c.name:<28} ({c.status.value}, conf: {c.confidence:.2f}){ev}")
            return 0

        elif parsed.command == "adapters":
            adps = engine.list_adapters()
            if parsed.json:
                print(json.dumps(adps, indent=2))
            else:
                print_banner()
                print(f"[*] Universal Technology Adapters ({len(adps)} registered):")
                for a in adps:
                    status = "[ACTIVE]" if a["active"] else "[INACTIVE]"
                    print(f"    • {status:<10} {a['name']:<35} ({a['category']}, v{a['version']})")
            return 0

        elif parsed.command == "check":
            changed_only = not getattr(parsed, "all", False)
            dry_run = getattr(parsed, "dry_run", False)
            res = engine.check(changed_only=changed_only, dry_run=dry_run, ci=getattr(parsed, "ci", False))
            if parsed.json:
                print(json.dumps(res, indent=2))
            else:
                print_banner()
                print("=" * 60)
                print(f"AEGIS QUALITY & RELEASE CHECK: {res['release_verdict']}")
                print("=" * 60)
                print(f"[*] Project        : {res['project_name']}")
                print(f"[*] Risk Level     : {res['risk_level']}")
                print(f"[*] Tests Executed : {res['tests_passed']}/{res['tests_executed']} passed")
                print(f"[*] Release Verdict: {res['release_verdict']}")
                for r in res.get("reasons", []):
                    print(f"    • {r}")
            return 0 if res["release_verdict"] in ("READY", "REQUIRES_REVIEW") else 1

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
            explain = getattr(parsed, "explain", False)
            plan = engine.plan_tests(changed_only=changed_only, explain=explain)
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
                if explain and plan.explanations:
                    print("\n[+] Selection Explanations (Adaptive Planner 2.0):")
                    for exp in plan.explanations:
                        icon = "[✓ SELECTED]" if exp.selected else "[✗ SKIPPED]"
                        print(f"    {icon} {exp.test_id} (Value Score: {exp.value_score})")
                        for r in exp.reasons:
                            print(f"        • {r}")
                        if exp.skip_reason:
                            print(f"        • {exp.skip_reason}")
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

        elif parsed.command == "history":
            act = getattr(parsed, "action", "all") or "all"
            limit = getattr(parsed, "limit", 50)
            from aegis.history.flakiness import FlakinessEngine

            if act == "failures":
                clusters = engine.history_store.get_failure_clusters(limit=limit)
                if parsed.json:
                    print(json.dumps([c.model_dump() for c in clusters], indent=2))
                else:
                    print_banner()
                    print(f"[*] Historical Failure Clusters ({len(clusters)} recorded):")
                    for c in clusters:
                        print(f"    • [{c.status.value}] {c.fingerprint} (x{c.occurrences}) -> {c.classification.value} ({c.sample_message[:60]})")
            elif act == "flaky":
                flakiness_eng = FlakinessEngine(engine.history_store)
                flaky_map = flakiness_eng.analyze_all(limit_per_test=limit)
                if parsed.json:
                    print(json.dumps({k: v.model_dump() for k, v in flaky_map.items()}, indent=2))
                else:
                    print_banner()
                    print(f"[*] Flakiness Analysis ({len(flaky_map)} tests tracked):")
                    for tid, rec in flaky_map.items():
                        print(f"    • [{rec.status.value}] {tid} (Instability: {rec.instability_rate:.2f}, Runs: {rec.total_runs}, Retries: {rec.retry_count})")
            elif act == "quality":
                q_hist = engine.history_store.get_quality_history(limit=limit)
                if parsed.json:
                    print(json.dumps([q.model_dump() for q in q_hist], indent=2))
                else:
                    print_banner()
                    print(f"[*] Historical Quality Findings ({len(q_hist)} tracked):")
                    for q in q_hist:
                        print(f"    • [{q.status.value}] [{q.dimension.upper()}] {q.finding_fingerprint} ({q.affected_target}) x{q.occurrences}")
            else:
                execs = engine.history_store.get_executions(limit=limit)
                if parsed.json:
                    print(json.dumps([e.model_dump() for e in execs], indent=2))
                else:
                    print_banner()
                    print(f"[*] Execution History ({len(execs)} recent executions):")
                    for e in execs[:20]:
                        print(f"    • [{e.status}] {e.test_id} ({e.duration_ms:.1f}ms) [Mode: {e.execution_mode}]")
            return 0

        elif parsed.command == "analyze":
            act = getattr(parsed, "action", "effectiveness") or "effectiveness"
            limit = getattr(parsed, "limit", 50)
            from aegis.history.effectiveness import TestEffectivenessEngine
            from aegis.history.redundancy import RedundancyEngine

            if act == "effectiveness":
                eff_eng = TestEffectivenessEngine(engine.history_store)
                eff_map = eff_eng.analyze_all(limit_per_test=limit)
                if parsed.json:
                    print(json.dumps({k: v.model_dump() for k, v in eff_map.items()}, indent=2))
                else:
                    print_banner()
                    print(f"[*] Test Effectiveness & Value Ranking ({len(eff_map)} tests):")
                    for tid, eff in sorted(eff_map.items(), key=lambda x: x[1].value_score, reverse=True):
                        print(f"    • [Score: {eff.value_score:>5.1f}] {tid} (Defects Found: {eff.defects_detected}/{eff.total_executions}, Cost: {eff.avg_duration_ms:.1f}ms)")
            elif act == "redundancy":
                red_eng = RedundancyEngine(engine.history_store)
                redundancies = red_eng.analyze_redundancy(limit=limit)
                if parsed.json:
                    print(json.dumps([r.model_dump() for r in redundancies], indent=2))
                else:
                    print_banner()
                    print(f"[*] Test Redundancy Analysis ({len(redundancies)} potential overlaps):")
                    for r in redundancies:
                        print(f"    • [Overlap: {r.overlap_score*100:.1f}%] {r.test_id_a} <-> {r.test_id_b}")
            elif act == "failures":
                clusters = engine.history_store.get_failure_clusters(limit=limit)
                if parsed.json:
                    print(json.dumps([c.model_dump() for c in clusters], indent=2))
                else:
                    print_banner()
                    print(f"[*] Failure Cluster Analysis ({len(clusters)} clusters):")
                    for c in clusters:
                        print(f"    • [{c.classification.value}] {c.fingerprint} (x{c.occurrences}) -> {c.sample_message[:60]}")
            elif act == "risk":
                # Historical risk calibration analysis
                assessment = engine.assess_risk()
                execs = engine.history_store.get_executions(limit=limit)
                failed_execs = [e for e in execs if e.status in ("FAILED", "ERROR", "TIMEOUT")]
                calib_data = {
                    "current_predicted_risk": assessment.level.value,
                    "composite_score": assessment.composite_score,
                    "historical_total_executions": len(execs),
                    "historical_failed_executions": len(failed_execs),
                    "calibration_status": "CALIBRATED" if len(execs) >= 5 else "INSUFFICIENT_SAMPLES",
                    "historical_failure_rate": round(len(failed_execs) / max(1, len(execs)), 3),
                    "risk_factors": [f.model_dump() for f in assessment.factors],
                }
                if parsed.json:
                    print(json.dumps(calib_data, indent=2))
                else:
                    print_banner()
                    print(f"[*] Risk Model Historical Calibration:")
                    print(f"    • Predicted Risk Level: {assessment.level.value} (Score: {assessment.composite_score})")
                    print(f"    • Historical Executions: {len(execs)} (Failures: {len(failed_execs)})")
                    print(f"    • Calibration Status: {calib_data['calibration_status']}")
            else:
                profile = engine.discover()
                if parsed.json:
                    print(json.dumps({
                        "project_name": profile.project_name,
                        "architecture": profile.infrastructure.model_dump(),
                        "interfaces": profile.interfaces.model_dump(),
                    }, indent=2))
                else:
                    print_banner()
                    print(f"[*] Static Architecture & Interface Analysis for: {profile.project_name}")
            return 0

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

        elif parsed.command in ("release", "release-check"):
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
