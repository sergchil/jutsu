import { describe, expect, it } from "bun:test";
import { ChecksUnavailable, WatcherQueryError } from "./github.ts";
import {
  NO_CHECKS_CONFIRM_SECONDS,
  NO_CHECKS_REPORTED_STATE,
  type WatchClock,
  applyQueueSnapshot,
  assessGitHubMerge,
  classifyPr,
  createQueueState,
  evaluateQueue,
  noChecksConfirmer,
  planQueue,
  queryBackoffSeconds,
  readSnapshot,
  runQueued,
  runSimple,
  selectTierMajorStackDecision,
} from "./policy.ts";
import { renderJson, renderPretty } from "./render.ts";
import {
  fakeReader,
  failedCheck,
  passingCheck,
  pendingCheck,
} from "./fakes.test-helper.ts";
import type {
  GitHubReader,
  NonEmpty,
  PollingOptions,
  PrContext,
  ProgressVerdict,
  PullRequestFacts,
  RollupState,
} from "./types.ts";
import { parsePrNumber } from "./types.ts";

const context = (number: number): PrContext => ({
  owner: "owner",
  repo: "repo",
  number: parsePrNumber(number),
});
const options = {
  interval: 10,
  sweepInterval: 300,
  timeout: 0,
  maxQueryErrors: 5,
  allowDraft: false,
} satisfies PollingOptions;

describe("readiness truth table", () => {
  it("covers every specified row and every UNKNOWN rollup value", () => {
    const cases: readonly [
      PullRequestFacts["mergeStateStatus"],
      RollupState,
      "allowed" | "refused",
    ][] = [
      ["BLOCKED", "FAILURE", "refused"],
      ["BLOCKED", "ERROR", "refused"],
      ["BLOCKED", "PENDING", "allowed"],
      ["UNSTABLE", "FAILURE", "allowed"],
      ["UNKNOWN", "ERROR", "allowed"],
      ["UNKNOWN", "EXPECTED", "allowed"],
      ["UNKNOWN", "FAILURE", "allowed"],
      ["UNKNOWN", "PENDING", "allowed"],
      ["UNKNOWN", "SUCCESS", "allowed"],
      ["UNKNOWN", null, "allowed"],
      ["CLEAN", "SUCCESS", "allowed"],
    ];
    for (const [mergeStateStatus, headRollupState, expected] of cases) {
      expect(
        assessGitHubMerge({ mergeStateStatus, headRollupState }).kind
      ).toBe(expected);
    }
  });

  it("turns a clean visible list plus GitHub refusal into an explicit CI blocker", async () => {
    const reader = fakeReader({
      facts: { mergeStateStatus: "BLOCKED" },
      fastPath: { kind: "checks", checks: [passingCheck()] },
      commitRollups: [{ oid: "head", state: "FAILURE" }],
    });
    const snapshot = await readSnapshot({
      reader,
      context: context(1),
      pendingHistory: "include",
      allowDraft: false,
    });
    expect(snapshot.kind).toBe("open");
    if (snapshot.kind !== "open") throw new Error("expected open snapshot");
    expect(snapshot.ci.kind).toBe("ci-github-rejected");
    expect(classifyPr(snapshot)).toMatchObject({
      kind: "blocker",
      blocker: { kind: "failing-checks" },
    });
  });
});

