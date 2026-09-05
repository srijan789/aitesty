import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

def generate_html_report(
    results_data: Dict[str, Any],
    project_name: str = "Project",
    target_url: str = "",
    run_id: str = "",
    raw_logs: str = "",
) -> str:
    """
    Synthesizes a self-contained, responsive HTML test report with
    failure classification (App Defect vs Automation Failure),
    step execution timelines, screenshots, and healer metadata.
    """
    summary = results_data.get("summary", {})
    total = summary.get("total", 0)
    passed = summary.get("passed", 0)
    failed = summary.get("failed", 0)
    skipped = summary.get("skipped", 0)
    duration_ms = summary.get("duration_ms", 0)
    app_defects = summary.get("app_defects", 0)
    automation_failures = summary.get("automation_failures", 0)

    pass_rate = round((passed / total * 100), 1) if total > 0 else 0
    tests = results_data.get("tests", [])

    tests_html = []
    for idx, t in enumerate(tests, 1):
        status = t.get("status", "passed").lower()
        test_name = t.get("test_name", f"Test {idx}")
        dur = t.get("duration_ms", 0)
        scenario_id = t.get("scenario_id") or ""
        error_details = t.get("error_details") or {}
        steps = t.get("steps") or []
        screenshot = t.get("screenshot_path") or ""

        classification_info = error_details.get("classification") or {}
        class_type = classification_info.get("classification", "")
        subtype = classification_info.get("subtype", "")
        summary_text = classification_info.get("summary", "")
        root_cause = classification_info.get("root_cause_analysis", "")
        healing_action = classification_info.get("healing_action", "")
        healing_context = classification_info.get("healing_context") or {}

        if status == "passed":
            status_badge = '<span class="px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">PASSED</span>'
            card_border = "border-slate-200"
        elif class_type == "APP_DEFECT":
            status_badge = '<span class="px-2.5 py-1 rounded-full text-xs font-bold bg-rose-100 text-rose-800 border border-rose-200">APP DEFECT (BUG)</span>'
            card_border = "border-rose-300 bg-rose-50/20"
        elif class_type == "AUTOMATION_FAILURE":
            status_badge = '<span class="px-2.5 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-800 border border-amber-200">AUTOMATION FAILURE</span>'
            card_border = "border-amber-300 bg-amber-50/20"
        else:
            status_badge = f'<span class="px-2.5 py-1 rounded-full text-xs font-bold bg-rose-100 text-rose-800 border border-rose-200">{status.upper()}</span>'
            card_border = "border-rose-300"

        # Steps list
        steps_markup = ""
        if steps:
            steps_items = []
            for s in steps:
                st_num = s.get("step_number", 1)
                st_act = s.get("action", "")
                st_tgt = s.get("target", "")
                st_out = s.get("outcome", "")
                st_dur = s.get("duration_ms", 0)
                target_span = f'<code class="bg-slate-100 px-1 py-0.5 rounded text-indigo-600">{st_tgt}</code>' if st_tgt else ""
                steps_items.append(f"""
                <li class="flex items-start justify-between text-xs py-1 border-b border-slate-100 last:border-0">
                    <div>
                        <span class="font-mono text-slate-400 mr-2">{st_num}.</span>
                        <span class="font-semibold text-slate-700">{st_act}</span> {target_span}
                        <span class="text-slate-500 text-[11px]">&rarr; {st_out}</span>
                    </div>
                    <span class="font-mono text-[10px] text-slate-400">{st_dur}ms</span>
                </li>
                """)
            steps_markup = f"""
            <div class="mt-3">
                <div class="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1">Execution Steps</div>
                <ul class="bg-slate-50 rounded-lg p-2.5 space-y-1">
                    {''.join(steps_items)}
                </ul>
            </div>
            """

        # Failure diagnostics block
        diag_markup = ""
        if status != "passed" and error_details:
            err_msg = error_details.get("error_message", "")
            traceback = error_details.get("traceback", "")

            screenshot_embed = ""
            if screenshot:
                screenshot_embed = f"""
                <div class="mt-2">
                    <span class="text-[11px] font-bold text-slate-600 block mb-1">Failure State Screenshot:</span>
                    <a href="{screenshot}" target="_blank">
                        <img src="{screenshot}" alt="Failure Screenshot" class="max-h-48 rounded border border-slate-300 shadow-xs hover:opacity-90 transition"/>
                    </a>
                </div>
                """

            diag_markup = f"""
            <div class="mt-3 p-3 rounded-lg border {'border-rose-200 bg-rose-50/60' if class_type == 'APP_DEFECT' else 'border-amber-200 bg-amber-50/60'} text-xs space-y-2">
                <div class="flex items-center justify-between">
                    <span class="font-bold text-slate-800">Diagnostic Root Cause:</span>
                    <span class="font-mono text-[11px] font-semibold px-2 py-0.5 rounded bg-white border border-slate-200">{subtype or 'FAILURE'}</span>
                </div>
                <p class="text-slate-700 leading-relaxed">{root_cause or err_msg}</p>
                
                {f'''<div class="p-2 bg-white rounded border border-slate-200">
                    <span class="font-semibold text-indigo-700 block text-[11px]">Recommended Healer Action: <code class="font-mono">{healing_action}</code></span>
                    <pre class="text-[10px] text-slate-600 mt-1 font-mono overflow-x-auto whitespace-pre-wrap">{json.dumps(healing_context, indent=2)}</pre>
                </div>''' if healing_context else ''}

                <details class="cursor-pointer text-[11px] text-slate-500">
                    <summary class="font-semibold hover:text-slate-800">View Stack Trace</summary>
                    <pre class="mt-1 p-2 bg-slate-900 text-slate-200 rounded font-mono text-[10px] overflow-x-auto whitespace-pre-wrap">{traceback or err_msg}</pre>
                </details>

                {screenshot_embed}
            </div>
            """

        tests_html.append(f"""
        <div class="rounded-xl border {card_border} p-4 shadow-sm bg-white transition hover:shadow-md">
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-3">
                <div class="flex items-center space-x-3">
                    <span class="font-mono text-xs text-slate-400">#{idx}</span>
                    <h4 class="text-sm font-bold text-slate-900 font-mono">{test_name}</h4>
                </div>
                <div class="flex items-center space-x-3">
                    <span class="font-mono text-xs text-slate-500">{dur} ms</span>
                    {status_badge}
                </div>
            </div>
            {steps_markup}
            {diag_markup}
        </div>
        """)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Run Report - {project_name}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css"/>
