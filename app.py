"""Streamlit interface for the Rayda Fleet Copilot assessment demo.

Run from the repository root with: streamlit run app.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from fleet_copilot.actions import ActionError, ActionStore
from fleet_copilot.agent import FleetAgent
from fleet_copilot.llm_agent import OpenAIFleetAgent
from fleet_copilot.data import (
    compliance_failures,
    dataset_profile,
    latest_by_device,
    load_snapshots,
    low_disk_devices,
)
from fleet_copilot.insights import all_insights
from fleet_copilot.risk import device_attention_register

st.set_page_config(
    page_title="Rayda | Fleet Copilot",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
  :root { color-scheme: dark; }
  html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
  .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    background: #0b1220; color: #e5edf8;
  }
  [data-testid="stHeader"] { background: rgba(11,18,32,.92); }
  [data-testid="stSidebar"] { background: #101b32; border-right: 1px solid #26364f; }
  [data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
  [data-testid="stSidebar"] label,
  [data-testid="stSidebar"] p,
  [data-testid="stSidebar"] span,
  [data-testid="stSidebar"] small { color: #dbe7f7 !important; }
  [data-testid="stSidebar"] [data-baseweb="select"] > div {
    background: #1b2940 !important; border-color: #526783 !important;
  }
  [data-testid="stSidebar"] [data-baseweb="select"] input,
  [data-testid="stSidebar"] [data-baseweb="select"] div,
  [data-testid="stSidebar"] [data-baseweb="select"] span {
    color: #f3f7fc !important; -webkit-text-fill-color: #f3f7fc !important;
  }
  [data-baseweb="popover"], [data-baseweb="menu"], [role="listbox"] {
    background: #17243a !important; color: #f3f7fc !important;
  }
  [role="option"], [role="listbox"] * { color: #f3f7fc !important; }
  [role="option"]:hover { background: #263a57 !important; }
  .brand { font-family: 'Space Grotesk',sans-serif; font-size: 1.35rem; font-weight: 700; color:#f3f7fc; }
  .eyebrow { color:#a9c7e7; font-size:.72rem; letter-spacing:.13em; font-weight:700; text-transform:uppercase; }
  .hero { background:linear-gradient(120deg,#132747,#244d70); color:white; padding:1.35rem 1.6rem; border:1px solid #355b80; border-radius:16px; margin:.25rem 0 1.2rem; }
  .hero h1 { color:white; font-family:'Space Grotesk',sans-serif; font-size:1.8rem; margin:.2rem 0; }
  .hero p { color:#d8e5f5; margin:.2rem 0 0; }
  h1, h2, h3, h4, h5, h6, p, li, label, [data-testid="stMarkdownContainer"] { color:#e5edf8; }
  [data-testid="stCaptionContainer"], .stCaption, small { color:#a8b8cc !important; }
  div[data-testid="stMetric"] {
    background:#142238; border:1px solid #2b405d; padding:14px 16px;
    border-radius:13px; box-shadow:0 2px 12px #00000020;
  }
  div[data-testid="stMetricLabel"] { color:#a8b8cc !important; }
  div[data-testid="stMetricValue"] { color:#f3f7fc !important; font-family:'Space Grotesk',sans-serif; }
  .note { background:#302719; border:1px solid #80632e; color:#ffe3a3; padding:.8rem 1rem; border-radius:10px; font-size:.86rem; }
  .stTabs [data-baseweb="tab-list"] { gap:1.1rem; border-bottom:1px solid #2b405d; }
  .stTabs [data-baseweb="tab"] { color:#b9c8da; font-weight:600; }
  .stTabs [aria-selected="true"] { color:#7db8ff !important; }
  [data-testid="stDataFrame"], [data-testid="stTable"] {
    background:#111d30; border:1px solid #2b405d; border-radius:10px;
  }
  [data-testid="stExpander"] { background:#111d30; border:1px solid #2b405d; border-radius:10px; }
  [data-testid="stExpander"] summary, [data-testid="stExpander"] summary p { color:#e5edf8 !important; }
  [data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea,
  [data-testid="stNumberInput"] input, [data-testid="stDateInput"] input {
    background:#17243a !important; color:#f3f7fc !important;
    border-color:#526783 !important; -webkit-text-fill-color:#f3f7fc !important;
  }
  [data-testid="stTextInput"] input::placeholder, [data-testid="stTextArea"] textarea::placeholder {
    color:#9aabc1 !important; -webkit-text-fill-color:#9aabc1 !important;
  }
  [data-baseweb="select"] > div { background:#17243a !important; border-color:#526783 !important; }
  [data-baseweb="select"] input, [data-baseweb="select"] span { color:#f3f7fc !important; -webkit-text-fill-color:#f3f7fc !important; }
  [data-testid="stButton"] button, [data-testid="stFormSubmitButton"] button {
    background:#245b91; color:#fff !important; border:1px solid #4b88c4;
  }
  [data-testid="stButton"] button:hover, [data-testid="stFormSubmitButton"] button:hover {
    background:#2e70ad; border-color:#79b7ef; color:#fff !important;
  }
  [data-testid="stAlert"], [data-baseweb="notification"] {
    background:#17243a !important; color:#e5edf8 !important; border:1px solid #405875 !important;
  }
  [data-testid="stAlert"] p, [data-testid="stAlert"] span,
  [data-baseweb="notification"] p, [data-baseweb="notification"] span { color:#e5edf8 !important; }
  [data-testid="stAlert"] svg, [data-baseweb="notification"] svg { fill:currentColor; }
  .dataset-status {
    display:flex; align-items:center; gap:.65rem; background:#172b3b;
    border:1px solid #2d6170; color:#c7f2e8; padding:.8rem .9rem;
    border-radius:10px; font-size:.88rem; font-weight:600;
  }
  .dataset-status .status-dot {
    width:.55rem; height:.55rem; flex:0 0 .55rem; border-radius:50%;
    background:#45c6a5; box-shadow:0 0 0 3px #45c6a522;
  }
  [data-testid="stDataFrame"] *, [data-testid="stTable"] * { color-scheme:dark; }
  [data-testid="stDataFrame"] iframe { background:#111d30 !important; }
  [data-testid="stCode"], pre, code {
    background:#101c2e !important; color:#d8e8fa !important; border-color:#2b405d !important;
  }
  [data-testid="stSelectbox"] [data-baseweb="select"] *,
  [data-testid="stMultiSelect"] [data-baseweb="select"] * { color:#f3f7fc !important; }
  hr { border-color:#2b405d !important; }
  [data-testid="stSidebar"] [data-testid="stAlert"] { background:#17243a; }
  [data-testid="stSidebar"] [data-testid="stAlert"] p,
  [data-testid="stSidebar"] [data-testid="stAlert"] span { color:#e5edf8 !important; }
</style>
""", unsafe_allow_html=True)

