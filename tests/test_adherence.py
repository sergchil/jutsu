"""tools/adherence.py on fixture transcripts.

Method from pstack-claude issue #264: over sessions where the mode hook's text appeared, count the share that
opened the router, a playbook, and a principle, and the same for their subagents.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "adherence.py"
PLUGIN = "/home/u/.claude/skills/jutsu"
ROUTER = f"{PLUGIN}/skills/poteto-mode/SKILL.md"
PLAYBOOK = f"{PLUGIN}/skills/poteto-mode/playbooks/bug-fix.md"
PRINCIPLE = f"{PLUGIN}/principles/principle-prove-it-works.md"
SECRET = "SECRET-PROMPT-TEXT"


def hook(event, text, kind="hook_success"):
    att = {"type": kind, "hookEvent": event, "hookName": event}
    if kind == "hook_success":
        att.update(content=text, stdout=text, exitCode="0")
    else:
        att["content"] = text
    return {"type": "attachment", "attachment": att}


def prompt(text=SECRET):
    return {"type": "user", "message": {"role": "user", "content": text}}


def read(path):
    return {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": "t", "name": "Read", "input": {"file_path": path}}]}}


ON = f"jutsu poteto mode is now on in this session. Unless the router is already loaded this turn, read {ROUTER} in full."
STILL_ON = f"jutsu poteto mode is on in this session. New task? (router: {ROUTER})"
CHILD = f"jutsu poteto mode is on in the parent session. The poteto-mode router is {ROUTER}. Read it in full."


class AdherenceTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.config = Path(self._tmp.name) / "claude"
        self.project = self.config / "projects" / "-repo"
        self.project.mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def session(self, sid, records, raw_lines=()):
        path = self.project / f"{sid}.jsonl"
        path.write_text("".join(json.dumps(r) + "\n" for r in records) + "".join(raw_lines))
        return path

    def subagent(self, sid, aid, agent_type, records):
        d = self.project / sid / "subagents"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"agent-{aid}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
        (d / f"agent-{aid}.meta.json").write_text(json.dumps({"agentType": agent_type}))

    def run_tool(self, *args, env_dir=True):
        env = {**os.environ}
        env.pop("CLAUDE_CONFIG_DIR", None)
        if env_dir:
            env["CLAUDE_CONFIG_DIR"] = str(self.config)
        env["HOME"] = str(Path(self._tmp.name) / "empty-home")
        return subprocess.run([sys.executable, str(TOOL), *args], env=env, capture_output=True, text=True, timeout=60)

    def build(self):
        # On, then router, playbook, and principle.
        self.session("a", [prompt(), hook("UserPromptSubmit", ON), read(ROUTER), read(PLAYBOOK), read(PRINCIPLE),
                           prompt(), hook("UserPromptSubmit", STILL_ON)])
        # Read the router before the mode came on, then nothing: not an open.
        self.session("b", [read(ROUTER), prompt(), hook("UserPromptSubmit", ON)],
                     raw_lines=["{not json\n"])
        # Never on: excluded, whatever it reads.
        self.session("c", [prompt(), read(ROUTER)])
        # The marker only inside a request blob is not the hook firing.
        self.session("d", [{"type": "api-request-blob", "body": ON}, read(ROUTER)])
        # A resumed session: the SessionStart hook turns counting on.
        self.session("e", [hook("SessionStart", "jutsu poteto mode is on in this session (router: x)"), read(PRINCIPLE)])
        self.subagent("a", "1", "jutsu:poteto-agent", [hook("SubagentStart", CHILD, "hook_additional_context"),
                                                       read(ROUTER), read(PLAYBOOK)])
        self.subagent("a", "2", "general-purpose", [prompt("brief"), read("/repo/x.py")])
        # Subagents of a session without the mode are out of scope.
        self.subagent("c", "3", "jutsu:poteto-agent", [read(ROUTER)])

    def test_counts_follow_the_issue_264_method(self):
        self.build()
        r = self.run_tool("--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        main = data["main"]
        self.assertEqual(main["sessions"], 3)
        self.assertEqual(main["prompts"], 3)
        self.assertEqual(main["router"], 1)
        self.assertEqual(main["playbook"], 1)
        self.assertEqual(main["principle"], 2)
        subs = data["subagents"]
        self.assertEqual(subs["jutsu:poteto-agent"], {"agents": 1, "hook": 1, "router": 1, "playbook": 1, "principle": 0})
        self.assertEqual(subs["other"], {"agents": 1, "hook": 0, "router": 0, "playbook": 0, "principle": 0})
        self.assertEqual(data["skipped_lines"], 1)

    def test_text_report_has_shares_and_no_transcript_content(self):
        self.build()
        r = self.run_tool()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("opened the router: 1 of 3 (33%)", r.stdout)
        self.assertNotIn(SECRET, r.stdout + r.stderr)
        self.assertNotIn("bug-fix", r.stdout + r.stderr)

    def test_config_dir_flag_and_default(self):
        self.build()
        r = self.run_tool("--json", "--config-dir", str(self.config), env_dir=False)
        self.assertEqual(json.loads(r.stdout)["main"]["sessions"], 3)
        r = self.run_tool("--json", env_dir=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["main"]["sessions"], 0)

    def test_never_writes(self):
        self.build()
        before = {p: (p.stat().st_mtime_ns, p.read_bytes()) for p in self.config.rglob("*") if p.is_file()}
        self.run_tool()
        after = {p: (p.stat().st_mtime_ns, p.read_bytes()) for p in self.config.rglob("*") if p.is_file()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