describe("snapshot query planning", () => {
  it("does not query commit rollups while queued checks are pending", async () => {
    const reader = fakeReader({
      fastPath: { kind: "checks", checks: [pendingCheck()] },
    });
    const snapshot = await readSnapshot({
      reader,
      context: context(2),
      pendingHistory: "omit",
      allowDraft: false,
    });
    expect(snapshot.kind).toBe("open");
    if (snapshot.kind !== "open") throw new Error("expected open snapshot");
    expect(snapshot.ci.kind).toBe("ci-pending");
    expect(reader.calls).toEqual([
      "pullRequest",
      "reviewThreadPage:null",
      "checksFastPath",
    ]);
  });

  it("queries rollups for settled and failed lists", async () => {
    const settled = fakeReader();
    await readSnapshot({
      reader: settled,
      context: context(3),
      pendingHistory: "omit",
      allowDraft: false,
    });
    expect(settled.calls).toContain("commitRollups");

    const failed = fakeReader({
      fastPath: { kind: "checks", checks: [failedCheck()] },
    });
    await readSnapshot({
      reader: failed,
      context: context(4),
      pendingHistory: "omit",
      allowDraft: false,
    });
    expect(failed.calls).toContain("commitRollups");
  });

  it("short-circuits merged rows before threads and checks", async () => {
    const reader = fakeReader({
      facts: { state: "MERGED", mergedAt: "2026-07-26T00:00:00Z" },
    });
    expect(
      (
        await readSnapshot({
          reader,
          context: context(5),
          pendingHistory: "include",
          allowDraft: false,
        })
      ).kind
    ).toBe("merged");
    expect(reader.calls).toEqual(["pullRequest"]);
  });
});

it("scans stacks tier-major so an upstack conflict outranks frontier CI", async () => {
  const frontier = await readSnapshot({
    reader: fakeReader({
      fastPath: { kind: "checks", checks: [failedCheck()] },
      commitRollups: [{ oid: "head", state: "FAILURE" }],
    }),
    context: context(10),
    pendingHistory: "omit",
    allowDraft: false,
  });
  const upstack = await readSnapshot({
    reader: fakeReader({ facts: { mergeable: "CONFLICTING" } }),
    context: context(11),
    pendingHistory: "omit",
    allowDraft: false,
  });
  const decision = selectTierMajorStackDecision([frontier, upstack]);
  expect(decision).toMatchObject({
    kind: "blocker",
    blocker: { kind: "merge-conflicts", pr: { number: 11 } },
  });
});

it("attributes a stack wait to the PR whose checks are pending, not the bottom", async () => {
  const readyBottom = await readSnapshot({
    reader: fakeReader(),
    context: context(20),
    pendingHistory: "omit",
    allowDraft: false,
  });
  const pendingUpstack = await readSnapshot({
    reader: fakeReader({
      fastPath: { kind: "checks", checks: [pendingCheck("upstack-build")] },
    }),
    context: context(21),
    pendingHistory: "omit",
    allowDraft: false,
  });
  const decision = selectTierMajorStackDecision([readyBottom, pendingUpstack]);
  expect(decision).toMatchObject({
    kind: "waiting",
    frontier: { number: 21 },
    pending: [{ name: "upstack-build" }],
  });
});

it("waits on a draft while checks are pending, then reports the draft gate", async () => {
  const pending = await readSnapshot({
    reader: fakeReader({
      facts: { isDraft: true },
      fastPath: { kind: "checks", checks: [pendingCheck()] },
    }),
    context: context(12),
    pendingHistory: "omit",
    allowDraft: false,
  });
  expect(classifyPr(pending).kind).toBe("waiting");

  const settled = await readSnapshot({
    reader: fakeReader({ facts: { isDraft: true } }),
    context: context(12),
    pendingHistory: "omit",
    allowDraft: false,
  });
  expect(classifyPr(settled)).toMatchObject({
    kind: "blocker",
    blocker: { kind: "merge-gate", reason: "draft-pr" },
  });
});

