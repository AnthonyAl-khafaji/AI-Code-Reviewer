from flask import Flask, jsonify, request
from flask_cors import CORS
import tempfile, subprocess, json, os, re

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": ["http://localhost:5173", "http://127.0.0.1:5173"]}},
     supports_credentials=True)

# ---------------------------
#         HEALTH
# ---------------------------
@app.get("/")
@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "backend"})

# ---------------------------
#       CODE REVIEW (REAL METRICS + OUTPUT)
# ---------------------------
@app.post("/review")
def review():
    """
    Body: { "filename": "snippet.py", "code": "print('hi')" }
    Returns: {
      summary: str,
      issues: [{type, detail, line}],
      scores: {readability, complexity, security, testing},
      output: str,                # <-- NEW: program output (stdout/stderr)
      suggestions: [str]
    }
    """
    data = request.get_json(force=True) or {}
    code = (data.get("code") or "").strip()
    filename = (data.get("filename") or "snippet.py").strip()

    if not code:
        return {"error": "No code provided."}, 400

    if not filename.lower().endswith(".py"):
        return {
            "summary": "Non-Python file — analysis is only enabled for .py in this MVP.",
            "issues": [],
            "scores": {"readability": 0, "complexity": 0, "security": 0, "testing": 0},
            "output": "(not run — non-Python file)",
            "suggestions": ["Paste a .py file to get full analysis."]
        }

    issues = []
    metrics = {"mi": None, "avg_cc": None, "max_cc": None}
    sec_findings = []

    # Write code once; reuse the same file for tools
    with tempfile.NamedTemporaryFile(delete=False, suffix=".py") as tmp:
        tmp.write(code.encode("utf-8"))
        path = tmp.name

    try:
        # 1) Syntax error (fast, friendly)
        syn_err = syntax_check(code)
        if syn_err:
            issues.append(syn_err)

        # 2) Ruff (lint)
        issues += run_ruff(path)

        # 3) Radon (Maintainability Index + Cyclomatic Complexity)
        metrics.update(run_radon_metrics(path))

        # 4) Bandit (security)
        sec_findings = run_bandit(path)
        for f in sec_findings:
            issues.append({
                "type": f.get("test_id", "BANDIT"),
                "detail": f.get("issue_text", "Potential security issue"),
                "line": f.get("line_number")
            })

        # 5) Scores + suggestions + summary
        scores = score_from(metrics, issues, sec_findings, code)
        suggestions = build_suggestions(metrics, issues, sec_findings, code)
        lint_count = len([i for i in issues if not (i.get("type") or "").startswith("SYNTAX")])
        summary = pretty_summary(metrics, lint_count, len(sec_findings))

        # 6) Run the code and capture stdout/stderr for the UI
        output = run_code_output(code)

        return {
            "summary": summary,
            "issues": issues,
            "scores": scores,
            "output": output,   # <-- NEW
            "suggestions": suggestions
        }
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


# ---------------------------
#           Helpers
# ---------------------------
def run(cmd, timeout=20):
    """Run a subprocess and return CompletedProcess."""
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

def syntax_check(code: str):
    """Return a friendly syntax error entry or None."""
    try:
        compile(code, "<string>", "exec")
        return None
    except SyntaxError as e:
        return {"type": "SYNTAX_ERROR", "detail": f"{e.msg}", "line": e.lineno or None}

def run_ruff(path: str):
    """Run ruff and normalize to our issues list."""
    try:
        out = run(["ruff", "check", path, "--output-format", "json"])
    except FileNotFoundError:
        return [{"type": "RUFF_MISSING", "detail": "ruff not installed in venv", "line": None}]
    except Exception as e:
        return [{"type": "RUFF_ERROR", "detail": str(e), "line": None}]

    # ruff: 0 clean, 1 findings, >1 internal error
    if out.returncode not in (0, 1):
        return [{"type": "RUFF_ERROR", "detail": (out.stderr or "ruff failed").strip(), "line": None}]

    findings = json.loads(out.stdout) if out.stdout.strip() else []
    issues = []
    for f in findings:
        loc = f.get("location", {})
        issues.append({
            "type": f.get("code", "RUFF"),
            "detail": f.get("message", "Lint"),
            "line": loc.get("row"),
        })
    return issues

