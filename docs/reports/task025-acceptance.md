# S3 acceptance packet

Status: needs-cto-review. Proposal only; S3 remains open and PR295 remains unmerged.
Reviewed implementation head: 4af29c3. Regression: 749 passed; CI passed.

## Verified evidence

| Check | Outcome | Limit |
|---|---|---|
| Changed calculation and order cleaning, independent fixed oracle | MP4/4, cluster4/4, native-client4/4 | Native D is controller CPU, not GPU |
| Bounded template replies | MP30/30, cluster30/30, native30/30 | Exact templates, no open-ended quality proof |
| Native mixed order workload | 5/5, five model calls | Separate authorized window |
| Model process first request / resident repeats | 3/3 and15/15 | MP only; OS/file cache not cleared |
| Same-device direct / worker, single request | 6/6 each | Small resident-model adapter comparison |
| Same-device direct / worker, two overlapping requests | 12/12 versus6/12 | Worker admission is one job; failed requests retained |
| Exact reuse and changed input | Prior first/repeat/changed evidence plus fault injection | Earlier self-referential oracle corrected in4af29c3 |
| Native handover | Existing service restored, lease released | Historical verification; no new window needed for this review |

Raw evidence was inspected, not inferred from test totals. Initial six cluster
transport failures remain in historical results and are not included as successes
in the separate final twelve-row changed-input batch. API checks are not visual QA.

## Unresolved acceptance criteria

1. Visual QA: the available browser rejected both the private-loopback page and
   isolated preview navigation. No alternate browser route or policy bypass used.
2. Older hardware: configured access covers the core comparison machines only.
   Older devices remain unmeasured; their model/runtime support is not established.

These are acceptance gaps, not code tests that can be closed by rerunning CI.
The current sprint scope and dates are unchanged.

## Proposed decision, not yet approved

Accept the implementation as a bounded S3 delivery, merge PR295, and record S3 as
conditionally closed rather than fully passed. Carry the two unresolved items as
explicit S4 acceptance gates. Before final exhibition readiness:

- inspect the rendered comparison controls, changed-input preview, results,
  failure/recorded labels and export in an authorized reachable browser;
- identify and connect the representative older devices, measure supported
  configurations and label inaccessible/incompatible cases accurately.

Do not call either gate passed before evidence exists. If the proposal is declined,
S3 remains open; the next required inputs are an authorized visual-review route and
older-device access. No additional feature work is proposed.