DATA_PATH = Path(os.getenv("FLEET_DATA_PATH", "data/device-telemetry-dataset.ndjson"))
DB_PATH = os.getenv("FLEET_ACTION_DB", "fleet_actions.sqlite")

@st.cache_data(show_spinner="Loading fleet telemetry…")
def get_data(path: str, modified: float):
    return load_snapshots(path)

@st.cache_resource
def get_action_store(path: str):
    return ActionStore(path)

if not DATA_PATH.exists():
    st.error(f"Telemetry dataset not found at `{DATA_PATH}`.")
    st.info("Place the assessment NDJSON file at data/device-telemetry-dataset.ndjson, or set FLEET_DATA_PATH.")
    st.stop()

try:
    snapshots = get_data(str(DATA_PATH), DATA_PATH.stat().st_mtime)
except Exception as exc:
    st.error(f"Could not load telemetry: {exc}")
    st.stop()

profile = dataset_profile(snapshots)
companies = sorted({item.company_id for item in snapshots})

with st.sidebar:
    st.markdown('<div class="brand" style="color:white">◈ RAYDA</div>', unsafe_allow_html=True)
    st.caption("FLEET INTELLIGENCE")
    st.divider()
    company = st.selectbox("DEMO TENANT", companies, help="Local assessment selector. Production tenant identity must come from verified authentication.")
    st.caption("Workspace")
    st.markdown("Fleet overview  ·  Copilot  ·  Insights  ·  Actions")
    st.divider()
    st.caption("DATASET STATUS")
    st.markdown(f'<div class="dataset-status"><span class="status-dot"></span>{profile["snapshots"]:,} telemetry records loaded</div>', unsafe_allow_html=True)
    st.caption(f"{profile['devices']} devices · {profile['companies']} companies")
    st.markdown('<div class="note">Assessment demo only. Tenant selector is not production authentication. All actions are simulated.</div>', unsafe_allow_html=True)

