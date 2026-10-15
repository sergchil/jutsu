"""Tests for tools/t3_tools.py. Fixture TypeScript only, no network."""
from __future__ import annotations

import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import t3_tools  # noqa: E402
from t3_tools import ExtractError, extract, strip_comments  # noqa: E402

TK = "apps/server/src/mcp/toolkits"
ORCH = "packages/provider-core/src/server/orchestrationInstructions.ts"
ORCH_TEXT = 'export const T3 = `\n## T3 Code orchestration\n- Use delegate_task.\n`;\n'

LITERALS = '''
import { Tool, Toolkit } from "effect/ai";
const ListTool = Tool.make("device_list", { description: "List devices. // not a comment" });
export const OpenTool = Tool.make('device_open', {
  description: "Open one /* still a string */",
});
const WrappedTool = browserTool(
  Tool.make(`preview_open`, { description: "x" }),
);
export const DeviceToolkit = Toolkit.make(ListTool, OpenTool, WrappedTool);
export const SmallToolkit = Toolkit.make(ListTool);
'''

CONSTANT_LOCAL = '''
const THREAD_TOOL_NAME = "t3_thread_read" as const;
const ReadTool = Tool.make(THREAD_TOOL_NAME, { description: "read" });
export const ThreadToolkit = Toolkit.make(ReadTool);
'''

CONSTANT_IMPORTED = '''
import { HTML_RENDER_TOOL_NAME } from "@t3tools/shared/htmlRender";
const RenderTool = Tool.make(HTML_RENDER_TOOL_NAME, { description: "render" });
export const HtmlToolkit = Toolkit.make(RenderTool);
'''
SHARED = 'export const HTML_RENDER_TOOL_NAME = "html_render";\n'

COMMENTED = '''
// const OldTool = Tool.make("old_line_comment", {});
/*
const GoneTool = Tool.make("old_block_comment", {});
export const GoneToolkit = Toolkit.make(GoneTool);
*/
/** Tool.make("doc_comment") is how a tool is declared. */
const KeptTool = Tool.make("kept", {}); // Tool.make("trailing_comment")
export const KeptToolkit = Toolkit.make(KeptTool /* , GoneTool */);
'''


def tk(name: str, src: str) -> dict:
    return {f"{TK}/{name}/tools.ts": src}


class ExtractTest(unittest.TestCase):
    def test_literal_names_in_every_quote_style(self):
        self.assertEqual(extract(tk("device", LITERALS)), ["device_list", "device_open", "preview_open"])

    def test_constant_in_the_same_file(self):
        self.assertEqual(extract(tk("thread", CONSTANT_LOCAL)), ["t3_thread_read"])

    def test_constant_from_another_package(self):
        names = extract(tk("html", CONSTANT_IMPORTED), {"packages/shared/src/htmlRender.ts": SHARED})
        self.assertEqual(names, ["html_render"])

    def test_a_literal_only_reader_would_miss_the_constant(self):
        files = tk("device", LITERALS)
        files.update(tk("html", CONSTANT_IMPORTED))
        names = extract(files, {"packages/shared/src/htmlRender.ts": SHARED})
        self.assertIn("html_render", names)
        self.assertEqual(len(names), 4)

    def test_comments_do_not_count(self):
        self.assertEqual(extract(tk("kept", COMMENTED)), ["kept"])

    def test_unresolved_constant_fails(self):
        with self.assertRaisesRegex(ExtractError, "HTML_RENDER_TOOL_NAME"):
            extract(tk("html", CONSTANT_IMPORTED))

    def test_conflicting_constant_fails(self):
        other = {"a.ts": SHARED, "b.ts": 'export const HTML_RENDER_TOOL_NAME = "html_draw";\n'}
        with self.assertRaisesRegex(ExtractError, "conflicting"):
            extract(tk("html", CONSTANT_IMPORTED), other)

    def test_a_tool_made_but_not_registered_fails(self):
        src = LITERALS + 'const StrayTool = Tool.make("stray", {});\n'
        with self.assertRaisesRegex(ExtractError, "4 Tool.make calls but 3"):
            extract(tk("device", src))

    def test_duplicate_name_fails(self):
        src = 'const A = Tool.make("x", {});\nconst B = Tool.make("x", {});\nToolkit.make(A, B);\n'
        with self.assertRaisesRegex(ExtractError, "also made"):
            extract(tk("dup", src))

    def test_strip_comments_keeps_strings_and_lines(self):
        src = 'a = "// x"; // gone\n/* gone\n */ b = \'/* y */\';'
        out = strip_comments(src)
        self.assertIn('"// x"', out)
        self.assertIn("'/* y */'", out)
        self.assertNotIn("gone", out)
        self.assertEqual(out.count("\n"), src.count("\n"))


def git(*cmd: str, cwd: Path) -> None:
    subprocess.run(("git",) + cmd, cwd=cwd, check=True, capture_output=True)


