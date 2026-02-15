# Contributing to KORA

KORA is an execution architecture, not a feature collection.

Contributions must preserve structural discipline.

Before submitting code, understand the philosophy:

- Determinism before inference
- Native decomposition
- Budget governance
- Schema validation
- Compute neutrality

KORA is minimal by design.

---

## 1. Contribution Principles

All contributions must satisfy the following:

### 1. Structure Over Convenience

Do not introduce shortcuts that reintroduce inference reflexivity.

Every model invocation must be:

- Explicit
- Bounded
- Schema-validated

No hidden calls.
No silent retries.

---

### 2. Deterministic-First Discipline

If a task can be resolved without inference, it must not invoke a model.

Contributors should always ask:

*Can this be deterministic?*

If yes, implement deterministic resolution.

---

### 3. No Feature Bloat

KORA is not:

- A chatbot wrapper
- An agent playground
- A prompt template library
- A model training framework

Do not add features that expand surface area without strengthening structure.

Minimalism preserves clarity.

---

### 4. Measurability Required

All new features must be measurable.

Add telemetry where appropriate.

If a change affects:

- Model invocation count
- Token usage
- Latency
- Retry behavior

It must be observable.

Architecture without metrics degrades.

---

## 2. Code Standards

### Deterministic Layer

- Pure functions where possible
- No hidden state
- Explicit error handling

### Model Layer

- Invocation must pass through reasoning adapter
- Budget constraints required
- Schema required
- Retry count bounded

### Validation Layer

- No acceptance of unvalidated model output
- Strict JSON schema enforcement
- No additionalProperties by default

---

## 3. Pull Request Guidelines

Each pull request should include:

- Clear problem statement
- Explanation of structural impact
- Measurable change description
- Telemetry implications
- Budget implications

If adding model invocation, justify necessity.

---

## 4. Architectural Review Checklist

Before approval, confirm:

| Question | Required |
|----------|----------|
| Does this introduce hidden inference? | Must be No |
| Is budget enforcement preserved? | Must be Yes |
| Is schema validation enforced? | Must be Yes |
| Is deterministic-first principle preserved? | Must be Yes |
| Is compute neutrality maintained? | Must be Yes |

If any answer fails, revision is required.

---

## 5. Experimental Contributions

For research-oriented contributions:

- Include falsifiable hypothesis
- Define measurable variables
- Provide before-and-after metrics
- Include break-even analysis where applicable

KORA favors empiricism over assumption.

---

## 6. Long-Term Direction

Contributors should align with:

- Decomposition-native evolution
- Heterogeneous routing
- CPU-first viability
- Budget-aware reasoning

Short-term convenience must not undermine long-term architecture.

---

## 7. Tone and Documentation

Documentation must:

- Avoid hype language
- Avoid vendor bias
- Use ASCII punctuation
- Include rendered tables when relevant
- Include Mermaid diagrams where structural clarity improves understanding
- Use bold and italic on