tenant_latest = latest_by_device(snapshots, company)
tenant_disk = low_disk_devices(snapshots, company)
tenant_compliance = compliance_failures(snapshots, company)
tenant_insights = all_insights(snapshots, company)
tenant_attention = device_attention_register(snapshots, company)
battery_flags = [x for x in tenant_insights if x["type"] == "battery_capacity_decline"]
ram_flags = [x for x in tenant_insights if x["type"] == "persistent_ram_pressure"]
storage_flags = [x for x in tenant_insights if x["type"] == "persistent_low_storage"]
drift_flags = [x for x in tenant_insights if x["type"] == "compliance_drift"]

st.markdown('<div class="hero"><div class="eyebrow" style="color:#a9c7e7">FLEET OPERATIONS CENTER</div><h1>Know your fleet. Act with evidence.</h1><p>Monitor device health, investigate patterns and review proposed actions in one workspace.</p></div>', unsafe_allow_html=True)
st.markdown(f"**Tenant:** `{company}` &nbsp; · &nbsp; **Latest device snapshots:** {len(tenant_latest)} &nbsp; · &nbsp; **Observation window:** {profile['start'][:10]} to {profile['end'][:10]}")

m1,m2,m3,m4,m5 = st.columns(5)
m1.metric("Devices", len(tenant_latest))
m2.metric("Low disk alerts", len(tenant_disk))
m3.metric("Compliance failures", len(tenant_compliance))
m4.metric("Historical insights", len(tenant_insights))
m5.metric("Battery decline flags", len(battery_flags))

overview, devices, copilot, insights, actions = st.tabs(["Overview", "Devices", "Fleet Copilot", "Insights", "Action center"])

with overview:
    left,right=st.columns([1.35,1])
    with left:
        st.subheader("Fleet health snapshot")
        rows=[]
        for item in tenant_latest:
            failed=sum(1 for check in item.compliance_results if check.get("status")=="fail")
            disk_values=[]
            for volume in item.disk_volumes:
                size,available=volume.get("size_bytes"),volume.get("available_bytes")
                if isinstance(size,(int,float)) and size>0 and isinstance(available,(int,float)):
                    disk_values.append(round(available/size*100,1))
            rows.append({"Device":item.device_id,"Employee":item.employee_id,
                         "Compliance failures":failed,
                         "Lowest free disk %":min(disk_values) if disk_values else None,
                         "Last seen":item.collected_at})
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    with right:
        st.subheader("Attention required")
        st.metric("Persistent RAM pressure",len(ram_flags))
        st.metric("Persistent low storage",len(storage_flags))
        st.metric("Compliance drift events",len(drift_flags))
        st.metric("Battery capacity decline",len(battery_flags))
        st.caption("Historical indicators use available snapshots only. Missing telemetry is not treated as a failure.")
    st.subheader("Device attention queue")
    st.caption("Transparent prototype triage score from current compliance failures, latest low-disk readings and historical indicators. Not Rayda-approved policy. Missing or invalid telemetry affects coverage only; it never adds score.")
    attention_rows = [{"Device": x["device_id"], "Employee": x["employee_id"], "Attention band": x["attention_band"].replace("_", " ").title(), "Heuristic score": x["attention_score"], "Compliance failures": x["current_compliance_failures"], "Low-disk volumes": x["current_low_disk_volumes"], "Historical indicators": x["historical_indicator_count"], "Assessment coverage %": x["assessment_coverage"]["coverage_pct"]} for x in tenant_attention]
    st.dataframe(pd.DataFrame(attention_rows), use_container_width=True, hide_index=True)
    with st.expander("How attention scoring works"):
        st.markdown("- Latest high/medium/low compliance failures: 30/20/10 points each, capped at 60.")
        st.markdown("- Each latest low-disk volume: 20 points, capped at 40.")
        st.markdown("- Historical battery decline, persistent RAM pressure, persistent low storage and compliance drift: 10/15/10/10 points per finding.")
        st.markdown("- Total capped at 100. Bands: high attention (50+), elevated (25–49), review (1–24), no detected issue (0).")
        st.markdown("- A zero-score device with under 60% assessment coverage is labelled assessment limited, not healthy.")
        st.caption("Heuristics are not calibrated probabilities, causal diagnoses or production policy.")
    st.subheader("Compliance checks")
    check_counts={}
    for item in tenant_latest:
        for check in item.compliance_results:
            key=str(check.get("check_id","unknown"))
            state=str(check.get("status","unknown"))
            check_counts.setdefault(key,{"Pass":0,"Fail":0,"Unknown":0})
            check_counts[key][{"pass":"Pass","fail":"Fail"}.get(state,"Unknown")]+=1
    if check_counts:
        st.bar_chart(pd.DataFrame(check_counts).T)
    else:
        st.info("No compliance check data is available for this tenant.")