class MainTest(unittest.TestCase):
    """Runs the command against a real git checkout made in a temp dir."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="t3-tools-test-"))
        self.addCleanup(shutil.rmtree, self.tmp)
        src = self.tmp / "t3code"
        for rel, text in {**tk("device", LITERALS), **tk("html", CONSTANT_IMPORTED),
                          f"{TK}/device/tools.test.ts": 'Tool.make("test_only", {});',
                          "packages/shared/src/htmlRender.ts": SHARED, ORCH: ORCH_TEXT}.items():
            (src / rel).parent.mkdir(parents=True, exist_ok=True)
            (src / rel).write_text(text)
        git("init", "-q", cwd=src)
        git("add", "-A", cwd=src)
        git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "fixture", cwd=src)
        self.src = src
        self.commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=src, capture_output=True,
                                     text=True, check=True).stdout.strip()
        self.pin = self.tmp / "t3.json"
        self.pin.write_text(json.dumps({
            "repo": "fixture/t3code", "repository": str(src), "commit": "0" * 40, "date": "2026-01-01",
            "toolkits": TK, "paths": [TK, "packages/shared/src"], "instructions": [ORCH]}))
        self.list = self.tmp / "t3-tools.txt"
        self.list.write_text("device_list\ndevice_open\ngone_tool\n")
        self.instructions = self.tmp / "t3-instructions.txt"
        (self.tmp / "plugin").mkdir()
        (self.tmp / "plugin" / "SKILL.md").write_text("Call `gone_tool` first.\n")
        for patch in (mock.patch.object(t3_tools, "PIN", self.pin), mock.patch.object(t3_tools, "LIST", self.list),
                      mock.patch.object(t3_tools, "INSTRUCTIONS", self.instructions),
                      mock.patch.object(t3_tools, "ROOT", self.tmp)):
            patch.start()
            self.addCleanup(patch.stop)

    def run_main(self, *argv: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = t3_tools.main(["--source", str(self.src), *argv])
        return code, out.getvalue()

    def test_dry_run_reports_and_writes_nothing(self):
        before = self.list.read_text()
        code, out = self.run_main("--dry-run")
        self.assertEqual(code, 0, out)
        self.assertIn("added: html_render", out)
        self.assertIn("removed: gone_tool (mentioned in plugin/SKILL.md)", out)
        self.assertIn("+preview_open", out)
        self.assertIn("+- Use delegate_task.", out)
        self.assertTrue(out.rstrip().endswith("changed: yes"))
        self.assertEqual(self.list.read_text(), before)
        self.assertFalse(self.instructions.exists())

    def change(self, rel: str, text: str) -> None:
        (self.src / rel).write_text(text)
        git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "change", cwd=self.src)

    def test_an_instruction_change_alone_is_a_change(self):
        # T3 added delegate_task isolation and a prompt rule on 2026-10-14 without
        # renaming a tool. The names-only report said "no tool names changed".
        self.assertEqual(self.run_main()[0], 0)
        code, out = self.run_main("--dry-run")
        self.assertTrue(out.rstrip().endswith("changed: no"), out)
        self.change(ORCH, ORCH_TEXT.replace("Use delegate_task.", 'Use delegate_task with isolation:"worktree".'))
        code, out = self.run_main("--dry-run")
        self.assertEqual(code, 0, out)
        self.assertIn("no tool names changed", out)
        self.assertIn('+- Use delegate_task with isolation:"worktree".', out)
        self.assertTrue(out.rstrip().endswith("changed: yes"), out)
        self.assertEqual(self.run_main("--check")[0], 1)

    def test_a_moved_instruction_file_fails_loudly(self):
        git("rm", "-q", ORCH, cwd=self.src)
        git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "move", cwd=self.src)
        code, out = self.run_main("--dry-run")
        self.assertEqual(code, 2)
        self.assertIn(f"{ORCH} is missing", out)

    def test_clone_checks_out_the_instruction_files(self):
        pin = json.loads(self.pin.read_text())
        dest = self.tmp / "clone"
        commit, _ = t3_tools.clone(pin, self.commit, dest)
        self.assertEqual(commit, self.commit)
        self.assertEqual((dest / ORCH).read_text(), ORCH_TEXT)
        self.assertTrue((dest / TK / "device" / "tools.ts").is_file())

    def test_write_then_check(self):
        code, out = self.run_main()
        self.assertEqual(code, 0, out)
        text = self.list.read_text()
        self.assertTrue(text.startswith("# Generated by tools/t3_tools.py"))
        self.assertIn(f"# fixture/t3code {self.commit} (", text)
        self.assertEqual(t3_tools.names_in(text), ["device_list", "device_open", "html_render", "preview_open"])
        self.assertEqual(json.loads(self.pin.read_text())["commit"], self.commit)
        snapshot = self.instructions.read_text()
        self.assertIn(f"===== {ORCH} =====\n{ORCH_TEXT}", snapshot)
        self.assertEqual(self.run_main("--check")[0], 0)

        self.list.write_text(text.replace("html_render\n", ""))
        code, out = self.run_main("--check")
        self.assertEqual(code, 1)
        self.assertIn("+html_render", out)

    def test_check_fails_when_the_pin_is_another_commit(self):
        self.run_main()
        pin = json.loads(self.pin.read_text())
        self.pin.write_text(json.dumps(dict(pin, commit="f" * 40)))
        code, out = self.run_main("--check")
        self.assertEqual(code, 1)
        self.assertIn("pins ffff", out)

    def test_committed_list_is_generated(self):
        text = (ROOT / "tools" / "t3-tools.txt").read_text()
        pin = json.loads((ROOT / "port" / "t3.json").read_text())
        self.assertIn(pin["commit"], text.splitlines()[1])
        snapshot = (ROOT / "tools" / "t3-instructions.txt").read_text()
        self.assertIn(pin["commit"], snapshot.splitlines()[1])
        for rel in pin["instructions"]:
            self.assertIn(f"===== {rel} =====\n", snapshot)
        # The build T3 users run (nightly 20261014.3105) is the pin.
        self.assertTrue(pin["commit"].startswith("3417bc385"))
        names = t3_tools.names_in(text)
        self.assertEqual(names, sorted(set(names)))
        self.assertIn(f"# {len(names)} tools", text)


if __name__ == "__main__":
    unittest.main()
