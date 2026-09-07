# Task025 — S3 initial comparison implementation

Classification: needs-cto-review. S3 remains OPEN; not merge-ready.

Implemented local three-column UI, run API, durable event/results and recorded-run
lookup; fixed D/M/W controls; quality-gated exact node reuse and invalidation;
explicit actual model/token accounting; configured worker identity; native lease
guard and loopback Host/Origin/token checks. No Core contracts changed.

Automated QC: full regression 736 passed; final focused controller suite 11 passed;
Ruff, JavaScript syntax, release smoke and wheel asset inclusion passed.
Automated Visual QC / Human Visual Review: not performed. HTTP/API tests do not
constitute browser visual or interaction verification.

Bounded live evidence (six fixed cases):

| Scenario | MP quality | Cluster quality | Model calls per system | Native |
|---|---|---|---|---|
| D, five repeats | 30/30 | 30/30 | 0 | 30/30 controller CPU only |
| M, five repeats | 30/30 | 30/30 | 30 | 30 blocked |
| W, reuse off, five repeats | 30/30 | 30/30 | 30 | 30 blocked |
| W, reuse on, two repeats | 12/12 | 12/12 | 6 | 12 blocked |
| Changed W, two repeats | 12/12 | 12/12 | 6 | 12 blocked |

Each repeated W set reused 12 nodes per Mac system. Changed input invalidated the
original entries, executed six new model calls, then reused its second repetition.
Native model rows are blocked by an unavailable service window, never omitted.
Earlier S2 native acceptance is historical, not S3 native validation.
The broad live batch preceded final guard/UI/provenance polish; a final-source
HTTP smoke verified fresh/reused W outcomes and zero new activity on the repeat.

Remaining S3 work: native window acceptance; browser visual and interaction QA;
expanded reference workload coverage beyond short calculation/classification;
controlled cold/warm and concurrent evidence plus same-device KORA-off/on evidence;
representative older hardware inventory/measurement with explicit unavailable states;
review and authorized commit/push/PR. Existing reuse-off comparison is only an
exact-reuse ablation, not complete KORA-off evidence. No broad performance claim.
Feature freeze remains September 25 18:00 KST; S4/readiness dates unchanged.

## Native window follow-up — 2026-09-06

User authorized this and subsequent equivalent bounded temporary handovers without
repeated approval; live lease/request/ownership checks and restoration still apply.
Five HTTP comparison batches all passed across the three systems. D30/30 per
system (native D is controller CPU); M30/30 and W-reuse-off30/30 per system, each
with30 calls and300 new output tokens. W-repeat and changed-W each12/12 per system.
Mac caches already contained these inputs from the prior acceptance: each reused
24 nodes with0 new model calls; H100 executed12 calls/120 tokens in each set. This
window is warm-cache validation, not fresh invalidation proof. Prior fresh-cache
validation remains separately recorded. Native total84 actual model calls.
Earlier blocked rows are retained; they are not rewritten as success.

Latest UI history is now chronological with readable time/scenario labels and
automatically selects the latest saved run, explicitly labelled recorded. Focused
controller tests11 passed after this presentation change; Ruff/JS syntax passed.
Native acceptance used the pre-presentation-change code snapshot recorded per run.
No new full-regression claim is made for the subsequent presentation-only edit.

Native acceptance gate passed. Service restoration is tracked in the private
handoff. Remaining S3: browser/visual QA, broader reference scenarios, controlled
measurement and KORA-off/on evidence, representative older hardware, integration
review. S3 remains open.

## Same-device model-only adapter comparison

Added a direct backend adapter without worker routing or exact result reuse.
On the same MP backend, six cases x five repetitions per mode passed30/30
both directly and through the worker. Mode order alternated by repetition.
Median controller latency: direct281.27ms, worker285.96ms; each mode made30
actual model calls. These are short classification requests on an already
loaded model with uncontrolled background load, not a cold-start or throughput
benchmark. The difference between medians is not paired per-request overhead
or a general KORA effect. No speedup claim. Direct-adapter quality/schema
failure accounting tests3 passed. Full regression736 predates this module.

## S3 reference integration — 2026-09-06

Order cleaning now runs through authenticated workers, runner, direct baseline,
exact reuse and UI. Thirteen S3 fixtures retain the original six cases and add
order normalization/deduplication/rules and six versioned template replies with
unique case IDs. Exact replies are not general writing-quality evidence.

Full regression: 748 passed. HTTP tests cover order execution, repeat reuse and
changed-input invalidation. Live MP/cluster order D/W original/changed batches
passed eight/eight per system; native D passed four/four on controller CPU.
First W reused earlier D cache entries; this is not a fresh mixed-run claim.

Reply generation passed 30/30 per Mac system, 30 calls each; median controller
latencies were 540.95 ms (MP) and 673.34 ms (cluster model worker). Native window
passed 35/35: 30 reply and five mixed-order requests, each with a model call.
Raw outputs and per-request timings are retained privately. Different precision,
resident models and uncontrolled background load prevent hardware/general claims.

Configured access covers the current two Mac workers and H100. No older-Mac
endpoint was available in that inventory: older devices remain unmeasured.
Browser visual QA remains unverified because the available browser cannot reach
the private controller loopback. No access-control bypass or public exposure was
introduced. Cold startup remains unmeasured; resident-model measurements are
labelled. S3 remains open pending those evidence gaps and integration review.

## Resident-model concurrency observation

On MP, direct single-request execution passed6/6, direct paired concurrent requests
passed12/12, worker single-request execution passed6/6, and worker paired concurrent
requests passed6/12. All outcomes remain recorded. The worker deliberately admits
one job at a time and refuses overlapping work; this harness has no shared queue.
These small observations describe admission behavior, not a throughput advantage.
Cold-start inference remains unmeasured.

## Process-start follow-up

Three MP model-process restarts passed18/18: first requests3/3 and subsequent
requests15/15. First-request median557.41ms (531.39–590.95); resident median517.40ms
(467.28–580.54). OS/file caches were not cleared. This is process-start evidence,
not storage-cold or statistically conclusive latency evidence. An initial operational
measurement attempt stopped on child reaping; the model was restored, the helper
repaired and subsequent samples saved incrementally. The interrupted attempt is
recorded separately and is not silently counted as a successful full sample.
The available browser rejected both private-loopback and isolated-preview navigation;
visual QA remains unverified. No workaround bypassing browser policy was used.

## Integration review — 2026-09-07

Fixed a self-referential changed-input quality oracle: expected results no longer
come from the deterministic implementation being tested. The changed fixed fixture
updates its preregistered oracle independently. An injected wrong arithmetic result
now fails all three comparison paths. Full regression749 passed; Ruff passed.
Earlier changed-input passes alone were not independent correctness evidence;
new runtime validation is recorded separately. No browser-policy bypass attempted.