with devices:
    st.subheader("Device inventory")
    search=st.text_input("Search device or employee",placeholder="Enter an ID")
    filtered=[item for item in tenant_latest if search.lower() in (item.device_id+" "+item.employee_id).lower()]
    st.dataframe(pd.DataFrame([{
        "Device ID":x.device_id,"Employee ID":x.employee_id,"Last reported":x.collected_at,
        "Battery condition":(x.battery or {}).get("condition","Not reported"),
        "Compliance failures":sum(1 for c in x.compliance_results if c.get("status")=="fail"),
        "Volumes reported":len(x.disk_volumes)
    } for x in filtered]),use_container_width=True,hide_index=True)
    selected_device=st.selectbox("Inspect device", [x.device_id for x in filtered] or [""], disabled=not filtered)
    if selected_device:
        item=next(x for x in filtered if x.device_id==selected_device)
        a,b,c=st.columns(3)
        a.metric("Employee",item.employee_id)
        b.metric("Compliance failures",sum(1 for check in item.compliance_results if check.get("status")=="fail"))
        c.metric("Disk volumes",len(item.disk_volumes))
        with st.expander("Raw latest telemetry evidence"):
            st.json(item.raw)

with copilot:
    st.subheader("Ask the Fleet Copilot")
    api_key_available=bool(os.getenv("OPENAI_API_KEY"))
    engine=st.radio(
        "Reasoning engine",
        ["OpenAI hybrid","Deterministic"],
        index=0 if api_key_available else 1,
        horizontal=True,
        disabled=not api_key_available,
        help="OpenAI interprets the request and selects read-only deterministic tools. Actions remain in the separate approval center.",
    )
    if not api_key_available:
        st.caption("OpenAI mode is disabled until OPENAI_API_KEY is set. Deterministic mode remains available.")
    else:
        st.caption("OpenAI handles intent, tool selection and evidence synthesis. Python tools retain tenant scope and perform all telemetry calculations.")
    prompt=st.text_area("Your question",placeholder="Which devices have low disk space? Are there persistent battery or RAM issues?",height=90)
    if st.button("Run investigation",type="primary",disabled=not prompt.strip(),key="run_copilot"):
        try:
            agent=OpenAIFleetAgent(snapshots) if engine=="OpenAI hybrid" else FleetAgent(snapshots)
            state=agent.invoke(prompt,company)
            st.session_state["last_agent_state"]={
                "company_id":company,
                "engine":engine,
                "answer":state.answer,"plan":state.plan,"steps":state.steps,"observations":state.observations
            }
        except Exception as exc:
            st.error(f"Investigation failed: {exc}")
    result=st.session_state.get("last_agent_state")
    if result and result.get("company_id") == company:
        st.caption(f"Engine: {result.get('engine','Deterministic')}")
        st.markdown("#### Investigation summary")
        st.info(result["answer"])
        st.markdown("#### Evidence returned")
        for observation in result["observations"]:
            with st.expander(f"{observation['tool']} · {observation['count']} finding(s)",expanded=True):
                if observation.get("results"):
                    st.dataframe(pd.json_normalize(observation["results"]),use_container_width=True,hide_index=True)
                else:
                    st.caption(observation.get("error","No matching records found."))
        with st.expander("Agent plan and execution trace"):
            st.write("Selected tools:",result["plan"])
            st.json(result["steps"])
    else:
        st.info("Start with a question about disk space, compliance, battery health, RAM, storage or historical trends.")