it("never reports READY on a branch that is behind its base", async () => {
  const behind = await readSnapshot({
    reader: fakeReader({ facts: { mergeStateStatus: "BEHIND" } }),
    context: context(13),
    pendingHistory: "omit",
    allowDraft: false,
  });
  expect(classifyPr(behind)).toMatchObject({
    kind: "blocker",
    blocker: { kind: "merge-gate", reason: "behind-base", pr: { number: 13 } },
  });
  const bottom = await readSnapshot({
    reader: fakeReader(),
    context: context(14),
    pendingHistory: "omit",
    allowDraft: false,
  });
  expect(selectTierMajorStackDecision([bottom, behind])).toMatchObject({
    kind: "blocker",
    blocker: { kind: "merge-gate", reason: "behind-base", pr: { number: 13 } },
  });
  const decision = classifyPr(behind);
  if (decision.kind !== "blocker") throw new Error("expected a blocker");
  const text = renderPretty({
    schemaVersion: 1,
    sequence: 1,
    observedAt: "2026-01-01T00:00:00Z",
    mode: "single",
    kind: "BLOCKER",
    terminal: true,
    exitCode: 6,
    blocker: decision.blocker,
  } as Parameters<typeof renderPretty>[0]);
  expect(text).toContain("BLOCKER: behind-base");
  expect(text).toContain("rebase");
});

describe("queued-stack cadence", () => {
  async function openSnapshot(pr: PrContext) {
    return readSnapshot({
      reader: fakeReader(),
      context: pr,
      pendingHistory: "omit",
      allowDraft: false,
    });
  }

  it("drops a sweep head only after its snapshot succeeds", async () => {
    const queue = [
      context(20),
      context(21),
      context(22),
    ] satisfies NonEmpty<PrContext>;
    let state = createQueueState(queue, 0);
    const first = await openSnapshot(queue[0]);
    state = applyQueueSnapshot(state, first, 0, options).state;
    expect(state.work).toMatchObject({
      kind: "whole-stack-sweep",
      remaining: [{ number: 21 }, { number: 22 }],
    });
    const second = await openSnapshot(queue[1]);
    state = applyQueueSnapshot(state, second, 60, options).state;
    expect(state.work).toMatchObject({
      kind: "whole-stack-sweep",
      remaining: [{ number: 22 }],
    });
  });

  it("resumes the sweep at the PR whose read failed", async () => {
    const middle = context(21);
    const base = fakeReader();
    let failNext = true;
    const timeline: string[] = [];
    const reader = {
      ...base,
      async pullRequest(pr: PrContext) {
        if (pr.number === middle.number && failNext) {
          failNext = false;
          timeline.push(`fail:${pr.number}`);
          throw new WatcherQueryError({
            kind: "command-exit",
            retryable: true,
            detail: "rate limited",
            code: 1,
          });
        }
        timeline.push(`read:${pr.number}`);
        return base.pullRequest(pr);
      },
    } satisfies GitHubReader;
    let now = 0;
    let sleeps = 0;
    const running = runQueued({
      dependencies: {
        reader,
        clock: {
          now: () => now,
          observedAt: () => "2026-07-26T00:00:00.000Z",
          async sleep(seconds) {
            timeline.push("sleep");
            now += seconds;
            sleeps += 1;
            if (sleeps === 2) throw new Error("stop after resume proof");
          },
        },
        emit(verdict) {
          timeline.push(`emit:${verdict.kind}`);
        },
      },
      contexts: [context(20), middle, context(22)],
      options,
    });
    await expect(running).rejects.toThrow("stop after resume proof");
    expect(timeline).toEqual([
      "emit:QUEUE",
      "read:20",
      "fail:21",
      "emit:RETRY",
      "sleep",
      "read:21",
      "read:22",
      "emit:STATUS",
      "emit:WAITING",
      "sleep",
    ]);
  });

  it("emits a completed sweep only after its final successful snapshot", async () => {
    const queue = [context(30), context(31)] satisfies NonEmpty<PrContext>;
    let state = createQueueState(queue, 0);
    const first = applyQueueSnapshot(
      state,
      await openSnapshot(queue[0]),
      0,
      options
    );
    expect(first.completedSweepRows).toBeNull();
    state = first.state;
    const second = applyQueueSnapshot(
      state,
      await openSnapshot(queue[1]),
      5,
      options
    );
    expect(
      second.completedSweepRows?.map((row) => Number(row.context.number))
    ).toEqual([30, 31]);
    expect(second.state.nextSweepAt).toBe(305);
  });

  it("ADVANCE continues directly to the new frontier without sleeping", async () => {
    const one = context(40);
    const two = context(41);
    const base = fakeReader();
    const reads = new Map<number, number>();
    const timeline: string[] = [];
    const reader = {
      ...base,
      async pullRequest(pr: PrContext) {
        timeline.push(`read:${pr.number}`);
        const facts = await base.pullRequest(pr);
        const count = (reads.get(pr.number) ?? 0) + 1;
        reads.set(pr.number, count);
        return pr.number === one.number && count > 1
          ? {
              ...facts,
              state: "MERGED" as const,
              mergedAt: "2026-07-26T00:00:00Z",
            }
          : facts;
      },
    } satisfies GitHubReader;
    let now = 0;
    let sleeps = 0;
    const emitted: ProgressVerdict[] = [];
    const running = runQueued({
      dependencies: {
        reader,
        clock: {
          now: () => now,
          observedAt: () => "2026-07-26T00:00:00.000Z",
          async sleep(seconds) {
            timeline.push("sleep");
            now += seconds;
            sleeps += 1;
            if (sleeps === 2) throw new Error("stop after advance proof");
          },
        },
        emit(verdict) {
          emitted.push(verdict);
          timeline.push(`emit:${verdict.kind}`);
        },
      },
      contexts: [one, two],
      options,
    });
    await expect(running).rejects.toThrow("stop after advance proof");
    expect(emitted.some((event) => event.kind === "ADVANCE")).toBe(true);
    const firstSleep = timeline.indexOf("sleep");
    expect(timeline.slice(firstSleep, firstSleep + 5)).toEqual([
      "sleep",
      "read:40",
      "emit:ADVANCE",
      "read:41",
      "emit:WAITING",
    ]);
  });

  it("deduplicates identical waits and schedules the next due sweep", async () => {
    const queue = [context(50)] satisfies NonEmpty<PrContext>;
    let state = createQueueState(queue, 0);
    state = applyQueueSnapshot(
      state,
      await openSnapshot(queue[0]),
      0,
      options
    ).state;
    const first = evaluateQueue(state, 0, options);
    expect(first.kind).toBe("waiting");
    if (first.kind !== "waiting") throw new Error("expected waiting");
    expect(first.emit).toBe(true);
    const second = evaluateQueue(first.state, 10, options);
    expect(second.kind).toBe("waiting");
    if (second.kind !== "waiting") throw new Error("expected waiting");
    expect(second.emit).toBe(false);
    expect(planQueue(second.state, 300).work?.kind).toBe("whole-stack-sweep");
  });
});

