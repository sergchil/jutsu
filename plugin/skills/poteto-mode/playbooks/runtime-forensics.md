### Runtime forensics

**You own the diagnosis. Instrument the live process, don't theorize from source.** The deliverable is a cited diagnosis, not a fix.

1. Capture the live signal: a CPU profile for a spinning process, a heap snapshot for a leak, a CDP trace for a visual glitch. A real artifact, not a guess. T3 has no profiler tool, so use the target's own. For Node and Bun, run with `--cpu-prof`, `--heap-prof`, or `--inspect` and a CDP client. For a macOS process, use `sample <pid>`, `spindump`, `leaks`, `heap`, or `vmmap`. For a simulator app, use `xcrun xctrace record --attach <pid>`. For a web page, take traces and heap snapshots through a CDP driver.
2. Reduce the artifact to the smoking gun: the function on the hot path, the retainer chain from the leaked object to a GC root, the loop firing without input. Parse large artifacts in a subagent (the **guard-the-context-window** principle skill, `../../../principles/principle-guard-the-context-window.md`), keep the reduced finding in the main thread. Pick each subagent's `effort` for the job, per the Subagents section.
3. Prove the mechanism before believing it. Inject instrumentation via CDP eval on the running process (`preview_evaluate` for a page in a T3 preview tab, which runs page JS only), or hotfix the live code without reloading, to confirm the hypothesis cheaply.
4. Map the finding back to source: file, symbol, the line that allocates or schedules.
5. Throughput checkpoint stays one line: `throughput checkpoint: n/a, read-only forensics`.

**Reply:** the signal captured, the reduced finding, how you proved the mechanism, the source location, artifact paths. No fix unless asked. Hand back to Bug fix or Perf once the cause is known.
