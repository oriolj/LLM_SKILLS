"""Run hermes update's post-swap tail on a checkout that was moved to a tag by hand.

Mirrors hermes_cli.update_cmd._finish_pulled_update (v2026.9.24) minus the git
pull, the desktop rebuild and the gateway restart (systemd unit handled outside).
Usage: venv/bin/python hermes_post_checkout.py <pre_pull_sha> <pre_update_version>
"""
import os
import sys

os.chdir(os.path.expanduser("~/.hermes/hermes-agent"))
sys.path.insert(0, os.getcwd())

from hermes_cli import update_cmd  # noqa: E402
from hermes_cli.update_cmd import _m  # noqa: E402

pre_sha, pre_version = sys.argv[1], sys.argv[2]
git_cmd = update_cmd._ensure_non_trampoline_git(update_cmd._base_git_cmd())

active_lazy = _m()._capture_active_lazy_features()
active_tools = _m()._capture_active_tool_dependencies()
print(f"active lazy features: {active_lazy}")
print(f"active tool deps: {active_tools}")

update_cmd._sync_python_dependencies_after_pull(
    git_cmd, "main", pre_sha,
    active_lazy_features=active_lazy, active_tool_dependencies=active_tools,
    _windows_gateway_resume=None)

node_failures = update_cmd._update_node_dependencies()
_m()._build_web_ui(_m().PROJECT_ROOT / "web")

from hermes_cli.update_cmd_maint import _run_post_update_maintenance  # noqa: E402

ok = _run_post_update_maintenance(
    assume_yes=True, gateway_mode=False, pre_update_snapshot_id=None,
    had_desktop_app_before_update=False, node_failures=node_failures,
    desktop_build_ok=True, pre_update_version=pre_version)
print(f"POST-CHECKOUT update_complete={ok} node_failures={node_failures}")
# ok is False on node failures too (_print_update_summary); exit non-zero so the
# caller's set -o pipefail stops before restarting the gateway.
sys.exit(0 if ok else 1)
