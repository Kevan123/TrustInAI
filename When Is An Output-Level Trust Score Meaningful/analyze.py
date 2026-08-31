"""
analyze.py — turn the scored JSONL into the construct-validity results.

Produces three tables and writes them as CSV:
  A. Availability by step type   (does each signal even apply per step type?)
  B. Fault detection             (does the expected signal fire at the fault?)
  C. Signal structure            (correlation + Cronbach alpha on co-available signals)

Usage:  python analyze.py --in steps.jsonl --outdir results
"""

import argparse, json, os
import numpy as np
import pandas as pd

SIGNALS = ["E", "V", "S", "L", "C"]
DROP_THRESHOLD = 0.15   # a signal "fires" if it drops by at least this from clean


def load(path):
    rows = [json.loads(l) for l in open(path) if l.strip()]
    return pd.DataFrame(rows)


def table_availability(df):
    clean = df[df["condition"] == "clean"].copy()
    out = []
    for st in ["reason", "act", "observe", "synthesize"]:
        sub = clean[clean["step_type"] == st]
        if len(sub) == 0:
            continue
        for sig in SIGNALS:
            statuses = [r.get(sig) for r in sub["availability"] if isinstance(r, dict)]
            n = len(statuses)
            row = {"step_type": st, "signal": sig, "n": n}
            for key in ["computed", "degenerate", "not_applicable"]:
                row[key] = round(sum(1 for s in statuses if s == key) / n, 3) if n else None
            out.append(row)
    return pd.DataFrame(out)


def table_fault_detection(df):
    clean = df[df["condition"] == "clean"]
    clean_idx = {(r["task_id"], r["step_index"]): r for _, r in clean.iterrows()}
    faulted = df[df["condition"] == "faulted"]
    out = []
    for _, fr in faulted.iterrows():
        key = (fr["task_id"], fr["step_index"])
        cr = clean_idx.get(key)
        if cr is None:
            continue
        exp = fr.get("expected_signal") or []
        rec = {"task_id": fr["task_id"], "step_index": fr["step_index"],
               "step_type": fr["step_type"], "fault_type": fr["fault_type"],
               "expected_signal": ",".join(exp) if exp else "(none)"}
        # did the expected signal(s) fire?
        fired, unavailable = False, False
        for sig in exp:
            cv, fv = cr.get(sig), fr.get(sig)
            if cv is None or fv is None:
                unavailable = True
                continue
            if (cv - fv) >= DROP_THRESHOLD:
                fired = True
        rec["expected_fired"] = fired
        rec["expected_unavailable"] = unavailable and not fired
        # composite movement
        ct, ft = cr.get("T"), fr.get("T")
        rec["T_clean"] = ct
        rec["T_faulted"] = ft
        rec["T_dropped"] = (ct is not None and ft is not None and (ct - ft) >= 5)
        rec["routing_changed"] = (cr.get("routing") != fr.get("routing"))
        # for the hypothesised-gap fault, did ANYTHING catch it?
        any_fired = False
        for sig in SIGNALS:
            cv, fv = cr.get(sig), fr.get(sig)
            if cv is not None and fv is not None and (cv - fv) >= DROP_THRESHOLD:
                any_fired = True
        rec["any_signal_fired"] = any_fired
        out.append(rec)
    return pd.DataFrame(out)


def _cronbach_alpha(matrix):
    """matrix: n_obs x k_items, no NaNs."""
    m = np.asarray(matrix, dtype=float)
    n, k = m.shape
    if k < 2 or n < 2:
        return None
    item_var = m.var(axis=0, ddof=1)
    total_var = m.sum(axis=1).var(ddof=1)
    if total_var == 0:
        return None
    return round((k / (k - 1)) * (1 - item_var.sum() / total_var), 3)


def table_structure(df):
    # rows where all five signals are numeric (co-available)
    def all_present(r):
        return all(pd.notna(r.get(s)) for s in SIGNALS)
    sub = df[df.apply(all_present, axis=1)]
    info = {"n_co_available": int(len(sub))}
    if len(sub) >= 2:
        M = sub[SIGNALS].astype(float)
        corr = M.corr().round(3)
        info["cronbach_alpha"] = _cronbach_alpha(M.values)
    else:
        corr = pd.DataFrame()
        info["cronbach_alpha"] = None
    return corr, info


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="steps.jsonl")
    ap.add_argument("--outdir", default="results")
    args = ap.parse_args(argv)
    os.makedirs(args.outdir, exist_ok=True)

    df = load(args.inp)
    print(f"loaded {len(df)} step records "
          f"({(df.condition=='clean').sum()} clean, {(df.condition=='faulted').sum()} faulted)\n")

    A = table_availability(df)
    A.to_csv(os.path.join(args.outdir, "availability_by_steptype.csv"), index=False)
    print("== Table A: availability by step type (fraction over clean steps) ==")
    print(A.to_string(index=False), "\n")

    B = table_fault_detection(df)
    B.to_csv(os.path.join(args.outdir, "fault_detection.csv"), index=False)
    if len(B):
        print("== Table B: fault detection ==")
        summ = (B.groupby(["fault_type", "expected_signal"])
                  .agg(n=("expected_fired", "size"),
                       expected_fired_rate=("expected_fired", "mean"),
                       expected_unavailable_rate=("expected_unavailable", "mean"),
                       T_dropped_rate=("T_dropped", "mean"),
                       routing_changed_rate=("routing_changed", "mean"),
                       any_signal_fired_rate=("any_signal_fired", "mean"))
                  .round(3).reset_index())
        print(summ.to_string(index=False), "\n")
        summ.to_csv(os.path.join(args.outdir, "fault_detection_summary.csv"), index=False)

    corr, info = table_structure(df)
    print("== Table C: signal structure (co-available rows) ==")
    print("n co-available:", info["n_co_available"], "| Cronbach alpha:", info["cronbach_alpha"])
    if not corr.empty:
        print(corr.to_string())
        corr.to_csv(os.path.join(args.outdir, "signal_correlation.csv"))
    print(f"\nCSVs written to {args.outdir}/")


if __name__ == "__main__":
    main()
