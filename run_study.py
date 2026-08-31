"""
run_study.py — build the labelled step dataset and score every step.

For each task it emits:
  * all CLEAN steps of the gold trajectory (condition=clean), and
  * for each enumerated fault, ONLY the single mutated step (condition=faulted).
Non-fault steps of a faulted variant are identical to the clean trajectory, so
scoring them again is wasted cost; pairing is done on (task_id, step_index).

Each step is scored through the backend /score_text endpoint (default) or, with
--local, by importing score_components directly. Output is JSONL; an optional
--push uploads to the HF dataset.

Usage:
  export TRACE_API_KEY=...            # same secret the backend expects
  python run_study.py --backend https://your-backend.onrender.com --out steps.jsonl
  python run_study.py --local --out steps.jsonl          # if running on the backend host
  python run_study.py ... --push --hf-repo phigrr/trace-experiment-logs
"""

import argparse, json, os, time, sys
import requests

import faults as faultlib


def load_tasks(path):
    with open(path) as f:
        return json.load(f)["tasks"]


def build_records(tasks, model):
    """Yield un-scored step records (clean + one mutated step per fault)."""
    for task in tasks:
        tid = task["task_id"]
        # clean trajectory: every step
        for s in task["trajectory"]:
            yield {
                "trajectory_id": f"{tid}::clean",
                "task_id": tid, "goal": task["goal"],
                "step_index": s["step_index"], "step_type": s["step_type"],
                "text": s["text"], "query_anchor": s.get("query_anchor", ""),
                "alts": s.get("alts"),
                "condition": "clean", "variant": "clean",
                "is_fault_step": False, "fault_type": None,
                "expected_signal": [], "model": model,
            }
        # faulted variants: only the mutated step
        for ft, si in faultlib.enumerate_faults(task):
            try:
                fstep, label = faultlib.inject(task, ft, si)
            except ValueError:
                continue
            yield {
                "trajectory_id": f"{tid}::{ft}@{si}",
                "task_id": tid, "goal": task["goal"],
                "step_index": si, "step_type": fstep["step_type"],
                "text": fstep["text"], "query_anchor": fstep.get("query_anchor", ""),
                "alts": fstep.get("alts"),
                "condition": "faulted", "variant": f"{ft}@{si}",
                "is_fault_step": label["is_fault_step"], "fault_type": ft,
                "expected_signal": label["expected_signal"], "model": model,
            }


def make_http_scorer(backend, api_key, weights, risk, timeout=180, retries=3):
    url = backend.rstrip("/") + "/score_text"
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    def scorer(rec):
        payload = {"text": rec["text"], "query_anchor": rec["query_anchor"],
                   "step_type": rec["step_type"], "alts": rec["alts"],
                   "weights": weights, "risk": risk}
        for attempt in range(retries):
            try:
                r = requests.post(url, headers=headers, json=payload, timeout=timeout)
                r.raise_for_status()
                return r.json()
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(5 * (attempt + 1))
                else:
                    return {"error": str(e)}
    return scorer


def make_local_scorer(weights, risk):
    import main  # requires the backend deps (nltk, cerebras sdk) on this host
    def scorer(rec):
        return main.score_components(rec["text"], query_anchor=rec["query_anchor"],
                                     step_type=rec["step_type"], alts=rec["alts"],
                                     weights=weights, risk=risk)
    return scorer


def get_model(backend, api_key, local):
    if local:
        try:
            import main
            return main.LLM_MODEL
        except Exception:
            return "unknown"
    try:
        r = requests.get(backend.rstrip("/") + "/health", timeout=20)
        return r.json().get("model", "unknown")
    except Exception:
        return "unknown"


def run(tasks, scorer, model, out_path, limit=None):
    n = 0
    with open(out_path, "w") as f:
        for rec in build_records(tasks, model):
            res = scorer(rec)
            keep = {k: res.get(k) for k in
                    ["E", "V", "S", "L", "C", "T", "routing", "availability",
                     "verdict", "hat_p", "n_claims", "contested"]}
            rec.update(keep)
            f.write(json.dumps(rec) + "\n")
            n += 1
            if limit and n >= limit:
                break
    return n


def push_to_hf(out_path, repo):
    from huggingface_hub import HfApi
    token = os.environ.get("HF_TOKEN", "")
    if not token:
        print("HF_TOKEN not set; skipping push"); return
    api = HfApi(token=token)
    api.upload_file(path_or_fileobj=out_path,
                    path_in_repo=f"steps_{int(time.time())}.jsonl",
                    repo_id=repo, repo_type="dataset")
    print(f"pushed {out_path} -> {repo}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default="tasks.json")
    ap.add_argument("--backend", default=os.environ.get("TRACE_BACKEND", ""))
    ap.add_argument("--api-key", default=os.environ.get("TRACE_API_KEY", ""))
    ap.add_argument("--local", action="store_true")
    ap.add_argument("--out", default="steps.jsonl")
    ap.add_argument("--risk", type=float, default=0.20)
    ap.add_argument("--weights", default="0.2,0.2,0.2,0.2,0.2")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--hf-repo", default="phigrr/trace-experiment-logs")
    args = ap.parse_args(argv)

    weights = [float(x) for x in args.weights.split(",")]
    tasks = load_tasks(args.tasks)
    model = get_model(args.backend, args.api_key, args.local)

    if args.local:
        scorer = make_local_scorer(weights, args.risk)
    else:
        if not args.backend or not args.api_key:
            sys.exit("provide --backend and TRACE_API_KEY (or use --local)")
        scorer = make_http_scorer(args.backend, args.api_key, weights, args.risk)

    n = run(tasks, scorer, model, args.out, limit=args.limit)
    print(f"wrote {n} step records to {args.out} (model={model})")
    if args.push:
        push_to_hf(args.out, args.hf_repo)


if __name__ == "__main__":
    main()
