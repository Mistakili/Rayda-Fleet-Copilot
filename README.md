# Rayda Agentic AI Fleet Copilot

A tenant-scoped fleet intelligence prototype built against the supplied NDJSON telemetry dataset.

## Implemented
- Strict NDJSON ingestion, dataset profiling and telemetry quality/coverage reporting
- Latest-snapshot disk and compliance queries
- Historical battery, RAM, storage and compliance-drift insights
- Explainable tenant-scoped device attention register combining latest-state issues, historical indicators and telemetry coverage
- Hybrid OpenAI reasoning layer with bounded tool-calling loop and deterministic fallback
- Explicit tool contracts; model selects read-only tools while Python enforces tenant scope and performs telemetry analysis
- Tenant scope passed by trusted application context to every tool
- Evidence-gated action proposals, explicit approval, simulated execution and audit log
- Deterministic regression evaluation cases
- Optional Streamlit demonstration UI

## Important implementation boundary
The project supports two reasoning modes. OpenAI hybrid mode uses an LLM to interpret the request, select from six read-only deterministic tools, and synthesize an evidence-grounded answer. The existing deterministic planner remains available as a reproducible fallback without an API key. In both modes, trusted application context supplies the tenant; the model cannot select or override it. The model cannot create, approve or execute actions. The separate action center retains human approval and simulated execution; no real procurement, ticketing or messaging integrations are present.

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
pip install -e ".[test,demo,openai]"
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

## Architecture
- `data.py`: strict parsing, tenant-scoped deterministic queries and telemetry quality reporting
- `insights.py`: historical trend detection and evidence
- `risk.py`: deterministic device attention ranking and per-device assessment coverage
- `cli.py`: reproducible profile, quality, attention, ask and evaluation commands
- `actions.py`: proposal/approval/audit store; simulated side effects only
- `agent.py`: deterministic plan → tool call → observation loop with a hard step bound\n- `llm_agent.py`: OpenAI tool-calling loop; model-selected read-only tools, strict empty-argument schemas, trusted tenant scope and bounded model round-trips
- `evals.py`: small deterministic regression checks
- `app.py`: optional Streamlit demonstration

## Device attention ranking
The optional dashboard queue uses an explicitly illustrative score: latest compliance failures contribute 30/20/10 points for high/medium/low severity (capped at 60); each latest low-disk volume contributes 20 (capped at 40); historical battery decline, persistent RAM pressure, persistent low storage and compliance drift contribute 10/15/10/10 points per finding. The total is capped at 100. Bands are high attention (50+), elevated (25–49), review (1–24), and no detected issue (0). A zero-score device with less than 60% telemetry assessment coverage is labelled assessment limited. Current and historical evidence can both contribute when they describe distinct time horizons; the score is a triage aid, not a calibrated probability, causal diagnosis or Rayda-approved policy. Missing/invalid telemetry never adds score.

## Grounding
Both reasoning modes call the same deterministic Python tools. Tool results include company IDs, device IDs, timestamps and source measurements. OpenAI receives only the selected tool outputs and must synthesize from that evidence; the UI also exposes the raw records and tool trace for inspection. The model never computes telemetry metrics itself. The prototype returns raw evidence records; production answers should render concise evidence citations linked to source snapshot IDs.

## Guardrails
- Company scope is an explicit trusted argument to every tool.
- The demo UI's tenant selector and typed approver ID/role are local testing inputs, not production authentication or verified role-based access control.
- Actions require evidence with matching tenant and device provenance, plus explicit approval.
- Execution is simulated and audited locally.
- No tool accepts a company ID generated by the model; tool schemas expose no tenant argument.\n- The OpenAI agent allowlists six read-only tools, rejects unknown tools and non-empty arguments, and bounds both successful tool calls and model round-trips.\n- The model cannot call action-store methods. Recommendations are not executions; proposals still require the separate human approval workflow.\n- Keep `OPENAI_API_KEY` in the local environment. Do not commit `.env` files or API keys.

## Evaluation
Run `fleet-copilot eval`. The four baseline cases check planner intent, dataset-grounded result counts (2 low-disk findings for Acme, 6 latest compliance failures for Globex, 0 battery-decline findings for Initech, and 1 persistent-RAM finding for Acme), and tenant IDs throughout nested result evidence. These exact counts are regression baselines for the supplied dataset, not universal fleet expectations; review the evidence before updating them if the dataset changes. The suite remains a focused starter benchmark, not proof of production security or comprehensive model quality.

## Design trade-offs
- Deterministic core over opaque free-form model reasoning for reliable reproducibility.
- Rule-based planning is intentionally transparent; an LLM planner can be added after tool contracts and evaluation are stable.
- SQLite keeps the assessment self-contained; production would use authenticated service boundaries and a managed database.
- Thresholds in trend detection are configurable examples, not Rayda policy.
