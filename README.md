# Rayda Agentic AI Fleet Copilot

A tenant-scoped fleet intelligence prototype built against the supplied NDJSON telemetry dataset.

## Implemented
- Strict NDJSON ingestion, dataset profiling and telemetry quality/coverage reporting
- Latest-snapshot disk and compliance queries
- Historical battery, RAM, storage and compliance-drift insights
- Explainable tenant-scoped device attention register combining latest-state issues, historical indicators and telemetry coverage
- Explicit bounded agent planning/tool loop with execution trace
- Tenant scope passed by trusted application context to every tool
- Evidence-gated action proposals, explicit approval, simulated execution and audit log
- Deterministic regression evaluation cases
- Optional Streamlit demonstration UI

## Important implementation boundary
The agent supports both a deterministic planner and an optional OpenAI-backed planner. The LLM selects from a fixed allowlist of read-only tools; Python validates the plan, enforces the configured step bound, supplies the selected tenant context to every tool, and executes the tools. The model never chooses or overrides tenant scope and cannot approve or execute actions. If the model call fails or returns an invalid plan, the deterministic planner is used. Action execution remains simulated; no real procurement, ticketing or messaging integrations are present.

## Dataset
Place the assessment file at `data/device-telemetry-dataset.ndjson`. The original dataset is 750 snapshots across 25 devices, 3 companies and 14 employees, with 30 snapshots per device. Missing telemetry is unknown, not failure.

**Repository note:** the source code and tests are committed. The 1.38 MB assessment dataset is not yet present in this GitHub repository and must be added at the path above before running the tests or demo.

## Setup
Python 3.11+ recommended.

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS/Linux
source .venv/bin/activate
pip install -e ".[test,demo,llm]"
```

## Run
```bash
fleet-copilot --data data/device-telemetry-dataset.ndjson profile
fleet-copilot --data data/device-telemetry-dataset.ndjson quality
fleet-copilot --data data/device-telemetry-dataset.ndjson quality --company acme-001
fleet-copilot --data data/device-telemetry-dataset.ndjson attention --company acme-001
fleet-copilot --data data/device-telemetry-dataset.ndjson ask --company acme-001 "Which devices have low disk space?"
fleet-copilot --data data/device-telemetry-dataset.ndjson eval
streamlit run app.py
```

Alternatively, run commands with `python -m fleet_copilot.cli` from the project root after installing editable.

## Optional LLM planner

Install the optional dependency with `pip install -e ".[llm,demo]" `. Set the API key in your local shell; never commit it or put it in source code.

Windows PowerShell:

```powershell
$env:OPENAI_API_KEY="your-key"
$env:OPENAI_MODEL="gpt-4o-mini"
streamlit run app.py
```

The Fleet Copilot tab has a **Use OpenAI LLM planner** toggle. The default model is `gpt-4o-mini`; `OPENAI_MODEL` can override it. The LLM returns structured tool names only. The application validates every name against the allowlist, deduplicates and caps the plan, and passes the selected tenant from application context to deterministic Python tools. Model output is never treated as evidence. If the API is unavailable or its response is invalid, the deterministic planner runs instead. The UI reports which planner mode was used.

The model is used for planning/tool selection, not for generating unsupported fleet facts. Tool observations remain the source of truth, and all action operations remain local simulations requiring the existing approval workflow.

## Architecture
- `data.py`: strict parsing, tenant-scoped deterministic queries and telemetry quality reporting
- `insights.py`: historical trend detection and evidence
- `risk.py`: deterministic device attention ranking and per-device assessment coverage
- `cli.py`: reproducible profile, quality, attention, ask and evaluation commands
- `actions.py`: proposal/approval/audit store; simulated side effects only
- `agent.py`: bounded plan → tool call → observation loop, deterministic fallback and tenant-scoped execution
- `llm_planner.py`: optional structured OpenAI tool planner with a strict allowlist
- `evals.py`: small deterministic regression checks
- `app.py`: optional Streamlit demonstration

## Device attention ranking
The optional dashboard queue uses an explicitly illustrative score: latest compliance failures contribute 30/20/10 points for high/medium/low severity (capped at 60); each latest low-disk volume contributes 20 (capped at 40); historical battery decline, persistent RAM pressure, persistent low storage and compliance drift contribute 10/15/10/10 points per finding. The total is capped at 100. Bands are high attention (50+), elevated (25–49), review (1–24), and no detected issue (0). A zero-score device with less than 60% telemetry assessment coverage is labelled assessment limited. Current and historical evidence can both contribute when they describe distinct time horizons; the score is a triage aid, not a calibrated probability, causal diagnosis or Rayda-approved policy. Missing/invalid telemetry never adds score.

## Grounding
The agent calls deterministic tools. Tool results include company IDs, device IDs, timestamps and source measurements. The current prototype returns raw evidence records for inspection; production answers should render concise evidence citations linked to source snapshot IDs.

## Guardrails
- Company scope is an explicit trusted argument to every tool.
- The demo UI's tenant selector and typed approver ID/role are local testing inputs, not production authentication or verified role-based access control.
- Actions require evidence with matching tenant and device provenance, plus explicit approval.
- Execution is simulated and audited locally.
- No tool accepts a company ID generated by the model.

## Evaluation
Run `fleet-copilot --data data/device-telemetry-dataset.ndjson eval`. The four baseline cases check planner intent, dataset-grounded result counts (2 low-disk findings for Acme, 6 latest compliance failures for Globex, 0 battery-decline findings for Initech, and 1 persistent-RAM finding for Acme), and tenant IDs throughout nested result evidence. These exact counts are regression baselines for the supplied dataset, not universal fleet expectations; review the evidence before updating them if the dataset changes. The suite remains a focused starter benchmark, not proof of production security or comprehensive model quality.

## Design trade-offs
- Deterministic Python tools and evaluation remain the source of truth; optional LLM planning improves natural-language tool selection.
- LLM planning is optional and bounded; deterministic planning remains the offline fallback.
- SQLite keeps the assessment self-contained; production would use authenticated service boundaries and a managed database.
- Thresholds in trend detection are configurable examples, not Rayda policy.

