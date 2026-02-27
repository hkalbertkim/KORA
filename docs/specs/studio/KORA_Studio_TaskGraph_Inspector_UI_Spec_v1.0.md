# KORA Studio TaskGraph Inspector UI Specification v1.0

Status: Product UX Detail Draft  
Language: English (Official Document)  
Purpose: Define the detailed UI/UX behavior of the TaskGraph Inspector in KORA Studio Advanced Mode, including node interactions, detail panels, filtering, and export.

---

# 1. Scope

This specification applies to KORA Studio Advanced Mode.

It defines:

• TaskGraph visualization and interaction model  
• Node-level detail inspection  
• Stage timeline correlation  
• Schema/validation visibility  
• Retry and budget traces  
• Export and debugging workflows

Non-goals:

• Implementation details (framework-specific)  
• Styling system beyond functional requirements

---

# 2. Entry Points

The TaskGraph Inspector is accessible via:

• Toggle: "Show Execution Details"  
• Tab within Telemetry Panel: "TaskGraph"  

Default behavior:

• Opens on the most recent assistant response execution.  
• Falls back to last completed run if current run is in-progress.

---

# 3. Layout and Components

## 3.1 Telemetry Panel Tabs

Tabs:

• Overview  
• Stage Timeline  
• TaskGraph  
• Event Log (optional, collapsed by default)

The TaskGraph tab contains:

• Graph Canvas (center)  
• Graph Controls (top bar)  
• Node Detail Drawer (right or bottom)  

---

# 4. Graph Canvas

## 4.1 Rendering Requirements

The graph must render:

• Nodes (tasks)  
• Directed edges (dependencies)  
• Acyclic structure representation

Minimum supported graph size:

• 200 nodes visible with pan/zoom without UI freeze.

Graph layout:

• Default: Left-to-right (dependencies → dependents)  
• Alternative: Top-to-bottom (user selectable)

---

## 4.2 Node Visual Encoding

Each node displays:

• Task label (name or short ID)  
• Task type badge:
  - deterministic
  - model
  - aggregation
• Execution state badge:
  - queued
  - ready
  - running
  - success
  - failed
  - timeout
  - skipped

Optional small counters (Advanced):

• retries: n

Color is not specified here; the UI must remain readable in light/dark modes.

---

## 4.3 Edge Visual Encoding

Edges represent dependency.

Rules:

• Solid arrow for strict dependency.  
• No speculative execution in v1.0 (no dotted edges).

---

# 5. Graph Controls (Top Bar)

Controls must include:

• Search by task id/name  
• Filter by task type (deterministic/model/aggregation)  
• Filter by state (success/failed/running/skipped)  
• Toggle: Show IDs  
• Toggle: Show retries  
• Zoom in/out  
• Fit to screen  
• Reset view

Advanced controls (collapsed):

• Group by stage  
• Show critical path  
• Highlight budgeted tasks

---

# 6. Node Interaction Model

## 6.1 Hover

On hover, show tooltip:

• task_id (short)  
• type  
• status  
• duration_ms (if completed)  
• tokens_in/tokens_out (if model task)

---

## 6.2 Click

On click, open Node Detail Drawer.

Behavior:

• Drawer opens with Summary section expanded.  
• Graph highlights selected node.  
• All upstream dependencies highlight as "inputs" (optional toggle).  
• All downstream dependents highlight as "consumers" (optional toggle).

---

## 6.3 Multi-select (Optional)

If multi-select is enabled:

• Shift-click selects multiple nodes.  
• Drawer switches to "Batch View".

Batch View shows:

• Total duration  
• Total tokens  
• Failure count  
• Retry count

Multi-select is optional in v1.0.

---

# 7. Node Detail Drawer

The drawer contains the following sections.

## 7.1 Summary (Always Present)

• task_id (full)  
• task_name  
• task_type  
• status  
• started_at / finished_at  
• duration_ms  
• retry_count  

---

## 7.2 Inputs

Display:

• Input payload (pretty JSON)  
• Input size (bytes)  
• Source references (dependency outputs)

Controls:

• Copy JSON  
• Collapse large fields

---

## 7.3 Schema & Validation

Display:

• Output schema (JSON schema)  
• validation_status (pass/fail)  
• validation_errors (if any)  

Rules:

• No silent acceptance of invalid outputs.  
• Validation failures must show the exact failing fields.

---

## 7.4 Budget

Display:

• max_tokens  
• max_time_ms  
• max_retries  

If budget breach occurred:

• breach_type (TOKENS/TIME/RETRIES)  
• breach_stage  
• remaining_budget snapshot (if available)

---

## 7.5 Model Invocation (Model Tasks Only)

Display:

• backend (local runtime name)  
• model identifier  
• tokens_in / tokens_out / total_tokens  
• latency_ms  

Optional (dev mode):

• request payload (redacted)  
• response payload (redacted)

---

## 7.6 Retry Timeline

Display list of attempts:

• attempt_index  
• stop_reason / error_code  
• retryable flag  
• backoff_ms (planned)  
• duration per attempt  

Rule:

• Retries must be visible; no hidden retry loops.

---

## 7.7 Telemetry Events (Task-scoped)

Display a compact sequence:

• task.created  
• task.started  
• task.completed / task.failed  
• task.validated

Events must link to full Event Log view.

---

# 8. Correlation with Stage Timeline

When a node is selected:

• Stage Timeline must highlight the corresponding time interval.  
• The timeline must show where time was spent:
  - deterministic
  - model invocation
  - validation
  - aggregation

A "jump to timeline" button must be present.

---

# 9. Export & Debugging

## 9.1 Export Options

From TaskGraph tab:

• Export TaskGraph JSON  
• Export Telemetry JSON  
• Export Markdown summary  

From Node Drawer:

• Export node detail JSON  
• Copy shareable debug snippet

All exports must be local-only by default.

---

## 9.2 Re-run From Node (Dev Mode Only)

Optional feature:

• Re-run a deterministic node locally

Constraints:

• Must not mutate historical telemetry  
• Must create a new run_id

---

# 10. Accessibility and Performance Requirements

• Keyboard navigation support for node selection  
• Search must be responsive under 200 nodes  
• Large graphs require progressive rendering

---

# 11. Summary

The TaskGraph Inspector must:

• Make structure explorable  
• Make costs measurable  
• Make failures debuggable  
• Make retries visible  
• Preserve clarity without overwhelming Basic Mode users

Execution transparency is a primary product differentiator.

---

End of Document

