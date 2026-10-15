import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { expect, test } from "bun:test";

// process.execPath is bun under `bun test`; check-plan.mjs runs on bun or node.
const checker = join(import.meta.dir, "check-plan.mjs");
const rule =
	"Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.";

const validPlan = `# Demo

## How to read this
One box is one unit of work and names the evidence. Check a box only when its evidence exists. See playbooks/.
${rule}

## Program checklist
### Arm the program
### Spawn owners
### PR mechanics
### Verdict and merge
### Boot recipe
Run from the installed plugin. \`schedule_task\` every 3600000 ms. status message

## PR 1
**Depends on.** None.
**Files.**
- [ ] Do the thing.
**Build.**
- [ ] Do the thing.
**You see.**
- [ ] Do the thing.
**Verify, unit.** ${rule}
- [ ] Check the thing.
**Verify, live.** ${rule} Ten lanes on \`example-model\` at the PR head
${Array.from({ length: 10 }, (_, i) => `- [ ] Lane ${i + 1}. Save \`lane-${i + 1}.png\`. Pass when evidence exists.`).join("\n")}
**Verify, perf.** ${rule}
- [ ] Metric. Recorded.
- [ ] Probe. Recorded.
- [ ] Baseline. Recorded.
- [ ] Rule. Recorded.
**Review gate.** None.
**Merge.**
- [ ] Merge when approved.

## Close the program
Close.

## Appendix Prototype evidence
Recorded.
`;

const runPlan = (example: string, expectedExit: number) => {
	const directory = mkdtempSync(join(tmpdir(), "check-plan-test-"));
	const file = join(directory, "plan.md");
	writeFileSync(file, validPlan + example);
	try {
		const result = spawnSync(process.execPath, [checker, file], { encoding: "utf8" });
		expect(result.status).toBe(expectedExit);
		return result;
	} finally {
		rmSync(directory, { recursive: true, force: true });
	}
};

test("accepts ordinary, indented, and longer closing fences", () => {
	for (const indent of ["", " ", "  ", "   "])
		runPlan(`${indent}\`\`\`markdown\n## Example only\n${indent}\`\`\`\n`, 0);
	runPlan("```markdown\n## Example only\n````\n", 0);
});

test("accepts nested backticks and tilde info strings", () => {
	runPlan("````markdown\n```markdown\n## Example only\n```\n````\n", 0);
	runPlan("~~~markdown `info`\n## Example only\n ~~~\n", 0);
});

test("keeps mismatched, shorter, and suffixed closers inside the fence", () => {
	runPlan("````markdown\n~~~\n## Example only\n````\n", 0);
	runPlan("````markdown\n```\n## Example only\n````\n", 0);
	runPlan("````markdown\n``` info\n## Example only\n````\n", 0);
});

test("rejects headings and prose outside a proper close", () => {
	for (const suffix of ["  ", "\t"]) {
		const heading = runPlan(`\`\`\`markdown\n## Example only\n\`\`\`${suffix}\n## Example only\n`, 1);
		expect(heading.stderr).toContain('"## Example only" after Close the program is not an appendix');
	}

	const prose = runPlan("```markdown\nThis prose has a mid-sentence colon: inside code\n```\nThis prose has a mid-sentence colon: bad.\n", 1);
	expect(prose.stderr).toContain("mid-sentence colon");
});

test("rejects backtick info strings containing a backtick", () => {
	const result = runPlan("```markdown `invalid`\n## Example only\n```\n", 1);
	expect(result.stderr).toContain('"## Example only" after Close the program is not an appendix');
});

const run = (args: string[]) => spawnSync(process.execPath, [checker, ...args], { encoding: "utf8" });

const withPr = (lanes: string, gate: string) =>
	validPlan
		.replace(/- \[ \] Lane 1\. [\s\S]*?(?=\*\*Verify, perf\.\*\*)/, `${lanes}\n`)
		.replace("**Review gate.** None.", gate);
const lanes = (ext: string) =>
	Array.from({ length: 10 }, (_, i) => `- [ ] Lane ${i + 1}. Run it. Save \`lane-${i + 1}.${ext}\`. Pass when it exits 0.`).join("\n");

const runText = (plan: string) => {
	const directory = mkdtempSync(join(tmpdir(), "check-plan-test-"));
	const file = join(directory, "plan.md");
	writeFileSync(file, plan);
	try {
		return spawnSync(process.execPath, [checker, file], { encoding: "utf8" });
	} finally {
		rmSync(directory, { recursive: true, force: true });
	}
};

test("--help prints usage and exits 0 without a stack trace", () => {
	for (const flag of ["--help", "-h"]) {
		const result = run([flag]);
		expect(result.status).toBe(0);
		expect(result.stdout).toContain("Usage:");
		expect(result.stderr).not.toContain("ENOENT");
	}
});

test("a missing plan file is a usage error, not a crash", () => {
	const result = run([join(tmpdir(), "no-such-plan-check-plan.md")]);
	expect(result.status).toBe(2);
	expect(result.stderr).toContain("cannot read");
	expect(result.stderr).not.toContain("    at ");
});

test("flags unfilled placeholders in prose and in code spans", () => {
	const prose = runPlan("Pick <the merge rule> here.\n", 1);
	expect(prose.stderr).toContain('unfilled placeholder "<the merge rule>"');
	const code = runPlan("Save `/tmp/swarm-<pr-id>/<slug>.png`.\n", 1);
	expect(code.stderr).toContain('unfilled placeholder "<pr-id>"');
	expect(code.stderr).toContain('unfilled placeholder "<slug>"');
});

test("does not flag generics, HTML tags, autolinks, or fenced examples", () => {
	runPlan("Use `Promise<void>` and `Map<K, V>`. See <https://example.com>.<br>\n```sh\ncp <src> <dst>\n```\n", 0);
});

test("a CLI or library PR needs no screenshot or video", () => {
	const gate = "**Review gate.** The operator reviews before merge.\n- [ ] Post the `tmux capture-pane` transcript in chat for the operator.";
	const result = runText(withPr(lanes("txt"), gate));
	expect(result.stderr).toBe("");
	expect(result.status).toBe(0);
});

test("a UI PR's review gate must post its screenshots", () => {
	const gate = "**Review gate.** The operator reviews before merge.\n- [ ] Post the transcript in chat for the operator.";
	const result = runText(withPr(lanes("png"), gate));
	expect(result.status).toBe(1);
	expect(result.stderr).toContain('Review gate lacks "screenshot"');
	expect(result.stderr).not.toContain('lacks "video"');
});

test("a lane must save its evidence and name a pass predicate", () => {
	const bad = lanes("txt").replace("Save `lane-3.txt`. ", "");
	const result = runText(withPr(bad, "**Review gate.** None."));
	expect(result.status).toBe(1);
	expect(result.stderr).toContain("lane 3 names no evidence file");
});
