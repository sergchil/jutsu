"""Fit-audit checks for the poteto-mode router and playbooks on a built plugin dir.

Usage: python3 test_fit_playbooks.py <built plugin dir>
Each check names the audit item it covers. Exit 1 on any failure.
"""
import re
import sys
from pathlib import Path

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "plugin"
pm = root / "skills" / "poteto-mode"
pb = pm / "playbooks"
fails = []


def text(p):
    return p.read_text()


def has(name, path, needle, why):
    if needle not in text(path):
        fails.append(f"{why}: {path.relative_to(root)} lacks {needle!r}")


def lacks(name, path, needle, why):
    if needle in text(path):
        fails.append(f"{why}: {path.relative_to(root)} still has {needle!r}")


router = pm / "SKILL.md"
# S1 / D1: no speed rule anywhere in the router or the playbooks this area owns.
speed = re.compile(r"fast or standard speed|standard speed|fast mode")
for p in [router] + sorted(pb.glob("*.md")):
    if p.name == "multi-phase-plan.md":
        continue  # owned by the scripts helper
    if speed.search(text(p)):
        fails.append(f"S1/D1 speed: {p.relative_to(root)}")
# Keep the effort sentence.
has(0, pb / "bug-fix.md", "Pick each subagent's `effort` for the job", "S1 keeps effort")
has(0, pb / "trace-forensics.md", "Pick each subagent's `effort` for the job", "S1 trace via subs")

# Item 1: isolation through delegate_task in T3.
for n in ["feature.md", "hillclimb.md", "visual-parity.md"]:
    has(0, pb / n, '`delegate_task` with `isolation: "worktree"`', "isolation")
has(0, pb / "shipping.md", "git worktree remove", "B2 verifier worktree leak")

# Item 2: worktree-cleanup leaves T3-managed worktrees to T3.
has(0, pb / "worktree-cleanup.md", "`t3-managed`", "cleanup t3-managed")
has(0, pb / "worktree-cleanup.md", "Never `git worktree remove` a `t3-managed`", "cleanup t3-managed")

# Item 3: store links.
for n in ["pause-safely.md", "orchestrate.md", "hillclimb.md", "autopilot-full.md", "session-pickup.md"]:
    has(0, pb / n, "../references/runtime.md#store", "store link")

# Item 4: babysit learnings go to a repo-local file read with the bundled one.
has(0, pb / "babysit.md", "bugbot-triage.local.md", "babysit step 9")
has(0, pm / "references" / "bugbot-triage.md", "bugbot-triage.local.md", "triage reads local file")

# Item 5: eval candidates for skill variants run in their own session.
has(0, pb / "eval.md", "claude -p --plugin-dir", "B3 eval")

# Item 6: T3 tools.
has(0, pb / "autopilot-stack.md", "write_pull_request_guides", "guides")
for n in ["autopilot-full.md", "orchestrate.md"]:
    has(0, pb / n, "t3_pending_request_respond", "pending request")
    has(0, pb / n, "t3_thread_organize", "organize")
for n in ["orchestrate.md", "pause-safely.md"]:
    has(0, pb / n, "t3_queue_list", "queue")
has(0, pb / "session-pickup.md", "t3_thread_fork", "fork")

# Item 7: opening-a-pr.
has(0, pb / "opening-a-pr.md", "sourceControlWritingStyle", "writing style")
has(0, pb / "opening-a-pr.md", "t3_worktree_status", "T3 worktree")
lacks(0, pb / "opening-a-pr.md", "Built-in PR tool", "S8")
lacks(0, pb / "opening-a-pr.md", "Invoked at the end of every other playbook", "router L153 twin")

# Item 8: router.
lacks(0, router, "or T3's own PR watching", "router L36")
lacks(0, router, "`auto` and `full-access` modes approve", "router L89")
has(0, router, "ExitPlanMode", "plan mode line")
has(0, router, 'isolation: "worktree"', "Subagents isolation")
lacks(0, router, "Bundled skills live at", "D9")
lacks(0, router, "UI / IDE / CLI", "S12")
lacks(0, router, "Invoked at the end of every other playbook", "router L153")
lacks(0, pb / "babysit.md", "T3's own PR watching", "babysit L3")

# Item 9 and D4/S15: orchestrate.
has(0, pb / "orchestrate.md", "--evidence <path>", "ledger evidence")
lacks(0, pb / "orchestrate.md", "Every worker runs on this machine", "D4")
lacks(0, pb / "orchestrate.md", "Every spawn here is local", "S15")

# Item 11.
for needle in ["--cpu-prof", "`sample <pid>`", "xctrace"]:
    has(0, pb / "runtime-forensics.md", needle, "B4 profiling surfaces")
has(0, pb / "prototype.md", "html_render", "prototype html_render")

# S11: transcript rule linked, not restated.
for n in ["session-pickup.md", "eval.md"]:
    lacks(0, pb / n, "projects/*/", "S11")

for f in fails:
    print("FAIL", f)
print(f"{len(fails)} failures")
sys.exit(1 if fails else 0)
