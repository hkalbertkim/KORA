# KORA Studio Local Limits & Upgrade Detection Specification v1.0

Status: Product Logic & Policy Draft  
Language: English (Official Document)  
Purpose: Define deterministic, measurable rules for detecting local capability limits in KORA Studio and triggering optional upgrade suggestions to Krako Cloud.

---

# 1. Principles

Upgrade detection must be:

• Deterministic  
• Measurable  
• Conservative (avoid noisy prompts)  
• Non-blocking  
• Suggestion-only (never forced routing)  

KORA Studio must always remain functional without Krako.

---

# 2. Observed Signals (Local Telemetry Inputs)

Upgrade detection uses local telemetry signals:

Hardware & runtime signals:

• gpu_vram_total_mb  
• gpu_vram_free_mb  
• cpu_cores  
• cpu_load_p95  
• ram_free_mb

Execution signals (per run):

• tokens_in, tokens_out, total_tokens  
• model_latency_ms_p95  
• total_latency_ms  
• deterministic_stage_ms  
• model_stage_ms  
• validation_retry_count  
• budget_breach_count

Concurrency signals:

• active_sessions  
• active_generations  
• queue_wait_ms_p95

---

# 3. Local Capability Profile

On startup, Studio computes a LocalCapabilityProfile:

• max_recommended_model_vram_mb  
• max_recommended_context_tokens  
• max_recommended_concurrency

This profile is used for upgrade suggestions.

---

# 4. Primary Trigger Categories

There are five trigger categories.

## 4.1 Model Fit Trigger (VRAM/RAM)

Trigger when any holds:

• model_required_vram_mb > gpu_vram_total_mb  
• model_required_vram_mb > (gpu_vram_free_mb + vram_reclaimable_mb_est)  
• model_load_failure_count >= 1

Actions:

• Suggest smaller/quantized model first  
• If user insists on same tier, suggest Krako Cloud

---

## 4.2 Context Window Trigger

Trigger when:

• requested_context_tokens > local_supported_context_tokens

Or when:

• local_context_oom_event = true

Actions:

• Suggest context reduction or summarization mode  
• Suggest Cloud if user requires full context

---

## 4.3 Latency Trigger (Tail Latency)

Compute rolling p95 over last N runs:

• N = 10 (default)

Trigger when either:

• model_latency_ms_p95 > LAT_P95_LIMIT_MS  
• total_latency_ms_p95 > TOTAL_P95_LIMIT_MS

Default thresholds:

• LAT_P95_LIMIT_MS = 4500  
• TOTAL_P95_LIMIT_MS = 6500

Sustained condition requirement:

• Must persist for W windows
• W = 3 consecutive windows

Actions:

• Suggest enabling more deterministic filtering  
• Suggest Cloud for performance tier

---

## 4.4 Concurrency Trigger

Trigger when:

• active_sessions > max_recommended_concurrency

Or when:

• queue_wait_ms_p95 > QUEUE_WAIT_LIMIT_MS

Default:

• QUEUE_WAIT_LIMIT_MS = 1200

Sustained condition requirement:

• Persist for 3 consecutive windows

Actions:

• Suggest Cloud for multi-user / multi-session scaling

---

## 4.5 Reliability Trigger (Retry & Validation Instability)

Trigger when:

• validation_retry_count_p95 > RETRY_P95_LIMIT

Or:

• budget_breach_count > 0 in last N runs

Default:

• RETRY_P95_LIMIT = 2

Interpretation:

High retries may indicate:

• model too small for schema constraints  
• local inference instability  
• insufficient context window

Actions:

• Suggest switching to a stronger local model  
• If not possible locally, suggest Cloud

---

# 5. Suggestion Policy (Anti-Spam)

## 5.1 Cooldown Rules

To avoid repeated prompts:

• Same trigger category cannot show more than once per 30 minutes  
• Same request signature cannot trigger suggestion more than once per session

Request signature is derived from:

• normalized user prompt hash  
• selected model id  
• context token size bucket

---

## 5.2 Escalation Ladder

Upgrade is suggested only after local mitigations are offered.

Mitigation order:

1. Suggest smaller/quantized local model  
2. Suggest deterministic-first enhancements (more filtering)  
3. Suggest lower context mode  
4. Suggest Krako Cloud

Cloud suggestion must include:

• explicit reason  
• predicted improvement  
• predicted cost

---

# 6. Suggested Upgrade Messaging

Upgrade messaging must be:

• factual  
• non-coercive  
• cost-transparent

Template:

"Local execution hit a limit: {reason}. You can:
(1) try {local_mitigation}
(2) upgrade to Krako Cloud for {benefit_estimate} at ~{cost_estimate}."

---

# 7. Cloud Readiness Check

Before enabling Cloud suggestion actions:

• KrakoBackend plugin installed?  
• Network available?  
• User authenticated?  
• Credits available?

If not ready:

• Suggest installing plugin / logging in  
• Do not block local execution

---

# 8. Metrics for Product Validation

Studio must log aggregated statistics:

• upgrade_suggestion_count  
• suggestion_accept_rate  
• suggestion_dismiss_rate  
• top_trigger_categories  
• local_mitigation_success_rate

These metrics must remain local-only unless user opts in.

---

# 9. Safety Constraints

Studio must never:

• Automatically route to cloud without explicit opt-in  
• Hide that cloud execution occurred  
• Hide cost estimates  
• Suggest upgrade without a measurable trigger

---

# 10. Versioning

All thresholds are versioned.

Changes to:

• trigger definitions  
• threshold values  
• cooldown rules

Require:

• MINOR version increment

---

# Final Position

Upgrade detection is a transparency feature.
It must protect user trust.

KORA Studio remains local-first.
Krako Cloud is optional scale.

---

End of Document