</head>
<body class="bg-slate-50 text-slate-800 font-sans p-4 md:p-8">
    <div class="max-w-6xl mx-auto space-y-6">
        <!-- Header Banner -->
        <header class="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div class="space-y-1">
                <div class="flex items-center space-x-2">
                    <span class="w-3 h-3 rounded-full bg-indigo-600"></span>
                    <h1 class="text-xl font-black tracking-tight text-slate-900">Aitesty Execution & Quality Report</h1>
                </div>
                <div class="flex flex-wrap items-center gap-3 text-xs text-slate-500">
                    <span>Project: <strong>{project_name}</strong></span>
                    <span>&bull;</span>
                    <span>Target: <a href="{target_url}" target="_blank" class="text-indigo-600 hover:underline">{target_url}</a></span>
                    <span>&bull;</span>
                    <span>Run ID: <code class="bg-slate-100 px-1 py-0.5 rounded font-mono">{run_id}</code></span>
                    <span>&bull;</span>
                    <span>Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</span>
                </div>
            </div>
            <div>
                <span class="inline-flex items-center px-3 py-1.5 rounded-xl text-xs font-bold {'bg-emerald-50 text-emerald-700 border border-emerald-200' if failed == 0 else 'bg-rose-50 text-rose-700 border border-rose-200'}">
                    <i class="fa-solid {'fa-circle-check text-emerald-500' if failed == 0 else 'fa-triangle-exclamation text-rose-500'} mr-1.5"></i>
                    {'ALL TESTS PASSED' if failed == 0 else f'{failed} TEST(S) FAILED'}
                </span>
            </div>
        </header>

        <!-- KPI Summary Cards -->
        <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
                <div class="text-[11px] font-semibold text-slate-400 uppercase">Total Tests</div>
                <div class="text-2xl font-black text-slate-900 mt-1">{total}</div>
            </div>
            <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
                <div class="text-[11px] font-semibold text-emerald-600 uppercase">Passed</div>
                <div class="text-2xl font-black text-emerald-600 mt-1">{passed}</div>
            </div>
            <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
                <div class="text-[11px] font-semibold text-slate-400 uppercase">Pass Rate</div>
                <div class="text-2xl font-black text-slate-900 mt-1">{pass_rate}%</div>
            </div>
            <div class="bg-white p-4 rounded-xl border border-rose-200 bg-rose-50/20 shadow-xs">
                <div class="text-[11px] font-bold text-rose-700 uppercase flex items-center">
                    <i class="fa-solid fa-bug mr-1"></i>App Defects
                </div>
                <div class="text-2xl font-black text-rose-700 mt-1">{app_defects}</div>
            </div>
            <div class="bg-white p-4 rounded-xl border border-amber-200 bg-amber-50/20 shadow-xs">
                <div class="text-[11px] font-bold text-amber-700 uppercase flex items-center">
                    <i class="fa-solid fa-wrench mr-1"></i>Auto Failures
                </div>
                <div class="text-2xl font-black text-amber-700 mt-1">{automation_failures}</div>
            </div>
            <div class="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
                <div class="text-[11px] font-semibold text-slate-400 uppercase">Duration</div>
                <div class="text-2xl font-black text-slate-900 mt-1">{round(duration_ms / 1000, 2)}s</div>
            </div>
        </div>

        <!-- Failure Diagnosis Summary Banner -->
        {f'''
        <div class="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-3">
            <h3 class="text-sm font-bold text-slate-900 flex items-center">
                <i class="fa-solid fa-stethoscope text-indigo-600 mr-2"></i>Failure Diagnosis & Healing Telemetry
            </h3>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                <div class="p-3 rounded-lg border border-rose-200 bg-rose-50/50">
                    <div class="font-bold text-rose-900 mb-1 flex items-center">
                        <i class="fa-solid fa-triangle-exclamation mr-1.5 text-rose-600"></i>Genuine Application Defects ({app_defects})
                    </div>
                    <p class="text-rose-700 text-[11px] leading-relaxed">
                        Failures triggered by HTTP 5xx responses, client-side JS runtime exceptions, or functional assertion violations. These reflect real defects in the web application under test.
                    </p>
                </div>
                <div class="p-3 rounded-lg border border-amber-200 bg-amber-50/50">
                    <div class="font-bold text-amber-900 mb-1 flex items-center">
                        <i class="fa-solid fa-wand-magic-sparkles mr-1.5 text-amber-600"></i>Automation / Script Failures ({automation_failures})
                    </div>
                    <p class="text-amber-700 text-[11px] leading-relaxed">
                        Failures caused by locator timeouts, selector drift, or DOM restructuring. These cases contain structured telemetry and can be repaired automatically by the <strong>Healer Sub-Agent</strong>.
                    </p>
                </div>
            </div>
        </div>
        ''' if failed > 0 else ''}

        <!-- Test Results Section -->
        <section class="space-y-4">
            <div class="flex items-center justify-between">
                <h3 class="text-sm font-bold uppercase tracking-wider text-slate-600">Executed Scenarios ({len(tests)})</h3>
            </div>
            <div class="space-y-3">
                {''.join(tests_html)}
            </div>
        </section>

        {f'''
        <!-- Complete Execution Logs Console -->
        <section class="bg-slate-900 rounded-xl border border-slate-800 p-5 shadow-xs text-slate-100 space-y-3">
            <div class="flex items-center justify-between cursor-pointer select-none" onclick="const c = document.getElementById('report-raw-logs'); c.classList.toggle('hidden');">
                <h3 class="text-sm font-bold flex items-center">
                    <i class="fa-solid fa-terminal text-emerald-400 mr-2"></i>Execution Logs Console
                </h3>
                <span class="text-xs text-slate-400 font-mono hover:text-white">Toggle Full Log &darr;</span>
            </div>
            <pre id="report-raw-logs" class="font-mono text-xs text-emerald-400 bg-slate-950 p-4 rounded-lg overflow-x-auto whitespace-pre-wrap max-h-96">{raw_logs}</pre>
        </section>
        ''' if raw_logs else ''}
        
        <footer class="text-center text-xs text-slate-400 pt-6">
            Synthesized by Aitesty Autonomous Test Orchestration Platform
        </footer>
    </div>
</body>
</html>"""
    return html_content


def save_run_report(
    project_id: str,
    run_id: str,
    results_dict: Dict[str, Any],
    workspace_manager,
    project_name: str = "Project",
    target_url: str = "",
    raw_logs: str = "",
) -> Dict[str, str]:
    """
    Saves results.json and report.html inside the run workspace directory:
    workspaces/<project_id>/runs/<run_id>/results.json
    workspaces/<project_id>/runs/<run_id>/report.html
    """
    run_dir = workspace_manager.get_run_dir(project_id, run_id)
    run_dir.mkdir(parents=True, exist_ok=True)

    json_path = run_dir / "results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results_dict, f, indent=2)

    if not raw_logs:
        exec_log_file = run_dir / "execution.log"
        if exec_log_file.exists():
            try:
                raw_logs = exec_log_file.read_text(encoding="utf-8")
            except Exception:
                raw_logs = ""

    html_content = generate_html_report(
        results_data=results_dict,
        project_name=project_name,
        target_url=target_url,
        run_id=run_id,
        raw_logs=raw_logs,
    )

    html_path = run_dir / "report.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return {
        "json_path": str(json_path),
        "html_path": str(html_path),
    }
