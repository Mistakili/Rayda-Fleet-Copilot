"""Optional Streamlit demo UI. Run: streamlit run app.py"""
import os
import streamlit as st
from fleet_copilot.data import load_snapshots
from fleet_copilot.agent import FleetAgent
from fleet_copilot.actions import ActionStore, ActionError

st.set_page_config(page_title="Fleet Copilot",page_icon="🛰️",layout="wide")
st.title("🛰️ Fleet Copilot")
st.caption("Evidence-grounded fleet intelligence · Assessment dataset · Simulated actions only")
data_path=os.getenv("FLEET_DATA_PATH","data/device-telemetry-dataset.ndjson")
snapshots=load_snapshots(data_path)
companies=sorted({s.company_id for s in snapshots})
company=st.sidebar.selectbox("Authenticated demo tenant",companies)
st.sidebar.warning("Demo identity selector only. Production must derive tenant identity from verified authentication.")
agent=FleetAgent(snapshots)
question=st.text_input("Ask about fleet health, compliance or trends",placeholder="Which devices have low disk space?")
if st.button("Investigate",type="primary",disabled=not question.strip()):
    state=agent.invoke(question,company)
    st.markdown(state.answer)
    st.subheader("Agent execution trace")
    st.json({"plan":state.plan,"steps":state.steps})
    for obs in state.observations:
        with st.expander(f'{obs["tool"]} · {obs["count"]} result(s)'):
            st.json(obs["results"])
st.divider()
st.subheader("Action approval sandbox")
st.caption("Actions are simulated locally; no external systems are contacted.")
store=ActionStore("fleet_actions.sqlite")
with st.form("proposal"):
    action=st.selectbox("Action type",["open_remediation_ticket","create_upgrade_order","flag_device_for_replacement","notify_employee"])
    target=st.text_input("Target device or employee ID")
    reason=st.text_area("Reason / proposed action")
    evidence_ref=st.text_input("Evidence reference (device ID / snapshot timestamp)")
    submit=st.form_submit_button("Create proposal")
if submit:
    try:
        p=store.propose(authenticated_company_id=company,actor_id="demo-admin",action_type=action,
          payload={"target":target,"reason":reason},
          evidence=[{"device_id":target,"collected_at":evidence_ref,"note":"Demo-provided reference; production must resolve this against telemetry."}] if target.strip() and evidence_ref.strip() else [])
        st.success(f'Pending proposal: {p["proposal_id"]}')
        st.session_state["pending_proposal"]=p["proposal_id"]
    except ActionError as e: st.error(str(e))
proposal_id=st.session_state.get("pending_proposal")
if proposal_id and st.button("Approve & simulate execution"):
    try:
        result=store.approve_and_execute(proposal_id=proposal_id,authenticated_company_id=company,approver_id="demo-approver",approver_role="admin")
        st.success("Simulated execution recorded"); st.json(result)
    except ActionError as e: st.error(str(e))
with st.expander("Tenant audit log"):
    st.json(store.audit_events(company))
