"""Tests for hooks/jutsu-mode, the hook that keeps poteto mode on for a session."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "port" / "added" / "hooks" / "jutsu-mode"
SESSION = "0e586f8a-0cfd-4368-ab98-f5918663c4ae"


class ModeHookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name) / "data"
        self.env = dict(os.environ, CLAUDE_PLUGIN_DATA=str(self.data), CLAUDE_PLUGIN_ROOT="/opt/jutsu")

    def tearDown(self):
        self.tmp.cleanup()

    def run_hook(self, event: str, payload, env=None) -> subprocess.CompletedProcess:
        stdin = payload if isinstance(payload, str) else json.dumps(payload)
        return subprocess.run(["sh", str(HOOK), event], input=stdin, capture_output=True, text=True,
                              env=env or self.env, timeout=10)

    def expand(self, name="jutsu", args="fix the login bug", **extra):
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

    def test_jutsu_turns_mode_on_and_reminds_each_turn(self):
        self.assertEqual(self.expand().returncode, 0)
        self.assertEqual(self.state_files(), [SESSION])
        r = self.prompt()
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(),
                         "jutsu poteto mode is on in this session. New task? Playbook match or rigor needed -> "
                         "apply poteto mode (router: /opt/jutsu/skills/poteto-mode/SKILL.md). "
                         "Casual turn or user opts out -> don't.")

    def test_plugin_qualified_router_name_turns_mode_on(self):
        self.expand(name="jutsu:poteto-mode", args="")
        self.assertEqual(self.state_files(), [SESSION])

    def test_other_skills_do_not_turn_mode_on(self):
        self.expand(name="jutsu:how", args="how does auth work")
        self.expand(name="p3-mode", args="x")
        self.assertEqual(self.state_files(), [])

    def test_off_in_any_case_and_spacing_turns_mode_off(self):
        self.expand()
        self.expand(name="jutsu:poteto-mode", args="  OFF ")
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
        self.assertIn("Reread /opt/jutsu/skills/poteto-mode/SKILL.md in full", r.stdout)
        r = self.run_hook("start", {"session_id": SESSION, "source": "resume"})
        self.assertEqual(r.stdout.strip(), "jutsu poteto mode is on in this session (router: /opt/jutsu/skills/poteto-mode/SKILL.md).")
        r = self.run_hook("start", {"session_id": SESSION, "source": "startup"})
        self.assertEqual(r.stdout, "")

    def test_unsafe_session_ids_write_nothing(self):
        for bad in ("../../etc", "a/b", "", "x y"):
            payload = {"session_id": bad, "command_name": "jutsu", "command_args": "go"}
            self.assertEqual(self.run_hook("expand", payload).returncode, 0)
        self.assertFalse((self.data / "sessions").exists() and any((self.data / "sessions").iterdir()))
        self.assertFalse((Path(self.tmp.name) / "etc").exists())

    def test_garbage_input_never_blocks(self):
        for event in ("expand", "prompt", "start", "subagent", "unknown"):
            for payload in ("", "not json", "{", "\x00\x01"):
                r = self.run_hook(event, payload)
                self.assertEqual(r.returncode, 0, (event, payload))
                self.assertEqual(r.stdout, "")

    def test_missing_data_dir_never_blocks(self):
        env = dict(self.env)
        env.pop("CLAUDE_PLUGIN_DATA")
        r = self.run_hook("expand", {"session_id": SESSION, "command_name": "jutsu", "command_args": "x"}, env=env)
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_pretty_printed_json(self):
        payload = json.dumps({"session_id": SESSION, "command_name": "jutsu", "command_args": "go"}, indent=2)
        self.run_hook("expand", payload)
        self.assertEqual(self.state_files(), [SESSION])

    def test_escaped_quotes_in_args_are_harmless(self):
        r = self.expand(args='fix the "login" bug; $(touch /tmp/jutsu-pwned)')
        self.assertEqual(r.returncode, 0)
        self.assertFalse(Path("/tmp/jutsu-pwned").exists())
        self.assertEqual(self.state_files(), [SESSION])

    # A T3 fork (SDK forkSession) or a lost state file starts a session with no state.
    # The hook restores it from the last /jutsu command in the session's transcript.
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
        tp = self.transcript(("/jutsu", 'fix the "login" bug'))
        r = self.start("fork", tp)
        self.assertEqual(r.stdout.strip(), "jutsu poteto mode is on in this session (router: /opt/jutsu/skills/poteto-mode/SKILL.md).")
        self.assertEqual(self.state_files(), [SESSION])
        self.assertIn("jutsu poteto mode is on", self.prompt().stdout)

    def test_restore_respects_the_last_command(self):
        for history, expect_on in [
            ([("/jutsu", "go"), ("/jutsu", "off")], False),
            ([("/jutsu", "off"), ("/jutsu", "go")], True),
            ([("/jutsu", "go"), ("/jutsu", "OFF ")], False),
            ([("/jutsu", "off the record, go")], True),
            ([("/jutsu", None)], True),
            ([("/jutsu:poteto-mode", "go")], True),
            ([("/jutsu:how", "how does it work")], False),
            ([], False),
        ]:
            with self.subTest(history=history):
                for f in (self.data / "sessions").glob("*") if (self.data / "sessions").exists() else []:
                    f.unlink()
                r = self.start("resume", self.transcript(*history))
                self.assertEqual(r.returncode, 0)
                self.assertEqual(self.state_files() == [SESSION], expect_on)

    def test_startup_never_restores(self):
        r = self.start("startup", self.transcript(("/jutsu", "go")))
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertEqual(self.state_files(), [])

    def test_missing_transcript_never_blocks(self):
        r = self.start("fork", Path(self.tmp.name) / "nope.jsonl")
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    # T3 expands only the last $skill mention into a slash command, so UserPromptSubmit
    # also reads the prompt itself. A mention counts only where a command would start:
    # at the start of the prompt or of a line, or as a skill:// link.
    ACTIVATED = ("jutsu poteto mode is now on in this session. Unless the router is already loaded "
                 "this turn, read /opt/jutsu/skills/poteto-mode/SKILL.md in full and apply it to this request.")

    def submit(self, text, **extra):
        payload = {"session_id": SESSION, "hook_event_name": "UserPromptSubmit", "prompt": text}
        payload.update(extra)
        return self.run_hook("prompt", payload)

    def reset(self):
        for f in (self.data / "sessions").glob("*") if (self.data / "sessions").exists() else []:
            f.unlink()

    def test_text_mentions_turn_mode_on(self):
        for text in [
            "$jutsu fix the login bug",
            "/jutsu fix the login bug",
            "$jutsu.",
            "$JUTSU go",
            "$jutsu:poteto-mode go",
            "/jutsu fix X with\n/jutsu:how",
            "fix the bug in auth.ts\n/jutsu",
            "[$jutsu](skill:///Users/me/.claude/skills/jutsu/SKILL.md) fix it",
            "[/jutsu](skill://jutsu) fix it",
            "use this (skill:///Users/me/.claude/skills/jutsu/SKILL.md) to fix it",
            "first line\n\t$jutsu\nlast line",
            'fix the "login" bug \\ with\n$jutsu',
        ]:
            with self.subTest(text=text):
                self.reset()
                r = self.submit(text)
                self.assertEqual(r.returncode, 0)
                self.assertEqual(r.stdout.strip(), self.ACTIVATED)
                self.assertEqual(self.state_files(), [SESSION])
                self.assertIn("jutsu poteto mode is on in this session.", self.prompt().stdout)

    def test_near_misses_do_not_turn_mode_on(self):
        for text in [
            "next",
            "/jutsu:how how does auth work",
            "$jutsu:how how does auth work",
            "/jutsus fix it",
            "$jutsu-x fix it",
            "foo/jutsu fix it",
            "see https://github.com/me/jutsu for the code",
            "open https://example.com/$jutsu now",
            "jutsu fix it",
            "run `$jutsu` later, not now",
            "```\n$jutsu fix it\n```\nwhat does that do?",
            "~~~sh\n/jutsu go\n~~~",
            "[$jutsu:how](skill:///x/jutsu/skills/how/SKILL.md) explain",
            "read skill:///x/jutsu/skills/how/SKILL.md",
            "/jutsu off",
            "$jutsu off",
        ]:
            with self.subTest(text=text):
                self.reset()
                r = self.submit(text)
                self.assertEqual((r.returncode, r.stdout), (0, ""))
                self.assertEqual(self.state_files(), [])

    def test_mentions_inside_a_sentence_do_not_turn_mode_on(self):
        # Talking about jutsu is not running it. Only a line that starts with the
        # command, or a skill:// link, turns the mode on.
        for text in [
            "what does $jutsu do compared to pstack?",
            "Should I uninstall /jutsu? it feels slow",
            "fix the login bug with $jutsu",
            "please use $jutsu.",
            "fix X with /jutsu and explain with /jutsu:how",
            'fix the "login" bug \\ with $jutsu',
        ]:
            with self.subTest(text=text):
                self.reset()
                r = self.submit(text)
                self.assertEqual((r.returncode, r.stdout), (0, ""))
                self.assertEqual(self.state_files(), [])

    def test_text_off_turns_mode_off(self):
        for text in ["/jutsu off", "$jutsu off", "  $JUTSU   OFF. ", "$jutsu:poteto-mode off!", "/jutsu\noff"]:
            with self.subTest(text=text):
                self.expand()
                r = self.submit(text)
                self.assertEqual((r.returncode, r.stdout), (0, ""))
                self.assertEqual(self.state_files(), [])

    def test_off_inside_a_sentence_does_not_turn_mode_off(self):
        self.expand()
        r = self.submit("$jutsu off the record, fix the bug")
        self.assertEqual(r.stdout.strip(), self.ACTIVATED)
        self.assertEqual(self.state_files(), [SESSION])
        r = self.submit("turn the $jutsu off switch into a toggle, see `/jutsu off`")
        self.assertEqual(self.state_files(), [SESSION])

    def test_text_mention_from_a_subagent_is_ignored(self):
        r = self.submit("$jutsu fix it", agent_id="a1")
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertEqual(self.state_files(), [])

    def test_unsafe_session_id_in_text_activation_writes_nothing(self):
        for bad in ("../../etc", "a/b", "", "x y"):
            r = self.run_hook("prompt", {"session_id": bad, "prompt": "$jutsu go"})
            self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertFalse((self.data / "sessions").exists() and any((self.data / "sessions").iterdir()))

    def test_unterminated_or_odd_prompt_never_blocks(self):
        for raw in ['{"session_id":"%s","prompt":"$jutsu go' % SESSION,
                    '{"session_id":"%s","prompt":12}' % SESSION,
                    '{"session_id":"%s","prompt":"\\u0024jutsu \\ud83d\\ude00 go"}' % SESSION]:
            r = self.run_hook("prompt", raw)
            self.assertEqual(r.returncode, 0, raw)
        self.assertEqual(self.state_files(), [SESSION])  # only the \u0024 form activates

    def test_huge_prompt_is_not_scanned(self):
        r = self.submit("x \\ \"y\"\n" * 40000 + " $jutsu go")
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertEqual(self.state_files(), [])
        self.expand()
        self.assertIn("jutsu poteto mode is on in this session.", self.submit("x\n" * 100000 + "$jutsu off").stdout)

    # SubagentStart: a jutsu:poteto-agent child of a session with the mode on gets the router path.
    def subagent(self, agent_type="jutsu:poteto-agent", **extra):
        payload = {"session_id": SESSION, "hook_event_name": "SubagentStart", "agent_id": "a1",
                   "agent_type": agent_type}
        payload.update(extra)
        return self.run_hook("subagent", payload)

    def test_subagent_gets_router_path_when_mode_is_on(self):
        self.assertEqual(self.subagent().stdout, "")
        self.expand()
        r = self.subagent()
        self.assertEqual(r.returncode, 0)
        out = json.loads(r.stdout)
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "SubagentStart")
        self.assertEqual(out["hookSpecificOutput"]["additionalContext"],
                         "jutsu poteto mode is on in the parent session. The poteto-mode router is "
                         "/opt/jutsu/skills/poteto-mode/SKILL.md. Read it in full before any work.")

    def test_other_subagent_types_get_nothing(self):
        self.expand()
        for t in ("general-purpose", "Explore", "jutsu:comment-sicko", "poteto-agent", ""):
            r = self.subagent(agent_type=t)
            self.assertEqual((r.returncode, r.stdout), (0, ""), t)

    def test_subagent_router_path_is_json_escaped(self):
        self.expand()
        env = dict(self.env, CLAUDE_PLUGIN_ROOT='/opt/ju"t\\su')
        payload = {"session_id": SESSION, "agent_type": "jutsu:poteto-agent"}
        r = self.run_hook("subagent", payload, env=env)
        ctx = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn('/opt/ju"t\\su/skills/poteto-mode/SKILL.md', ctx)

    def test_hooks_json_registers_subagent_start_for_poteto_agent_only(self):
        spec = json.loads((ROOT / "port" / "added" / "hooks" / "hooks.json").read_text())["hooks"]
        groups = spec["SubagentStart"]
        self.assertEqual([g["matcher"] for g in groups], ["^jutsu:poteto-agent$"])
        self.assertTrue(groups[0]["hooks"][0]["command"].endswith("/hooks/jutsu-mode\" subagent"))


if __name__ == "__main__":
    unittest.main()
