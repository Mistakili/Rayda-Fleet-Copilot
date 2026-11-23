# Assessment Demo Guide

This guide is a reproducible walkthrough for the Rayda Fleet Copilot assessment repository.

## 1. Prerequisites

- Python 3.11 or newer
- The supplied assessment file: `device-telemetry-dataset.ndjson`
- A terminal opened at the repository root

The dataset is intentionally not committed to this repository. Put the supplied file at:

```text
data/device-telemetry-dataset.ndjson
```

Alternatively, set `FLEET_DATA_PATH` to its location. The CLI accepts an explicit `--data` path.

## 2. Install

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[test,demo,openai]"
```

### macOS / Linux

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[test,demo]"
```

## 3. Verify the dataset and regression baselines

Run these from the repository root:

```bash
fleet-copilot --data data/device-telemetry-dataset.ndjson profile
fleet-copilot --data data/device-telemetry-dataset.ndjson quality
fleet-copilot --data data/device-telemetry-dataset.ndjson eval
pytest -q
```

The supplied dataset's documented profile is 750 snapshots, 25 devices, 3 companies and 14 employees, with 30 snapshots per device. The four regression baselines are:

| Case | Expected result |
|---|---:|
| Acme low-disk findings | 2 |
| Globex latest compliance failures | 6 |
| Initech battery-decline findings | 0 |
| Acme persistent-RAM findings | 1 |

The evaluation also checks tenant scope in returned observations. These counts are regression expectations for this supplied dataset, not universal fleet policy. If the dataset changes, inspect the evidence before changing a baseline.

## 4. Run the dashboard

```bash
streamlit run app.py
```

If the dataset is outside the default path, set the environment variable before starting Streamlit.

PowerShell:

```powershell
$env:FLEET_DATA_PATH = "C:\path\to\device-telemetry-dataset.ndjson"
streamlit run app.py
```

The sidebar tenant selector is a local demo control. It is not production authentication.

## 5. Configure and demonstrate OpenAI hybrid mode (optional)\n\nOpenAI API access is separate from a ChatGPT subscription. In PowerShell, set the key only in the current local terminal session:\n\n```powershell\n$env:OPENAI_API_KEY = "your-api-key"\n$env:OPENAI_MODEL = "gpt-4o-mini"  # optional\nstreamlit run app.py\n```\n\nThe Fleet Copilot tab then offers **OpenAI hybrid** and **Deterministic** reasoning modes. The OpenAI mode lets the model interpret the request, choose among six read-only tools, and summarize their returned evidence. Tenant scope is still supplied by the app; tools perform all telemetry calculations. If no API key is set, the deterministic mode remains usable.\n\n## 6. Suggested walkthrough

1. **Fleet overview:** select `acme-001` and review the device count, compliance indicators and attention queue.
2. **Grounded copilot query:** select OpenAI hybrid (if configured) and ask, "Which devices are at greatest operational risk, and what should we investigate first?" Inspect the model-selected tools, returned evidence, and synthesized answer. Repeat in Deterministic mode to show the reproducible fallback. The model may recommend a next step but cannot create or execute an action.
3. **Historical insights:** review battery, RAM, storage and compliance-drift findings. Distinguish historical observations from the latest device snapshot.
4. **Attention ranking:** open a high-attention device and explain which current and historical findings contributed to its score. The score is a transparent prototype triage heuristic, not a calibrated probability or Rayda-approved policy.
5. **Action proposal:** open the action approval center, choose a device and action, enter a reason, and create a pending proposal. Expand **Review attached source evidence** to inspect the exact source telemetry snapshot bound to that proposal.
6. **Approval boundary:** first try approver ID `demo-requester`; self-approval should be refused. Then use a different demo ID such as `demo-approver` with the `admin` or `fleet_manager` role to record a simulated execution.
7. **Audit trail:** show the proposal and approval events in the selected tenant's audit trail. Switch tenants and verify that the other tenant's audit view does not show those events.

The four action types are `create_upgrade_order`, `open_remediation_ticket`, `flag_device_for_replacement` and `notify_employee`. All execution is simulated locally. No external procurement, ticketing, messaging or device-management system is contacted.

## 7. Action-store reset between demos

The dashboard stores action proposals and audit events in `fleet_actions.sqlite` by default. Stop Streamlit before resetting the demo history.

PowerShell:

```powershell
Remove-Item .\fleet_actions.sqlite -ErrorAction SilentlyContinue
Remove-Item .\fleet_actions.sqlite-shm -ErrorAction SilentlyContinue
Remove-Item .\fleet_actions.sqlite-wal -ErrorAction SilentlyContinue
```

macOS / Linux:

```bash
rm -f fleet_actions.sqlite fleet_actions.sqlite-shm fleet_actions.sqlite-wal
```

If `FLEET_ACTION_DB` is set, reset that configured database instead.

## 8. Architecture and limitations to state clearly

- OpenAI hybrid mode is model-backed for intent interpretation, tool selection and answer synthesis. The deterministic mode remains available as fallback. Both use the same deterministic telemetry tools and bounded execution. The LLM is not the source of fleet facts.
- Company scope is passed from trusted application context into the tools. Tool schemas have no tenant argument; the model does not choose the tenant.\n- The OpenAI agent allows only six read-only tools, rejects unknown tool names and non-empty arguments, and enforces a hard bound on tool executions and model round-trips. It has no action-execution tool.
- Missing telemetry is unknown, not a failure. Invalid measurements are excluded from relevant calculations and coverage.
- The attention score is an illustrative heuristic for human triage, not a calibrated risk probability, causal diagnosis or Rayda policy.
- The UI's tenant selector and typed approver identity/role are demo inputs, not production authentication or verified RBAC.
- Approval is required before a simulated action is recorded. Each dashboard proposal attaches the exact source telemetry snapshot plus tenant/device/timestamp provenance; the evidence is bound into the proposal integrity digest and checked for mutation before approval.
- SQLite is used for a self-contained assessment prototype. A production deployment would need authenticated service boundaries, verified authorization, managed persistence, operational monitoring and real integrations.
- The four evaluation cases are a focused regression benchmark, not comprehensive proof of production security or model quality.

## 9. Final submission checklist

- [ ] Confirm the supplied NDJSON file is available at the configured path.
- [ ] Run the profile and telemetry quality commands.
- [ ] Run the four-case evaluation and full test suite.
- [ ] Launch Streamlit and complete the walkthrough.
- [ ] Verify self-approval is denied and a separate demo approver can record a simulation.
- [ ] Verify tenant-scoped audit history.
- [ ] Capture screenshots from the actual running dashboard.
- [ ] Ensure no secrets, local database files or private environment files are included in the submission.
