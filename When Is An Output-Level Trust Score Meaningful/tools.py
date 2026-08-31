"""
tools.py — minimal, deterministic tool layer for the construct-validity study.

Tools are intentionally local and deterministic so that the clean "gold"
trajectories are fully reproducible and so that the correct observation for any
action is known by construction (which is what fault injection needs). A live
web_search wrapper is included but is OFF by default; the seed tasks use only
calculator and kb_lookup.

A tool call is represented in a trajectory as the string  name(arg=value, ...)
and a tool result (observation) is the JSON-serialisable object the tool returns.
"""

import ast, json, operator, re

# ---- safe arithmetic -------------------------------------------------------
_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg,
    ast.Mod: operator.mod,
}

def _safe_eval(node):
    if isinstance(node, ast.Num):
        return node.n
    if isinstance(node, ast.BinOp):
        return _OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp):
        return _OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("unsupported expression")

def calculator(expression: str):
    """Evaluate a basic arithmetic expression. Returns a number."""
    tree = ast.parse(str(expression), mode="eval")
    return round(float(_safe_eval(tree.body)), 4)


def kb_lookup(key: str, kb: dict):
    """Look up a key in the task knowledge base. Returns the stored value or None."""
    return kb.get(key)


# ---- optional live retrieval (off by default) ------------------------------
def web_search(query: str):
    """
    Optional DuckDuckGo instant-answer lookup. Requires network access and is
    NOT used by the seed tasks. Returns a short text or None.
    """
    import requests
    try:
        r = requests.get("https://api.duckduckgo.com/", timeout=10,
                         headers={"User-Agent": "TRACE-Study/1.0"},
                         params={"q": query, "format": "json", "no_html": "1"})
        d = r.json()
        for f in ("Abstract", "Answer", "Definition"):
            if d.get(f, "").strip():
                return d[f].strip()
    except Exception:
        return None
    return None


TOOLS = {"calculator": calculator, "kb_lookup": kb_lookup, "web_search": web_search}


def parse_call(text: str):
    """
    Parse a tool-call string of the form  name(arg=value, ...)  into
    (name, kwargs). Values are parsed as Python literals where possible,
    else kept as strings. Returns (None, None) if the text is not a call.
    """
    m = re.match(r"\s*([a-zA-Z_]\w*)\s*\((.*)\)\s*$", text, re.DOTALL)
    if not m:
        return None, None
    name, body = m.group(1), m.group(2).strip()
    kwargs = {}
    if body:
        # split on commas that are not inside quotes/brackets (simple cases only)
        parts = re.split(r",(?![^\[\(]*[\]\)])", body)
        for p in parts:
            if "=" in p:
                k, v = p.split("=", 1)
                k, v = k.strip(), v.strip()
                try:
                    kwargs[k] = ast.literal_eval(v)
                except Exception:
                    kwargs[k] = v.strip("\"'")
    return name, kwargs


def execute(call_text: str, kb: dict):
    """Execute a tool-call string against the task kb. Returns the observation."""
    name, kwargs = parse_call(call_text)
    if name not in TOOLS:
        return {"error": f"unknown tool: {name}"}
    if name == "kb_lookup":
        return {"result": kb_lookup(kwargs.get("key", ""), kb)}
    if name == "calculator":
        return {"result": calculator(kwargs.get("expression", ""))}
    if name == "web_search":
        return {"result": web_search(kwargs.get("query", ""))}
    return {"error": "unhandled"}
