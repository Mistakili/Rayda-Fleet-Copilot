from __future__ import annotations
import argparse, json
from pathlib import Path
from .data import load_snapshots, dataset_profile
from .agent import FleetAgent
from .evals import run_evaluations

def main():
    parser=argparse.ArgumentParser(description="Rayda Fleet Copilot")
    parser.add_argument("--data",default="data/device-telemetry-dataset.ndjson")
    sub=parser.add_subparsers(dest="command",required=True)
    sub.add_parser("profile")
    ask=sub.add_parser("ask"); ask.add_argument("--company",required=True); ask.add_argument("question")
    sub.add_parser("eval")
    args=parser.parse_args()
    snapshots=load_snapshots(args.data)
    if args.command=="profile": print(json.dumps(dataset_profile(snapshots),indent=2,default=str))
    elif args.command=="ask":
        state=FleetAgent(snapshots).invoke(args.question,args.company)
        print(state.answer); print(json.dumps({"plan":state.plan,"observations":state.observations},indent=2,default=str))
    elif args.command=="eval":
        results=run_evaluations(args.data); print(json.dumps(results,indent=2))
        if not all(x["passed"] for x in results): raise SystemExit(1)
if __name__=="__main__": main()
