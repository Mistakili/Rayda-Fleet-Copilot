import pytest
from fleet_copilot.actions import ActionStore, ActionError

EVIDENCE = [{"company_id": "acme", "device_id": "dev-1", "collected_at": "2026-06-12T10:00:00Z", "free_pct": 4.2}]


def make_proposal(store, **overrides):
    values = dict(authenticated_company_id="acme", actor_id="requester-1",
                  action_type="open_remediation_ticket",
                  payload={"device_id": "dev-1"}, evidence=EVIDENCE)
    values.update(overrides)
    return store.propose(**values)


def approve(store, proposal, **overrides):
    values = dict(proposal_id=proposal["proposal_id"],
                  authenticated_company_id="acme",
                  approver_id="admin-2", approver_role="admin")
    values.update(overrides)
    return store.approve_and_execute(**values)


def test_action_requires_provenance_and_explicit_approval():
    store = ActionStore()
    with pytest.raises(ActionError, match="without evidence"):
        make_proposal(store, evidence=[])
    with pytest.raises(ActionError, match="provenance"):
        make_proposal(store, evidence=[{"device_id": "dev-1", "collected_at": "2026-06-12T10:00:00Z"}])
    with pytest.raises(ActionError, match="different company"):
        make_proposal(store, evidence=[{**EVIDENCE[0], "company_id": "globex"}])
    with pytest.raises(ActionError, match="does not match"):
        make_proposal(store, payload={"target_device_id": "dev-2"})
    proposal = make_proposal(store)
    assert proposal["status"] == "pending"
    result = approve(store, proposal)
    assert result["simulated"] is True
    assert store.get_proposal(proposal["proposal_id"], "acme")["status"] == "approved"
    assert [x["event"] for x in store.audit_events("acme")] == [
        "proposal_created", "proposal_approved_and_simulated"]


def test_cross_tenant_approval_is_denied_and_audited():
    store = ActionStore()
    proposal = make_proposal(store)
    with pytest.raises(ActionError, match="different company"):
        approve(store, proposal, authenticated_company_id="globex")
    assert store.get_proposal(proposal["proposal_id"], "acme")["status"] == "pending"
    assert store.audit_events("globex")[-1]["event"] == "cross_tenant_access_denied"


def test_cannot_execute_same_proposal_twice():
    store = ActionStore()
    proposal = make_proposal(store)
    approve(store, proposal)
    with pytest.raises(ActionError, match="not pending"):
        approve(store, proposal)


def test_only_authorised_roles_can_approve():
    store = ActionStore()
    proposal = make_proposal(store)
    with pytest.raises(ActionError, match="not authorised"):
        approve(store, proposal, approver_role="employee")
    assert store.get_proposal(proposal["proposal_id"], "acme")["status"] == "pending"


def test_requester_cannot_self_approve():
    store = ActionStore()
    proposal = make_proposal(store)
    with pytest.raises(ActionError, match="cannot approve"):
        approve(store, proposal, approver_id="requester-1")


def test_proposal_tampering_invalidates_approval():
    store = ActionStore()
    proposal = make_proposal(store)
    store.db.execute("UPDATE proposals SET payload_json=? WHERE proposal_id=?",
                     ('{"device_id":"different-device"}', proposal["proposal_id"]))
    with pytest.raises(ActionError, match="changed after creation"):
        approve(store, proposal)
    assert store.get_proposal(proposal["proposal_id"], "acme")["status"] == "pending"
    assert store.audit_events("acme")[-1]["event"] == "proposal_integrity_check_failed"

def test_proposal_evidence_is_preserved_and_tampering_invalidates_approval():
    store = ActionStore()
    source = {
        "company_id": "acme",
        "device_id": "dev-1",
        "collected_at": "2026-06-12T10:00:00Z",
        "source": "latest_dataset_snapshot",
        "snapshot": {
            "battery": {"full_charge_capacity": 42000},
            "disk_volumes": [{"volume_name": "C:", "size_bytes": 100, "available_bytes": 4}],
        },
    }
    proposal = make_proposal(store, evidence=[source])
    saved = store.get_proposal(proposal["proposal_id"], "acme")
    assert saved["evidence"] == [source]

    store.db.execute(
        "UPDATE proposals SET evidence_json=? WHERE proposal_id=?",
        ('[{"company_id":"acme","device_id":"dev-1","collected_at":"2026-06-12T10:00:00Z","snapshot":{"disk_volumes":[]}}]',
         proposal["proposal_id"]),
    )
    with pytest.raises(ActionError, match="changed after creation"):
        approve(store, proposal)
    assert store.get_proposal(proposal["proposal_id"], "acme")["status"] == "pending"
    assert store.audit_events("acme")[-1]["event"] == "proposal_integrity_check_failed"

