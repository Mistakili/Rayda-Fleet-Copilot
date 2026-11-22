"""Tenant-scoped action proposals with integrity-bound approval and audit history.

Operational execution is simulated locally. No external systems are contacted.
"""
from __future__ import annotations
import hashlib, json, sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ALLOWED_ACTIONS = {"create_upgrade_order", "open_remediation_ticket", "flag_device_for_replacement", "notify_employee"}
APPROVER_ROLES = {"admin", "fleet_manager"}

class ActionError(ValueError):
    pass

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _canonical_digest(*, proposal_id: str, company_id: str, action_type: str, payload_json: str, evidence_json: str) -> str:
    material = {"proposal_id": proposal_id, "company_id": company_id, "action_type": action_type,
                "payload": json.loads(payload_json), "evidence": json.loads(evidence_json)}
    canonical = json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

class ActionStore:
    def __init__(self, database: str | Path = ":memory:") -> None:
        self.db = sqlite3.connect(str(database), timeout=10, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.execute("""
        CREATE TABLE IF NOT EXISTS proposals (
            proposal_id TEXT PRIMARY KEY, company_id TEXT NOT NULL,
            action_type TEXT NOT NULL, payload_json TEXT NOT NULL,
            evidence_json TEXT NOT NULL, status TEXT NOT NULL,
            created_by TEXT NOT NULL, created_at TEXT NOT NULL,
            approved_by TEXT, approved_at TEXT, integrity_digest TEXT
        )""")
        columns = {row["name"] for row in self.db.execute("PRAGMA table_info(proposals)")}
        if "integrity_digest" not in columns:
            self.db.execute("ALTER TABLE proposals ADD COLUMN integrity_digest TEXT")
            rows = self.db.execute("SELECT * FROM proposals").fetchall()
            for row in rows:
                digest = _canonical_digest(proposal_id=row["proposal_id"], company_id=row["company_id"],
                    action_type=row["action_type"], payload_json=row["payload_json"], evidence_json=row["evidence_json"])
                self.db.execute("UPDATE proposals SET integrity_digest=? WHERE proposal_id=?", (digest, row["proposal_id"]))
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS executions (
            execution_id TEXT PRIMARY KEY, proposal_id TEXT NOT NULL UNIQUE,
            company_id TEXT NOT NULL, action_type TEXT NOT NULL,
            payload_json TEXT NOT NULL, simulated INTEGER NOT NULL,
            executed_by TEXT NOT NULL, executed_at TEXT NOT NULL,
            FOREIGN KEY(proposal_id) REFERENCES proposals(proposal_id)
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id TEXT NOT NULL, actor_id TEXT NOT NULL,
            event TEXT NOT NULL, resource_id TEXT NOT NULL,
            details_json TEXT NOT NULL, created_at TEXT NOT NULL
        );
        """)

    def propose(self, *, authenticated_company_id: str, actor_id: str, action_type: str,
                payload: dict[str, Any], evidence: list[dict[str, Any]]) -> dict[str, Any]:
        if action_type not in ALLOWED_ACTIONS:
            raise ActionError(f"Unsupported action type: {action_type}")
        if not authenticated_company_id or not actor_id:
            raise ActionError("Authenticated company and actor are required")
        if not isinstance(evidence, list) or not evidence:
            raise ActionError("Cannot propose a state-changing action without evidence")
        if not isinstance(payload, dict) or not payload:
            raise ActionError("Action payload must be a non-empty object")
        for item in evidence:
            if (not isinstance(item, dict) or not item.get("device_id")
                    or not item.get("collected_at") or not item.get("company_id")):
                raise ActionError("Evidence must include company_id, device_id and collected_at provenance")
            if item["company_id"] != authenticated_company_id:
                raise ActionError("Evidence belongs to a different company")
        target_device = payload.get("target_device_id") or payload.get("device_id")
        if target_device and any(item["device_id"] != target_device for item in evidence):
            raise ActionError("Evidence device does not match the action target")
        proposal_id, now = str(uuid.uuid4()), _now()
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        evidence_json = json.dumps(evidence, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        digest = _canonical_digest(proposal_id=proposal_id, company_id=authenticated_company_id,
            action_type=action_type, payload_json=payload_json, evidence_json=evidence_json)
        self.db.execute("""INSERT INTO proposals
            (proposal_id, company_id, action_type, payload_json, evidence_json, status, created_by, created_at,
             approved_by, approved_at, integrity_digest)
            VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, NULL, NULL, ?)""",
            (proposal_id, authenticated_company_id, action_type, payload_json, evidence_json, actor_id, now, digest))
        self._audit(authenticated_company_id, actor_id, "proposal_created", proposal_id,
            {"action_type": action_type, "evidence_count": len(evidence), "integrity_digest": digest})
        return self.get_proposal(proposal_id, authenticated_company_id)

    def approve_and_execute(self, *, proposal_id: str, authenticated_company_id: str,
                            approver_id: str, approver_role: str) -> dict[str, Any]:
        if not approver_id or not authenticated_company_id:
            raise ActionError("Authenticated company and approver are required")
        if approver_role not in APPROVER_ROLES:
            raise ActionError("Approver role is not authorised")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT * FROM proposals WHERE proposal_id=?", (proposal_id,)).fetchone()
            if row is None: raise ActionError("Proposal not found")
            if row["company_id"] != authenticated_company_id:
                self._audit(authenticated_company_id, approver_id, "cross_tenant_access_denied", proposal_id, {})
                self.db.commit()
                raise ActionError("Proposal belongs to a different company")
            if row["status"] != "pending": raise ActionError(f"Proposal is not pending (status={row['status']})")
            if row["created_by"] == approver_id: raise ActionError("Proposal creator cannot approve their own proposal")
            if not json.loads(row["evidence_json"]): raise ActionError("Proposal has no evidence; execution refused")
            actual_digest = _canonical_digest(proposal_id=row["proposal_id"], company_id=row["company_id"],
                action_type=row["action_type"], payload_json=row["payload_json"], evidence_json=row["evidence_json"])
            if not row["integrity_digest"] or actual_digest != row["integrity_digest"]:
                self._audit(authenticated_company_id, approver_id, "proposal_integrity_check_failed", proposal_id, {})
                self.db.commit()
                raise ActionError("Proposal changed after creation; approval refused")
            now = _now()
            updated = self.db.execute("""UPDATE proposals SET status='approved', approved_by=?, approved_at=?
                WHERE proposal_id=? AND status='pending'""", (approver_id, now, proposal_id))
            if updated.rowcount != 1: raise ActionError("Proposal is no longer pending")
            execution_id = str(uuid.uuid4())
            self.db.execute("INSERT INTO executions VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                (execution_id, proposal_id, authenticated_company_id, row["action_type"], row["payload_json"], approver_id, now))
            self._audit(authenticated_company_id, approver_id, "proposal_approved_and_simulated", proposal_id,
                {"execution_id": execution_id, "simulated": True, "approver_role": approver_role, "integrity_digest": actual_digest})
            self.db.commit()
            return {"execution_id": execution_id, "proposal_id": proposal_id, "company_id": authenticated_company_id,
                    "action_type": row["action_type"], "status": "simulated_execution", "simulated": True}
        except Exception:
            if self.db.in_transaction: self.db.rollback()
            raise

    def get_proposal(self, proposal_id: str, authenticated_company_id: str) -> dict[str, Any]:
        row = self.db.execute("SELECT * FROM proposals WHERE proposal_id=? AND company_id=?", (proposal_id, authenticated_company_id)).fetchone()
        if row is None: raise ActionError("Proposal not found")
        result = dict(row)
        result["payload"] = json.loads(result.pop("payload_json"))
        result["evidence"] = json.loads(result.pop("evidence_json"))
        return result

    def audit_events(self, authenticated_company_id: str) -> list[dict[str, Any]]:
        rows = self.db.execute("SELECT * FROM audit_log WHERE company_id=? ORDER BY audit_id", (authenticated_company_id,)).fetchall()
        result = []
        for row in rows:
            item = dict(row); item["details"] = json.loads(item.pop("details_json")); result.append(item)
        return result

    def _audit(self, company_id: str, actor_id: str, event: str, resource_id: str, details: dict[str, Any]) -> None:
        self.db.execute("""INSERT INTO audit_log (company_id, actor_id, event, resource_id, details_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (company_id, actor_id, event, resource_id, json.dumps(details), _now()))