def run_radon_metrics(path: str):
    """Get Maintainability Index and Cyclomatic Complexity via radon CLI."""
    res = {"mi": None, "avg_cc": None, "max_cc": None}

    # Maintainability Index (MI)
    try:
        out = run(["radon", "mi", "-j", path])
        if out.returncode == 0 and out.stdout.strip():
            mi_data = json.loads(out.stdout)
            mi_raw = mi_data.get(path)
            mi_val = None
            if isinstance(mi_raw, dict):
                mi_val = mi_raw.get("mi")
            elif isinstance(mi_raw, list) and mi_raw:
                mi_val = mi_raw[0].get("mi")
            if isinstance(mi_val, (int, float)):
                res["mi"] = float(mi_val)
    except Exception:
        pass

    # Cyclomatic Complexity (CC)
    try:
        out = run(["radon", "cc", "-s", "-j", path])
        if out.returncode == 0 and out.stdout.strip():
            cc_data = json.loads(out.stdout)
            entries = cc_data.get(path) or []
            if entries:
                nums = [e.get("complexity") for e in entries if isinstance(e.get("complexity"), (int, float))]
                if nums:
                    res["avg_cc"] = sum(nums) / len(nums)
                    res["max_cc"] = max(nums)
                else:
                    res["avg_cc"] = 0.0
                    res["max_cc"] = 0.0
            else:
                res["avg_cc"] = 0.0
                res["max_cc"] = 0.0
        else:
            res["avg_cc"] = 0.0
            res["max_cc"] = 0.0
    except Exception:
        pass

    return res

def run_bandit(path: str):
    """Run Bandit and return raw findings list (can be empty)."""
    try:
        out = run(["bandit", "-q", "-f", "json", path], timeout=30)
    except FileNotFoundError:
        return []
    except Exception:
        return []

    # Bandit returns 0 (no issues) or 1 (issues found)
    if out.returncode not in (0, 1):
        return []

    try:
        data = json.loads(out.stdout or "{}")
    except Exception:
        return []
    return data.get("results", []) or []

def score_from(metrics, issues, sec_findings, code):
    """
    Build dynamic 0-100 scores.
    If there's a syntax error, most scores = 0 (security only >0 if Bandit found something).
    """
    if any(i.get("type") == "SYNTAX_ERROR" for i in issues):
        return {
            "readability": 0,
            "complexity": 0,
            "security": 0 if not sec_findings else 30,
            "testing": 0
        }

    # Readability from MI
    mi = metrics.get("mi")
    readability = clamp(mi if isinstance(mi, (int, float)) else 0, 0, 100)

    # Complexity from avg CC (lower CC => higher score)
    avg_cc = metrics.get("avg_cc")
    if isinstance(avg_cc, (int, float)):
        if   avg_cc <= 1:  complexity = 95
        elif avg_cc <= 3:  complexity = 85
        elif avg_cc <= 6:  complexity = 70
        elif avg_cc <= 10: complexity = 55
        else:              complexity = 35
    else:
        complexity = 0

    # Security: penalize by Bandit severity
    penalty = 0
    for f in sec_findings:
        sev = (f.get("issue_severity") or "").upper()
        penalty += 20 if sev == "HIGH" else 10 if sev == "MEDIUM" else 5
    security = clamp(95 - penalty, 0, 95)

    # Testing: basic heuristic
    has_tests = bool(
        re.search(r"\bimport\s+(unittest|pytest)\b", code) or
        re.search(r"\bdef\s+test_", code)
    )
    testing = 80 if has_tests else 20

    return {
        "readability": int(round(readability)),
        "complexity": int(round(complexity)),
        "security": int(round(security)),
        "testing": int(round(testing)),
    }

