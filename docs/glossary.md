# Glossary

This glossary defines terms used across the KORA documentation.

Definitions are architectural, not marketing descriptions.

---

## Aggregation Task

A deterministic task that combines outputs from dependent tasks into a final structured result. Aggregation tasks must not invoke models.

---

## Atomic Task

The smallest executable unit in KORA.

An atomic task is:

- Typed
- Bounded
- Schema-constrained
- Independently executable

Atomic tasks enable decomposition and routing.

---

## Budget Governance

The enforcement of resource limits on model-bound tasks.

Includes:

- max_tokens
- max_time_ms
- max_retries

Budget is contractual, not advisory.

---

## Compute Neutrality

Architectural principle that KORA does not bind execution to a specific hardware class or model vendor.

Tasks may execute on heterogeneous compute resources.

---

## Decomposition

The process of splitting complex requests into atomic tasks.
<br>In KORA, decomposition is native and structural.
<br>It precedes inference.

---

## Deterministic Task

A task executed without invoking probabilistic reasoning.
<br>Examples include arithmetic, lookup, structural transformation, and aggregation.
<br>Deterministic tasks must be pure and bounded.

---

## Decomposition-Native Foundation Model (DNFM)

A proposed future model architecture that accepts structured task graphs rather than monolithic prompts. DNFM is a research direction implied by KORA's structural principles.

---

## Directed Acyclic Graph (DAG)

The execution structure of tasks in KORA.

Ensures:

- Explicit dependencies
- No cycles
- Parallelizable execution

---

## Inference Reflexivity

Architectural pattern where every request triggers a model invocation without evaluating necessity. KORA exists to eliminate inference reflexivity.

---

## Model Task

A task requiring probabilistic reasoning through a model invocation.
<br>Model tasks must declare budget and schema.

---

## Observability

The structured emission of telemetry data for each task.
<br>Enables measurement of:

- Cost
- Latency
- Retry behavior
- Decomposition coverage

---

## Orchestrator

The component responsible for:

- Building the task graph
- Validating dependencies
- Routing tasks
- Aggregating results

The orchestrator maintains structural authority.

---

## Reasoning Adapter

Abstraction layer that mediates all model invocations.

Ensures:

- Budget enforcement
- Schema validation
- Routing flexibility
- Vendor neutrality

---

## Routing

The process of assigning atomic tasks to execution backends.
<br>Routing decisions are policy-driven and respect budget and security constraints.

---

## Schema Validation

The process of verifying that model output conforms to an explicit JSON schema.
<br>Validation is mandatory before aggregation.

---

## Structural Overhead

The additional execution cost introduced by:

- Task construction
- DAG validation
- Schema validation
- Telemetry logging

Structural overhead must remain bounded.

---

## Structural Intelligence

The principle that reasoning should be governed by explicit task structure rather than monolithic prompts. Structure precedes scale.

---

## Task IR (Task Intermediate Representation)

The structured object representing a unit of execution.

Task IR defines:

- Type
- Dependencies
- Input
- Schema
- Budget
- Routing metadata

Task IR is the foundation of KORA execution.

---

## Telemetry

Structured logging emitted by tasks during execution.

Telemetry supports:

- Falsifiability
- Performance modeling
- Budget auditing
- Security monitoring

---

## Trust Boundary

The boundary at which outputs must be validated before acceptance.
<br>In KORA, schema validation defines the primary trust boundary.

---

## Versioning

The practice of maintaining explicit version identifiers for Task IR schema to preserve backward compatibility and prevent architectural drift.

---

## Closing Note

Terminology in KORA is structural.

Words such as decomposition, determinism, and neutrality are architectural commitments, not metaphors.

Consistency of definition preserves integrity of the system.