it("uses the specified retry floor and cap", () => {
  expect(queryBackoffSeconds(1, 1)).toBe(60);
  expect(queryBackoffSeconds(1, 2)).toBe(120);
  expect(queryBackoffSeconds(60, 4)).toBe(300);
});

describe("a PR with no checks configured", () => {
  const noChecksMessage = {
    kind: "unusable",
    exitCode: 1,
    stderr: "no checks reported on the 'trunk' branch",
  } as const;
  // No commit on the PR has a check rollup: the repository has no CI.
  const noCi = {
    fastPath: noChecksMessage,
    commitRollups: [
      { oid: "older", state: null },
      { oid: "head", state: null },
    ],
  } as const;
  function ticking(): WatchClock {
    let now = 0;
    return {
      now: () => now,
      observedAt: () => new Date(now * 1000).toISOString(),
      async sleep(seconds) {
        now += seconds;
      },
    };
  }
  const run = (
    reader: GitHubReader,
    clock: WatchClock,
    emitted: ProgressVerdict[],
    overrides: { statusOnly?: boolean; timeout?: number } = {}
  ) =>
    runSimple({
      dependencies: { reader, clock, emit: (verdict) => emitted.push(verdict) },
      contexts: [context(30)],
      mode: "single",
      statusOnly: overrides.statusOnly ?? false,
      options: { ...options, timeout: overrides.timeout ?? 0 },
    });

  // Adapted from upstream PR #510: a confirmed check-less head is clean.
  it("treats a PR with no configured checks as clean once confirmed", async () => {
    const snapshot = await readSnapshot({
      reader: fakeReader(noCi),
      context: context(3),
      pendingHistory: "include",
      allowDraft: false,
      confirmNoChecks: () => true,
    });
    expect(snapshot.kind).toBe("open");
    if (snapshot.kind !== "open") throw new Error("expected open snapshot");
    expect(snapshot.ci.kind).toBe("ci-clean");
    expect(snapshot.ci.all).toEqual([]);
    expect(classifyPr(snapshot)).toMatchObject({ kind: "ready" });
  });

  it("waits on a first sighting instead of reporting ready", async () => {
    const snapshot = await readSnapshot({
      reader: fakeReader(noCi),
      context: context(3),
      pendingHistory: "include",
      allowDraft: false,
    });
    expect(snapshot).toMatchObject({
      kind: "open",
      ci: {
        kind: "ci-pending",
        all: [],
        pending: [{ reportedState: NO_CHECKS_REPORTED_STATE }],
      },
    });
    expect(classifyPr(snapshot)).toMatchObject({ kind: "waiting" });
  });

  // Bugbot's finding on upstream PR #510: right after a push, gh says "no
  // checks reported" because the workflows have not registered yet.
  it("is not ready right after a push when an earlier PR commit had checks", async () => {
    const reader = fakeReader({
      fastPath: noChecksMessage,
      commitRollups: [
        { oid: "older", state: "SUCCESS" },
        { oid: "head", state: null },
      ],
    });
    await expect(
      readSnapshot({
        reader,
        context: context(3),
        pendingHistory: "include",
        allowDraft: false,
        confirmNoChecks: () => true,
      })
    ).rejects.toBeInstanceOf(ChecksUnavailable);

    const emitted: ProgressVerdict[] = [];
    const verdict = await run(reader, ticking(), emitted, { timeout: 600 });
    expect(verdict.kind).not.toBe("READY");
    expect(emitted.length).toBeGreaterThan(0);
    expect(emitted.every((event) => event.kind === "RETRY")).toBe(true);
  });

  it("fails closed when the head commit has a rollup the readers did not list", async () => {
    await expect(
      readSnapshot({
        reader: fakeReader({
          fastPath: noChecksMessage,
          commitRollups: [{ oid: "head", state: "PENDING" }],
        }),
        context: context(3),
        pendingHistory: "omit",
        allowDraft: false,
        confirmNoChecks: () => true,
      })
    ).rejects.toBeInstanceOf(ChecksUnavailable);
  });

  it("fails closed when the head commit is missing from the commit list", async () => {
    await expect(
      readSnapshot({
        reader: fakeReader({
          fastPath: noChecksMessage,
          commitRollups: [{ oid: "older", state: null }],
        }),
        context: context(3),
        pendingHistory: "include",
        allowDraft: false,
        confirmNoChecks: () => true,
      })
    ).rejects.toBeInstanceOf(ChecksUnavailable);
  });

  it("confirms only once the same head has stayed check-less for 60 seconds", () => {
    expect(NO_CHECKS_CONFIRM_SECONDS).toBe(60);
    let now = 0;
    const confirm = noChecksConfirmer({ now: () => now });
    const head = { context: context(30), headRefOid: "head" };
    expect(confirm(head)).toBe(false);
    now = 59;
    expect(confirm(head)).toBe(false);
    now = 60;
    expect(confirm(head)).toBe(true);
    const pushed = { ...head, headRefOid: "pushed" };
    expect(confirm(pushed)).toBe(false);
    now = 119;
    expect(confirm(pushed)).toBe(false);
    now = 120;
    expect(confirm(pushed)).toBe(true);
    const other = { context: context(31), headRefOid: "head" };
    expect(confirm(other)).toBe(false);
  });

  it("reports READY only after the clock passes 60 seconds on the same head", async () => {
    const clock = ticking();
    const emitted: ProgressVerdict[] = [];
    const verdict = await run(fakeReader(noCi), clock, emitted);
    expect(emitted.map((event) => event.kind)).toEqual(
      Array.from({ length: 6 }, () => "WAITING")
    );
    expect(clock.now()).toBe(60);
    expect(verdict).toMatchObject({
      kind: "READY",
      scope: { pr: { proof: { ci: { kind: "ci-clean", all: [] } } } },
    });
  });

  it("times out instead of reporting READY when the deadline is under 60 seconds", async () => {
    const verdict = await run(fakeReader(noCi), ticking(), [], {
      timeout: 30,
    });
    expect(verdict).toMatchObject({
      kind: "TIMEOUT",
      exitCode: 5,
      reason: { kind: "pending-checks" },
    });
  });

  it("holds a queued frontier as pending until the head is confirmed", async () => {
    const clock = ticking();
    const emitted: ProgressVerdict[] = [];
    const running = runQueued({
      dependencies: {
        reader: fakeReader(noCi),
        clock: {
          ...clock,
          async sleep(seconds) {
            await clock.sleep(seconds);
            if (clock.now() > 60) throw new Error("stop after confirmation");
          },
        },
        emit: (verdict) => emitted.push(verdict),
      },
      contexts: [context(30)],
      options,
    });
    await expect(running).rejects.toThrow("stop after confirmation");
    const waits = emitted.flatMap((event) =>
      event.kind === "WAITING" ? [event.reason.kind] : []
    );
    expect(waits).toEqual(["pending-checks", "merge-queue"]);
  });

  it("reports status-only as not yet confirmed, in a parseable row", async () => {
    const clock = ticking();
    const verdict = await run(fakeReader(noCi), clock, [], {
      statusOnly: true,
    });
    expect(verdict).toMatchObject({
      kind: "STATUS",
      exitCode: 0,
      rows: [
        {
          ci: {
            kind: "ci-pending",
            pending: [{ reportedState: NO_CHECKS_REPORTED_STATE }],
          },
        },
      ],
    });
    expect(clock.now()).toBe(0);
    expect(renderPretty(verdict)).toContain("| ⏳ 1 pending |");
    expect(JSON.parse(renderJson(verdict))).toMatchObject({
      kind: "STATUS",
      rows: [{ ci: { pending: [{ name: "no checks reported yet" }] } }],
    });
  });
});

