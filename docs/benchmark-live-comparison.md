# Local comparison screen

Run the fixed-fixture three-system harness from a loopback UI:

```sh
python -m kora.benchmarks.dashboard \
  --config /path/to/private-systems.json \
  --fixtures examples/benchmarks/three-environment/s3-workloads.json \
  --output /path/to/private-run-directory --port 9190
```

Open `http://127.0.0.1:9190` on the controller machine. Remote workers remain
behind authenticated SSH tunnels. Do not expose this loopback server publicly.
Worker credentials are read from configured environment variables and never sent
to the page. Requests require the page token and matching loopback Host/Origin.

The S3 corpus has thirteen fixed cases: six original calculation/classification
cases, one order-cleaning case and six bounded template-reply cases. D calculates
or cleans orders, M classifies or generates a template reply, and W combines both.
Changed input increments quantity (the first row for orders) and replaces model
input, prompt, contract and expected output with the next cyclic case. M always
bypasses exact reuse. Reply quality means exact template and case-ID correctness,
not open-ended writing quality. Original six-case fixtures remain unchanged.

Order cleaning normalizes NFKC IDs/SKUs, checks ASCII formats and integer bounds,
deduplicates by first valid ID and totals accepted rows. Rejected rows and duplicate
indices remain in the output. No arbitrary corpus, endpoint or command is accepted.

## Evidence

A run creates addressable `state.json`, `events.jsonl`, and `results.jsonl` under
a unique UUID directory. Results include failures/blocked outcomes, quality,
controller elapsed time, nodes, actual completed model calls and new output
tokens. Uncertain failed model execution is not proof that no call occurred.
The screen shows the most recent outcome and aggregate counters per system.
Events describe real progress. Saved runs are labelled recorded; unfinished
runs discovered after controller restart are labelled interrupted.

Execution is serial across systems to avoid overlapping worker load; timing
includes dispatch and network overhead. Background load and cold/warm state
are not controlled by this screen. It does not claim statistical superiority,
energy savings, production performance, token throughput or H100 parity.
Native D runs arithmetic on the controller CPU, never on the H100 GPU.

## Exact reuse boundary

Only successful, quality-passing, side-effect-free fixture nodes are cached.
Keys include code, fixture snapshot, whole fixture and prompt, system configuration,
operation input, worker identity/boot ID and declared backend generation identity.
Changing any of these invalidates reuse. This conservative key intentionally
invalidates both nodes on any fixture change. Legacy model workers without a
configured generation identity cannot produce model cache hits.

Files are atomically replaced, checksum checked and capped at 256 entries.
Corruption is a miss. Failed quality does not populate cache. Reuse preserves
source job/activity provenance but reports zero new model calls and output tokens.
Cached worker identity is not evidence of new cluster execution. H100 never uses
this cache. Cache-off here measures removal of exact reuse on the same runner;
it is not a complete KORA-off hardware baseline.

Identity is operator-configured, not cryptographic runtime attestation. Restart
the worker after changing a backend/model even if its served alias is unchanged.
Do not mutate model files under a running pinned process. Multiple controllers
must not launch concurrent runs against the same workers. The UI serializes its
own sessions only; this is not a distributed scheduler.

## Native GPU window

Native model execution is blocked by default. No GPU service is stopped by this
application. First arrange an authorized window, acquire the shared lease, launch
the native model in that lease's named unit, and verify its model/health. Supply
`--native-guard-config /path/to/private-guard.json` only for that window. The JSON
has `command` (argv list for a read-only live board query), `lease_id`, `project`,
and `unit`. The command executes on the controller, never from browser input.

The guard checks fresh observation (within 30 seconds), matching lease/project/unit,
expected end, and that all observed GPU compute processes belong to the named unit.
It checks before each native model case and refuses stale/foreign/expired state.
It is cooperative and has a check-to-execution race; it is not GPU isolation.
Stop owned GPU work, restore any borrowed service, verify health, then release.
Do not treat the existence of a guard configuration as permission to stop services.
