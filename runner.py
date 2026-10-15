"""Runs student code against test cases in a throwaway directory.

Limits applied: wall-clock timeout, CPU/file-size rlimits, minimal environment.
This is a lightweight sandbox for a campus project, NOT a hardened one. For a
public deployment run code in containers (e.g. Judge0, Piston) instead.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time

TIMEOUT = 5
MAX_OUT = 6000

LANGS = {
    "python": {"label": "Python 3", "file": "main.py", "compile": None,
               "run": [sys.executable, "-I", "main.py"], "need": [sys.executable]},
    "javascript": {"label": "JavaScript (Node.js)", "file": "main.js", "compile": None,
                   "run": ["node", "main.js"], "need": ["node"]},
    "c": {"label": "C (gcc)", "file": "main.c",
          "compile": ["gcc", "main.c", "-O1", "-o", "main", "-lm"],
          "run": ["./main"], "need": ["gcc"]},
    "java": {"label": "Java", "file": "Main.java", "compile": ["javac", "Main.java"],
             "run": ["java", "-Xmx256m", "Main"], "need": ["javac", "java"]},
}


def is_available(lang):
    cfg = LANGS.get(lang)
    return bool(cfg) and all(shutil.which(x) or os.path.exists(x) for x in cfg["need"])


def availability():
    return {k: is_available(k) for k in LANGS}


def _preexec():
    try:
        import resource
    except ImportError:  # Windows
        return None

    def limits():
        resource.setrlimit(resource.RLIMIT_CPU, (8, 8))
        resource.setrlimit(resource.RLIMIT_FSIZE, (2_000_000, 2_000_000))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    return limits


def _trim(s):
    s = s or ""
    return s if len(s) <= MAX_OUT else s[:MAX_OUT] + "\n...[output truncated]"


def normalize(s):
    lines = [ln.rstrip() for ln in (s or "").replace("\r\n", "\n").split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def _env(workdir):
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": workdir, "LANG": "C.UTF-8"}


def _run_one(cfg, workdir, stdin, timeout):
    start = time.time()
    try:
        p = subprocess.run(
            cfg["run"], cwd=workdir, input=stdin or "", capture_output=True, text=True,
            timeout=timeout, env=_env(workdir), preexec_fn=_preexec(), start_new_session=True,
        )
        status = "ok" if p.returncode == 0 else "runtime_error"
        return {"status": status, "stdout": _trim(p.stdout), "stderr": _trim(p.stderr),
                "ms": int((time.time() - start) * 1000)}
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "stdout": "", "stderr": f"Time limit exceeded ({timeout}s)",
                "ms": int(timeout * 1000)}
    except Exception as exc:  # noqa: BLE001
        return {"status": "runtime_error", "stdout": "", "stderr": str(exc), "ms": 0}


def evaluate(lang, code, cases, timeout=TIMEOUT):
    """cases: list of {"in": str, "out": str|None}. Returns dict with results or error."""
    cfg = LANGS.get(lang)
    if not cfg:
        return {"error": "Unsupported language."}
    if not is_available(lang):
        return {"error": f"{cfg['label']} is not installed on this server, so code can't be run here."}
    if len(code) > 20000:
        return {"error": "Code is too long (limit 20,000 characters)."}
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, cfg["file"]), "w", encoding="utf-8") as fh:
            fh.write(code)
        if cfg["compile"]:
            try:
                p = subprocess.run(cfg["compile"], cwd=d, capture_output=True, text=True,
                                   timeout=30, env=_env(d), start_new_session=True)
            except subprocess.TimeoutExpired:
                return {"compile_error": "Compilation timed out."}
            if p.returncode != 0:
                return {"compile_error": _trim(p.stderr or p.stdout)}
        results = []
        for c in cases:
            r = _run_one(cfg, d, c.get("in", ""), timeout)
            if c.get("out") is not None:
                r["passed"] = r["status"] == "ok" and normalize(r["stdout"]) == normalize(c["out"])
            results.append(r)
        return {"results": results}