it("never reports READY when a required review is missing or GitHub blocks the merge", async () => {
  const cases = [
    [{ reviewDecision: "REVIEW_REQUIRED" }, "review-required", "approving review"],
    [{ mergeStateStatus: "BLOCKED" }, "merge-blocked", "branch protection"],
  ] as const;
  for (const [facts, reason, action] of cases) {
    const row = await readSnapshot({
      reader: fakeReader({ facts }),
      context: context(21),
      pendingHistory: "omit",
      allowDraft: false,
    });
    const decision = classifyPr(row);
    expect(decision).toMatchObject({ kind: "blocker", blocker: { kind: "merge-gate", reason } });
    if (decision.kind !== "blocker") throw new Error("expected a blocker");
    const text = renderPretty({
      schemaVersion: 1,
      sequence: 1,
      observedAt: "2026-01-01T00:00:00Z",
      mode: "single",
      kind: "BLOCKER",
      terminal: true,
      exitCode: 6,
      blocker: decision.blocker,
    } as Parameters<typeof renderPretty>[0]);
    expect(text).toContain(`BLOCKER: ${reason}`);
    expect(text).toContain(action);
  }
});

it("waits, not blocks, while GitHub says BLOCKED because required checks still run", async () => {
  const row = await readSnapshot({
    reader: fakeReader({
      facts: { mergeStateStatus: "BLOCKED" },
      fastPath: { kind: "checks", checks: [pendingCheck()] },
    }),
    context: context(22),
    pendingHistory: "omit",
    allowDraft: false,
  });
  expect(classifyPr(row).kind).toBe("waiting");
});