def build_suggestions(metrics, issues, sec_findings, code):
    """Turn metrics + issues into actionable suggestions."""
    sugg = []

    if any(i.get("type") == "SYNTAX_ERROR" for i in issues):
        sugg.append("Fix the syntax error first so static analysis can run cleanly.")

    codes = {i.get("type") for i in issues if i.get("type")}
    if "F401" in codes:
        sugg.append("Remove unused imports (ruff F401).")
    if "E302" in codes or "E305" in codes:
        sugg.append("Apply PEP 8 spacing around functions/classes.")
    if "E501" in codes:
        sugg.append("Wrap long lines (E501) to improve readability.")
    if any(str(c).startswith("B") for c in codes):
        sugg.append("Review potential security issues flagged by Bandit.")

    avg_cc = metrics.get("avg_cc")
    if isinstance(avg_cc, (int, float)) and avg_cc > 6:
        sugg.append("Refactor large/nested functions to reduce cyclomatic complexity.")
    mi = metrics.get("mi")
    if isinstance(mi, (int, float)) and mi < 60:
        sugg.append("Increase maintainability: simplify logic, extract helpers, add docstrings.")

    hi = [f for f in sec_findings if (f.get("issue_severity") or "").upper() == "HIGH"]
    if hi:
        sugg.append(f"Address {len(hi)} HIGH-severity Bandit finding(s) immediately.")
    elif sec_findings:
        sugg.append("Resolve Bandit MED/LOW findings as part of hardening.")

    if not (re.search(r"\bimport\s+(unittest|pytest)\b", code) or re.search(r"\bdef\s+test_", code)):
        sugg.append("Add unit tests (pytest or unittest) for critical paths and edge cases.")

    if not sugg:
        sugg.append("Looks good. Consider docstrings and a few tests to lock behavior in.")
    return sugg

def pretty_summary(metrics, lint_count, sec_count):
    """Readable summary line for the UI."""
    mi = metrics.get("mi")
    avg_cc = metrics.get("avg_cc")
    max_cc = metrics.get("max_cc")

    mi_txt = "n/a" if mi is None else f"{mi:.0f}"
    avg_txt = "n/a" if avg_cc is None else f"{avg_cc:.1f}"
    max_txt = "n/a" if max_cc is None else f"{max_cc:.1f}"

    # simple label for avg complexity
    if isinstance(avg_cc, (int, float)):
        if   avg_cc == 0:  cx_label = "trivial"
        elif avg_cc <= 3:  cx_label = "low"
        elif avg_cc <= 6:  cx_label = "moderate"
        elif avg_cc <= 10: cx_label = "high"
        else:              cx_label = "very high"
    else:
        cx_label = "n/a"

    return (
        f"Maintainability Index: {mi_txt} | "
        f"Complexity: avg {avg_txt} ({cx_label}), max {max_txt} | "
        f"Ruff: {lint_count} issues | "
        f"Bandit: {sec_count} findings"
    )

def run_code_output(code: str):
    """Run the user's code and capture stdout/stderr so the UI can show output."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".py") as tmp:
        tmp.write(code.encode("utf-8"))
        path = tmp.name
    try:
        out = subprocess.run(
            ["python", path],
            capture_output=True,
            text=True,
            timeout=5
        )
        pieces = []
        if out.stdout.strip():
            pieces.append(out.stdout.strip())
        if out.stderr.strip():
            pieces.append("ERR: " + out.stderr.strip())
        return "\n".join(pieces) if pieces else "(no output)"
    except Exception as e:
        return f"Runtime error: {e}"
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

# ---------------------------
#            CHAT (same)
# ---------------------------
@app.post("/chat")
def chat():
    """
    Try Ollama (llama3.2:3b) -> OpenAI -> echo.
    Returns: { reply: "...", source: "ollama"|"openai"|"echo" }
    """
    data = request.get_json(force=True) or {}
    msgs = data.get("messages") or []
    last_user = next((m.get("content","") for m in reversed(msgs) if m.get("role")=="user"), "").strip()

    # 1) Ollama (no key)
    try:
        import requests
        r = requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={
                "model": os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
                "prompt": last_user or "Hello",
                "stream": False,
                "options": {"temperature": 0.3}
            },
            timeout=60
        )
        if r.ok:
            j = r.json()
            reply = (j.get("response") or "").strip()
            if reply:
                return {"reply": reply, "source": "ollama"}
        else:
            print("Ollama HTTP error:", r.status_code, r.text[:200])
    except Exception as e:
        print("Ollama exception:", e)

    # 2) OpenAI (optional)
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            conv = [{"role": "system", "content": "You are a helpful coding assistant. Keep answers short."}]
            for m in msgs:
                role = m.get("role") or "user"
                content = (m.get("content") or "").strip()
                if content:
                    conv.append({"role": role, "content": content})
            resp = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=conv,
                temperature=0.3,
            )
            reply = resp.choices[0].message.content
            if reply:
                return {"reply": reply, "source": "openai"}
        except Exception as e:
            print("OpenAI exception:", e)

    # 3) Echo fallback
    return {"reply": f"You said: {last_user}", "source": "echo"}

# ---------------------------
#        ENTRY POINT
# ---------------------------
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)
