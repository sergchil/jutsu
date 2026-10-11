"""Tests for hooks/p3-mode, the hook that keeps poteto mode on for a session."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "port" / "added" / "hooks" / "p3-mode"
SESSION = "0e586f8a-0cfd-4368-ab98-f5918663c4ae"


class ModeHookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name) / "data"
        self.env = dict(os.environ, CLAUDE_PLUGIN_DATA=str(self.data), CLAUDE_PLUGIN_ROOT="/opt/p3")

    def tearDown(self):
        self.tmp.cleanup()

    def run_hook(self, event: str, payload, env=None) -> subprocess.CompletedProcess:
        stdin = payload if isinstance(payload, str) else json.dumps(payload)
        return subprocess.run(["sh", str(HOOK), event], input=stdin, capture_output=True, text=True,
                              env=env or self.env, timeout=10)

    def expand(self, name="p3", args="fix the login bug", **extra):
        payload = {"session_id": SESSION, "hook_event_name": "UserPromptExpansion",
                   "expansion_type": "slash_command", "command_name": name, "command_args": args,
                   "prompt": f"/{name} {args}"}
        payload.update(extra)
        return self.run_hook("expand", payload)

    def prompt(self):
        return self.run_hook("prompt", {"session_id": SESSION, "hook_event_name": "UserPromptSubmit", "prompt": "next"})

    def state_files(self):
        d = self.data / "sessions"
        return sorted(p.name for p in d.iterdir()) if d.exists() else []

    def test_silent_until_turned_on(self):
        r = self.prompt()
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_p3_turns_mode_on_and_reminds_each_turn(self):
        self.assertEqual(self.expand().returncode, 0)
        self.assertEqual(self.state_files(), [SESSION])
        r = self.prompt()
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(),
                         "p3 poteto mode is on in this session. New task? Playbook match or rigor needed -> "
                         "apply poteto mode (router: /opt/p3/skills/poteto-mode/SKILL.md). "
                         "Casual turn or user opts out -> don't.")

    def test_plugin_qualified_router_name_turns_mode_on(self):
        self.expand(name="p3:poteto-mode", args="")
        self.assertEqual(self.state_files(), [SESSION])

    def test_other_skills_do_not_turn_mode_on(self):
        self.expand(name="p3:how", args="how does auth work")
        self.expand(name="p3-mode", args="x")
        self.assertEqual(self.state_files(), [])

    def test_off_in_any_case_and_spacing_turns_mode_off(self):
        self.expand()
        self.expand(name="p3:poteto-mode", args="  OFF ")
        self.assertEqual(self.state_files(), [])
        self.assertEqual(self.prompt().stdout, "")

    def test_off_with_more_words_keeps_mode_on(self):
        self.expand(args="off the record, fix the bug")
        self.assertEqual(self.state_files(), [SESSION])

    def test_subagent_expansion_is_ignored(self):
        self.expand()
        self.expand(args="off", agent_id="a1")
        self.assertEqual(self.state_files(), [SESSION])

    def test_compact_rereads_the_router_and_resume_only_reminds(self):
        self.expand()
        r = self.run_hook("start", {"session_id": SESSION, "source": "compact"})
        self.assertIn("Reread /opt/p3/skills/poteto-mode/SKILL.md in full", r.stdout)
        r = self.run_hook("start", {"session_id": SESSION, "source": "resume"})
        self.assertEqual(r.stdout.strip(), "p3 poteto mode is on in this session (router: /opt/p3/skills/poteto-mode/SKILL.md).")
        r = self.run_hook("start", {"session_id": SESSION, "source": "startup"})
        self.assertEqual(r.stdout, "")

    def test_unsafe_session_ids_write_nothing(self):
        for bad in ("../../etc", "a/b", "", "x y"):
            payload = {"session_id": bad, "command_name": "p3", "command_args": "go"}
            self.assertEqual(self.run_hook("expand", payload).returncode, 0)
        self.assertFalse((self.data / "sessions").exists() and any((self.data / "sessions").iterdir()))
        self.assertFalse((Path(self.tmp.name) / "etc").exists())

    def test_garbage_input_never_blocks(self):
        for event in ("expand", "prompt", "start", "unknown"):
            for payload in ("", "not json", "{", "\x00\x01"):
                r = self.run_hook(event, payload)
                self.assertEqual(r.returncode, 0, (event, payload))
                self.assertEqual(r.stdout, "")

    def test_missing_data_dir_never_blocks(self):
        env = dict(self.env)
        env.pop("CLAUDE_PLUGIN_DATA")
        r = self.run_hook("expand", {"session_id": SESSION, "command_name": "p3", "command_args": "x"}, env=env)
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_pretty_printed_json(self):
        payload = json.dumps({"session_id": SESSION, "command_name": "p3", "command_args": "go"}, indent=2)
        self.run_hook("expand", payload)
        self.assertEqual(self.state_files(), [SESSION])

    def test_escaped_quotes_in_args_are_harmless(self):
        r = self.expand(args='fix the "login" bug; $(touch /tmp/p3-pwned)')
        self.assertEqual(r.returncode, 0)
        self.assertFalse(Path("/tmp/p3-pwned").exists())
        self.assertEqual(self.state_files(), [SESSION])

    # A T3 fork (SDK forkSession) or a lost state file starts a session with no state.
    # The hook restores it from the last /p3 command in the session's transcript.
    def transcript(self, *commands) -> Path:
        path = Path(self.tmp.name) / "session.jsonl"
        lines = ['{"type":"user","message":{"role":"user","content":"hi"}}']
        for name, args in commands:
            content = f"<command-message>{name[1:]}</command-message>\\n<command-name>{name}</command-name>"
            if args is not None:
                content += f"\\n<command-args>{args}</command-args>"
            lines.append('{"type":"user","message":{"role":"user","content":"' + content.replace('"', '\\"') + '"},"uuid":"u"}')
        path.write_text("\n".join(lines) + "\n")
        return path

    def start(self, source, transcript):
        return self.run_hook("start", {"session_id": SESSION, "source": source, "transcript_path": str(transcript)})

    def test_fork_restores_the_mode_from_history(self):
        tp = self.transcript(("/p3", 'fix the "login" bug'))
        r = self.start("fork", tp)
        self.assertEqual(r.stdout.strip(), "p3 poteto mode is on in this session (router: /opt/p3/skills/poteto-mode/SKILL.md).")
        self.assertEqual(self.state_files(), [SESSION])
        self.assertIn("p3 poteto mode is on", self.prompt().stdout)

    def test_restore_respects_the_last_command(self):
        for history, expect_on in [
            ([("/p3", "go"), ("/p3", "off")], False),
            ([("/p3", "off"), ("/p3", "go")], True),
            ([("/p3", "go"), ("/p3", "OFF ")], False),
            ([("/p3", "off the record, go")], True),
            ([("/p3", None)], True),
            ([("/p3:poteto-mode", "go")], True),
            ([("/p3:how", "how does it work")], False),
            ([], False),
        ]:
            with self.subTest(history=history):
                for f in (self.data / "sessions").glob("*") if (self.data / "sessions").exists() else []:
                    f.unlink()
                r = self.start("resume", self.transcript(*history))
                self.assertEqual(r.returncode, 0)
                self.assertEqual(self.state_files() == [SESSION], expect_on)

    def test_startup_never_restores(self):
        r = self.start("startup", self.transcript(("/p3", "go")))
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertEqual(self.state_files(), [])

    def test_missing_transcript_never_blocks(self):
        r = self.start("fork", Path(self.tmp.name) / "nope.jsonl")
        self.assertEqual((r.returncode, r.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()
