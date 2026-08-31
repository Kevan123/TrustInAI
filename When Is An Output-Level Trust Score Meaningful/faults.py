"""
faults.py — controlled fault catalogue and single-step injector.

Each fault type maps to a documented agent failure archetype, applies to
specific step types, and carries an `expected_signal`: the TRACE signal(s)
hypothesised to detect it. The construct-validity test is whether the expected
signal actually fires (drops) at the faulted step, and whether signals that are
structurally inapplicable to that step type stay silent.

Injection mutates exactly ONE step of a copied trajectory and labels it. All
mutators are deterministic and require no model call, so ground truth is exact.

Archetypes (Pan et al. 2025; Ji et al. 2024; and the car-wash task-goal
violation from the TRACE papers):
  HALLUCINATED_FACT       confident false claim in a claim-bearing step
  WRONG_TOOL_ARG          corrupted argument in a tool call
  GOAL_INCOHERENT_ACTION  syntactically valid but goal-irrelevant action
  FABRICATED_OBSERVATION  tool result not produced by the tool / inconsistent
  PREMATURE_SYNTHESIS     final answer overreaching the gathered evidence
"""

import copy, json, re


def _largest_number(text):
    nums = re.findall(r"-?\d+(?:\.\d+)?", text)
    if not nums:
        return None
    return max(nums, key=lambda s: abs(float(s)))


def _mut_hallucinated_fact(step, task):
    """Replace the salient number with a clearly false one, else append a false clause."""
    text = step["text"]
    n = _largest_number(text)
    if n is not None:
        wrong = str(round(float(n) * 3 + 1, 4)).rstrip("0").rstrip(".")
        return text.replace(n, wrong, 1)
    return text.rstrip(".") + ". This figure is the officially established and verified value."


def _mut_wrong_tool_arg(step, task):
    text = step["text"]
    # kb_lookup: point at a non-existent key
    m = re.search(r'key\s*=\s*["\']([^"\']+)["\']', text)
    if m:
        return text.replace(m.group(1), m.group(1) + "_typo", 1)
    # calculator: corrupt the first number in the expression
    n = _largest_number(text)
    if n is not None:
        wrong = str(round(float(n) * 2 + 5, 4)).rstrip("0").rstrip(".")
        return text.replace(n, wrong, 1)
    return text


def _mut_goal_incoherent(step, task):
    # a valid call that does nothing for the task goal (car-wash analogue)
    return 'calculator(expression="2+2")'


def _mut_fabricated_observation(step, task):
    text = step["text"]
    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and "result" in obj and isinstance(obj["result"], (int, float)):
            obj["result"] = round(float(obj["result"]) * 9 + 7, 4)
            return json.dumps(obj)
    except Exception:
        pass
    return json.dumps({"result": "value confirmed from internal records"})


def _mut_premature_synthesis(step, task):
    return ("The applicant clearly qualifies for the maximum available facility "
            "and no further verification of the policy thresholds is required.")


FAULTS = {
    "HALLUCINATED_FACT":      {"applies_to": {"reason", "synthesize"},
                               "expected_signal": {"E", "V"},
                               "mutate": _mut_hallucinated_fact},
    "WRONG_TOOL_ARG":         {"applies_to": {"act"},
                               "expected_signal": {"L"},
                               "mutate": _mut_wrong_tool_arg},
    "GOAL_INCOHERENT_ACTION": {"applies_to": {"act"},
                               "expected_signal": {"L"},
                               "mutate": _mut_goal_incoherent},
    "FABRICATED_OBSERVATION": {"applies_to": {"observe"},
                               "expected_signal": set(),  # hypothesised gap
                               "mutate": _mut_fabricated_observation},
    "PREMATURE_SYNTHESIS":    {"applies_to": {"synthesize"},
                               "expected_signal": {"L", "C"},
                               "mutate": _mut_premature_synthesis},
}


def inject(task, fault_type, step_index):
    """
    Return a (faulted_step, label) pair for a single injected fault.
    The faulted_step is a copy of the target step with mutated text; the label
    records the fault type, expected signal, and that this is the fault step.
    Honours an optional per-task override in task['fault_overrides'].
    """
    spec = FAULTS[fault_type]
    step = None
    for s in task["trajectory"]:
        if s["step_index"] == step_index:
            step = copy.deepcopy(s)
            break
    if step is None:
        raise ValueError(f"no step {step_index} in task {task['task_id']}")
    if step["step_type"] not in spec["applies_to"]:
        raise ValueError(f"{fault_type} does not apply to a {step['step_type']} step")

    override = None
    for o in task.get("fault_overrides", []):
        if o["fault_type"] == fault_type and o["step_index"] == step_index:
            override = o
            break
    step["text"] = override["faulted_text"] if override else spec["mutate"](step, task)

    label = {
        "is_fault_step": True,
        "fault_type": fault_type,
        "expected_signal": sorted(spec["expected_signal"]),
    }
    return step, label


def enumerate_faults(task):
    """
    Yield (fault_type, step_index) for every applicable auto-fault on this task,
    plus any explicitly declared overrides. One fault per applicable step.
    """
    seen = set()
    for s in task["trajectory"]:
        for ft, spec in FAULTS.items():
            if s["step_type"] in spec["applies_to"]:
                key = (ft, s["step_index"])
                if key not in seen:
                    seen.add(key)
                    yield key
    for o in task.get("fault_overrides", []):
        key = (o["fault_type"], o["step_index"])
        if key not in seen:
            seen.add(key)
            yield key
