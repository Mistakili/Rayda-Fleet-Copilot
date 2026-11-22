"""Deterministic historical fleet insights with source-snapshot evidence.

Thresholds are explicit defaults, not claims about Rayda's production policy.
Callers may override them when a tenant policy is available.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime
from math import isfinite
from statistics import mean
from typing import Any, Iterable
from .data import Snapshot

def _time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))

def _base(item: Snapshot) -> dict[str, Any]:
    return {"device_id": item.device_id, "company_id": item.company_id, "employee_id": item.employee_id, "collected_at": item.collected_at}

def _series(snapshots: Iterable[Snapshot], company_id: str) -> dict[str, list[Snapshot]]:
    grouped: dict[str, list[Snapshot]] = defaultdict(list)
    for item in snapshots:
        if item.company_id == company_id: grouped[item.device_id].append(item)
    for values in grouped.values(): values.sort(key=lambda x: _time(x.collected_at))
    return grouped

def _metric_trend(values: list[tuple[Snapshot, float]], metric: str) -> dict[str, Any]:
    first_item, first_value = values[0]; last_item, last_value = values[-1]
    return {"metric": metric, "start_value": round(first_value, 2), "end_value": round(last_value, 2),
        "change": round(last_value-first_value, 2), "observations": len(values),
        "start_evidence": {**_base(first_item), "value": round(first_value, 2)},
        "end_evidence": {**_base(last_item), "value": round(last_value, 2)}}

def battery_insights(snapshots: Iterable[Snapshot], company_id: str, capacity_drop_pct: float = 10.0) -> list[dict[str, Any]]:
    findings=[]
    for device_id, history in _series(snapshots, company_id).items():
        values=[(s,float(s.battery["full_charge_capacity"])) for s in history if s.battery and
            isinstance(s.battery.get("full_charge_capacity"),(int,float)) and
            isfinite(s.battery["full_charge_capacity"]) and s.battery["full_charge_capacity"]>0]
        if len(values)<2: continue
        first,last=values[0][1],values[-1][1]; decline=(first-last)/first*100
        if decline>=capacity_drop_pct:
            findings.append({"type":"battery_capacity_decline","severity":"review",
                "finding":f"Battery full-charge capacity declined by {decline:.1f}% over the observed period.",
                "explanation":"This is a historical capacity change, not by itself a confirmed end-of-life diagnosis.",
                "trend":_metric_trend(values,"full_charge_capacity"),
                "evidence":[{**_base(s),"full_charge_capacity":s.battery["full_charge_capacity"],
                    "condition":s.battery.get("condition"),"cycle_count":s.battery.get("cycle_count")} for s,_ in (values[0],values[-1])]})
    return findings

def memory_insights(snapshots: Iterable[Snapshot], company_id: str, high_utilization_pct: float = 85.0,
                    persistence_pct: float = 70.0) -> list[dict[str, Any]]:
    findings=[]
    for device_id,history in _series(snapshots,company_id).items():
        values=[]
        for s in history:
            mem=s.memory; total,used=mem.get("total_memory_bytes"),mem.get("used_memory_bytes")
            if (isinstance(total,(int,float)) and isfinite(total) and total>0
                    and isinstance(used,(int,float)) and isfinite(used) and 0<=used<=total):
                values.append((s,used/total*100))
        if len(values)<2: continue
        high=[(s,pct) for s,pct in values if pct>=high_utilization_pct]; rate=len(high)/len(values)*100
        if rate>=persistence_pct:
            findings.append({"type":"persistent_ram_pressure","severity":"review",
                "finding":f"RAM utilization was at least {high_utilization_pct:.0f}% in {len(high)}/{len(values)} valid snapshots ({rate:.1f}%).",
                "explanation":"Persistence is measured across available snapshots; this indicates sustained high utilization, not proven user-perceived slowness.",
                "device_id":device_id,"company_id":company_id,"observations":len(values),"high_observations":len(high),
                "average_utilization_pct":round(mean(p for _,p in values),2),
                "evidence":[{**_base(s),"ram_utilization_pct":round(p,2)} for s,p in high]})
    return findings

def storage_insights(snapshots: Iterable[Snapshot], company_id: str, low_free_pct: float = 15.0,
                     persistence_pct: float = 50.0) -> list[dict[str, Any]]:
    findings=[]
    for device_id,history in _series(snapshots,company_id).items():
        volumes: dict[str,list[tuple[Snapshot,float]]]=defaultdict(list)
        for s in history:
            for volume in s.disk_volumes:
                size,available=volume.get("size_bytes"),volume.get("available_bytes"); name=str(volume.get("volume_name","unknown"))
                if (isinstance(size,(int,float)) and isfinite(size) and size>0
                        and isinstance(available,(int,float)) and isfinite(available)
                        and 0<=available<=size):
                    volumes[name].append((s,available/size*100))
        for name,values in volumes.items():
            if len(values)<2: continue
            low=[(s,pct) for s,pct in values if pct<=low_free_pct]; rate=len(low)/len(values)*100 if values else 0
            if values and rate>=persistence_pct:
                findings.append({"type":"persistent_low_storage","severity":"review",
                    "finding":f"Volume {name} had {low_free_pct:.0f}% or less free space in {len(low)}/{len(values)} valid snapshots ({rate:.1f}%).",
                    "explanation":"The finding is based on repeated reported free-space measurements.",
                    "device_id":device_id,"company_id":company_id,"volume":name,"observations":len(values),"low_observations":len(low),
                    "evidence":[{**_base(s),"volume":name,"free_pct":round(p,2)} for s,p in low]})
    return findings

def compliance_drift_insights(snapshots: Iterable[Snapshot], company_id: str) -> list[dict[str, Any]]:
    grouped: dict[tuple[str,str],list[tuple[Snapshot,str,str|None]]]=defaultdict(list)
    for device_id,history in _series(snapshots,company_id).items():
        for s in history:
            for check in s.compliance_results:
                status=check.get("status")
                if status in {"pass","fail"}: grouped[(device_id,str(check.get("check_id")))].append((s,status,check.get("severity")))
    findings=[]
    for (device_id,check_id),values in grouped.items():
        values.sort(key=lambda x:_time(x[0].collected_at))
        transitions=[(values[i-1],values[i]) for i in range(1,len(values)) if values[i-1][1]!=values[i][1]]
        if not transitions: continue
        first,last=values[0],values[-1]; direction=f"{first[1]} to {last[1]}" if first[1]!=last[1] else "status changed during the period"
        findings.append({"type":"compliance_drift","severity":last[2] or "unknown",
            "finding":f"Compliance check {check_id} changed status ({direction}); {len(transitions)} transition(s) observed.",
            "explanation":"A status transition is reported from the recorded snapshots; the underlying cause is not present in this dataset.",
            "device_id":device_id,"company_id":company_id,"check_id":check_id,
            "transitions":[{"from":{**_base(a[0]),"status":a[1]},"to":{**_base(b[0]),"status":b[1]}} for a,b in transitions]})
    return findings

def _add_evidence_quality(finding: dict[str, Any]) -> dict[str, Any]:
    """Attach transparent evidence-volume metadata; not statistical certainty."""
    evidence = finding.get("evidence", [])
    transitions = finding.get("transitions", [])
    timestamps = [item["collected_at"] for item in evidence if item.get("collected_at")]
    for transition in transitions:
        for side in ("from", "to"):
            item = transition.get(side, {})
            if item.get("collected_at"):
                timestamps.append(item["collected_at"])
    observations = finding.get("observations")
    if observations is None and finding.get("trend"):
        observations = finding["trend"].get("observations")
    if observations is None:
        observations = len(set(timestamps))
    unique_timestamps = sorted(set(timestamps), key=_time)
    span_days = None
    if len(unique_timestamps) >= 2:
        span_days = round((_time(unique_timestamps[-1]) - _time(unique_timestamps[0])).total_seconds() / 86400, 1)
    if observations >= 10 and span_days is not None and span_days >= 7:
        level = "strong"
    elif observations >= 4:
        level = "moderate"
    else:
        level = "limited"
    enriched = dict(finding)
    enriched["evidence_quality"] = {
        "valid_observations": observations,
        "dated_evidence_points": len(unique_timestamps),
        "dated_evidence_span_days": span_days,
        "level": level,
        "method": "Heuristic evidence-volume bands; not a probability, causal diagnosis, or Rayda policy.",
    }
    return enriched


def all_insights(snapshots: Iterable[Snapshot], company_id: str) -> list[dict[str, Any]]:
    """Run all deterministic historical detectors and annotate evidence volume."""
    data = list(snapshots)
    findings = (battery_insights(data, company_id) + memory_insights(data, company_id) +
                storage_insights(data, company_id) + compliance_drift_insights(data, company_id))
    return [_add_evidence_quality(item) for item in findings]
