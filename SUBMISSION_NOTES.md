# Submission Notes

Use this as a concise guide for the assessment walkthrough and technical discussion. Keep the explanation aligned with the implementation: the current planner is deterministic, and all external actions are simulated.

## 90-second overview

Rayda Fleet Copilot turns a stream of device telemetry into tenant-scoped fleet investigations and reviewable operational proposals. It ingests NDJSON snapshots, validates required identity and timestamp fields, separates missing telemetry from measured failures, and supports current-state queries plus historical trend detection.

The copilot uses an explicit, bounded planner/tool loop. Each tool receives the company scope supplied by the application, returns structured observations with source evidence, and contributes to an execution trace. A separate attention register combines current compliance and storage issues with historical indicators using transparent, explainable heuristics.

For operational follow-through, the prototype supports four action types. A proposal is tied to tenant, device, timestamp and the source telemetry snapshot. A separate approver must approve it; proposal contents are integrity-checked before a simulated execution is recorded. Events are written to a tenant-scoped SQLite audit log. No external system is contacted.

## Architecture walkthrough

1. **Ingestion — `data.py`:** strict NDJSON parsing into snapshot records; tenant-scoped latest-state queries and telemetry quality reporting.
2. **Analysis — `insights.py`:** historical battery, memory, storage and compliance-drift indicators with supporting observations and evidence-quality labels.
3. **Prioritisation — `risk.py`:** explainable device attention score, issue breakdown and telemetry coverage. This is a prototype triage heuristic, not a calibrated probability or company policy.
4. **Agent loop — `agent.py`:** deterministic intent planner, allowlisted tool execution, application-supplied tenant scope, bounded steps and trace.
5. **Actions — `actions.py`:** evidence-gated proposals, separate approval, integrity digest, simulated execution and audit events.
6. **Evaluation — `evals.py` and `tests/`:** dataset-grounded regression counts, tenant-scope checks and unit tests.
7. **Interface — `app.py`:** Streamlit overview, device inspection, copilot, insights and action approval center.

## Likely technical questions

### Why is the planner deterministic instead of using an LLM?

The assessment needs reproducible, inspectable behaviour over a fixed dataset. The deterministic planner makes tool selection and execution bounds explicit and avoids introducing model variability or API dependencies into the core evaluation. The tool contracts are separated from the planner, so a model-backed planner could be added later without allowing it to choose the tenant or bypass tool authorization.

### Is this a production-ready agent?

No. It is an assessment prototype demonstrating the data, tool, evidence, approval and evaluation boundaries. Production would require verified user authentication and RBAC, managed persistence, monitoring, hardened service boundaries, operational integrations, and broader security and evaluation work.

### How is tenant isolation enforced?

The application supplies the company scope to the agent and every tool; the planner does not generate or override it. In this assessment demo, the Streamlit tenant selector is the source of that scope and is only a local demo input, not production authentication. Data queries filter by the selected company, action proposals validate evidence company IDs, and proposal/audit reads are scoped. In production, the company scope must come from verified user authentication and authorization.

### What happens when telemetry is missing or invalid?

Missing values are treated as unknown, not as failures. Invalid numeric readings are excluded from calculations. Coverage is reported separately so an absence of evidence is not mistaken for a healthy device.

### How should the attention score be interpreted?

As a transparent human-triage aid. Its components and caps are visible in the UI and README. It is not statistically calibrated, does not establish causation, and is not a Rayda-approved policy.

### What prevents an action from being executed immediately?

The proposal remains pending until a different approver approves it. The current prototype checks the approver role supplied by the demo UI, rejects requester self-approval, verifies the proposal integrity digest, and records only a simulated execution. The typed demo role is not verified RBAC.

### Are the action integrations real?

No. The four action types are simulated locally. The prototype does not create real purchase orders, tickets, replacement requests or employee notifications.

### What do the evaluations prove?

They verify selected intent-to-tool mappings, exact expected counts for the supplied dataset, and tenant IDs in nested tool observations. They are focused regression checks, not comprehensive proof of production security or model quality.

## Claims to avoid

- Do not call the current planner an LLM-powered or autonomous reasoning model.
- Do not describe the attention score as a probability or approved risk policy.
- Do not claim production authentication or verified RBAC in the Streamlit demo.
- Do not claim that real tickets, purchase orders, messages or replacements are created.
- Do not claim the full test suite or dashboard has passed a fresh-clone runtime check until it has been run locally with the supplied dataset.