with insights:
    st.subheader("Historical fleet insights")
    st.caption("These are rule-based indicators derived from historical telemetry, not diagnoses or company policy.")
    if not tenant_insights:
        st.success("No historical indicators crossed the current prototype thresholds.")
    for item in tenant_insights:
        title=item["type"].replace("_"," ").title()
        with st.expander(f"{title} · {item.get('device_id','fleet-level')} · {item.get('severity','review')}"):
            st.write(item["finding"])
            st.caption(item.get("explanation",""))
            evidence=item.get("evidence") or item.get("transitions") or []
            if evidence: st.dataframe(pd.json_normalize(evidence),use_container_width=True,hide_index=True)
            if item.get("trend"): st.json(item["trend"])

with actions:
    st.subheader("Action approval center")
    st.markdown('<div class="note">Every action below is a local simulation. No purchase order, support ticket, employee message or device replacement is actually created.</div>',unsafe_allow_html=True)
    store=get_action_store(DB_PATH)
    st.markdown("#### Propose an action")
    device_by_id={item.device_id:item for item in tenant_latest}
    if not device_by_id:
        st.warning("No devices available in this tenant.")
    else:
        with st.form("action_proposal"):
            action_type=st.selectbox("Action type",["open_remediation_ticket","create_upgrade_order","flag_device_for_replacement","notify_employee"])
            target_id=st.selectbox("Evidence device",sorted(device_by_id))
            target_item=device_by_id[target_id]
            reason=st.text_area("Why is this action being proposed?",placeholder="Describe the observed issue and recommended next step.")
            submitted=st.form_submit_button("Create pending proposal",type="primary")
        if submitted:
            if not reason.strip():
                st.error("Add a reason before creating the proposal.")
            else:
                evidence=[{"company_id":company,"device_id":target_item.device_id,"collected_at":target_item.collected_at,
                           "employee_id":target_item.employee_id,"source":"latest_dataset_snapshot",
                           "snapshot":target_item.raw}]
                payload={"target_device_id":target_item.device_id,"target_employee_id":target_item.employee_id,
                         "reason":reason.strip(),"source_snapshot_at":target_item.collected_at}
                try:
                    proposal=store.propose(authenticated_company_id=company,actor_id="demo-requester",
                        action_type=action_type,payload=payload,evidence=evidence)
                    st.session_state["last_proposal_id"]=proposal["proposal_id"]
                    st.success(f"Proposal created: {proposal['proposal_id']}")
                except ActionError as exc:
                    st.error(str(exc))
    st.markdown("#### Pending proposals")
    pending=store.db.execute("SELECT proposal_id,action_type,created_by,created_at,payload_json FROM proposals WHERE company_id=? AND status='pending' ORDER BY created_at DESC",(company,)).fetchall()
    if not pending:
        st.caption("No pending proposals for this tenant.")
    for row in pending:
        payload=json.loads(row["payload_json"])
        with st.container(border=True):
            st.write(f"**{row['action_type'].replace('_',' ').title()}** · {payload.get('target_device_id','')}")
            st.caption(f"Created {row['created_at']} by {row['created_by']}")
            st.write(payload.get("reason",""))
            proposal_record=store.get_proposal(row["proposal_id"],company)
            with st.expander("Review attached source evidence"):
                st.json(proposal_record["evidence"])
            approver=st.text_input("Approver ID",value="demo-approver",key=f"approver_{row['proposal_id']}")
            role=st.selectbox("Approver role",["admin","fleet_manager","employee"],key=f"role_{row['proposal_id']}")
            if st.button("Approve & simulate",key=f"approve_{row['proposal_id']}"):
                try:
                    result=store.approve_and_execute(proposal_id=row["proposal_id"],
                        authenticated_company_id=company,approver_id=approver,approver_role=role)
                    st.success("Simulated action recorded.")
                    st.json(result)
                    st.rerun()
                except ActionError as exc:
                    st.error(str(exc))
    st.markdown("#### Tenant audit trail")
    audit=store.audit_events(company)
    if audit:
        st.dataframe(pd.json_normalize(audit),use_container_width=True,hide_index=True)
    else:
        st.caption("No audit events recorded yet.")

st.divider()
st.caption("Rayda Fleet Copilot · Assessment prototype · Deterministic agent · Simulated action execution")
