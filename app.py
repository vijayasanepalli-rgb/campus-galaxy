"""Campus Galaxy: Student Success Platform (Flask)."""
import csv
import io
import json
import os
from datetime import date, datetime
from functools import wraps

from flask import (Flask, Response, abort, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import bank
import copilot
import db as dbm
import importer
import runner
import scoring
import seed

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-galaxy-secret-change-me")
app.teardown_appcontext(dbm.close_db)

_booted = False

EVENT_KINDS = ["event", "hackathon", "workshop", "club", "certification"]
LANG_LABELS = {k: v["label"] for k, v in runner.LANGS.items()}

STUDENT_NAV = [
    ("student_overview", "Overview", "📊"), ("student_academics", "Academics", "📝"),
    ("student_tests", "Tests", "🤖"), ("student_attendance", "Attendance", "📅"),
    ("student_lms", "LMS", "📚"), ("student_engagement", "Engagement", "🏆"),
    ("student_placement", "Placement", "💼"), ("student_skills", "Skills & Feedback", "🧠"),
    ("student_score", "Success Score", "🎯"), ("copilot_page", "AI Copilot", "✨"),
    ("settings", "Settings", "⚙️"),
]
STAFF_NAV = [
    ("staff_overview", "Overview", "📊"), ("staff_students", "Students", "👨‍🎓"),
    ("staff_tests", "Tests & Coding", "📝"), ("staff_events", "Events", "🏆"),
    ("staff_interventions", "Interventions", "📈"), ("staff_reports", "Reports", "📄"),
    ("copilot_page", "AI Copilot", "✨"),
]
ADMIN_NAV = [("admin_integration", "Data Integration", "📥"), ("admin_users", "Users", "👥")]


@app.before_request
def boot_and_load_user():
    global _booted
    if not _booted:
        dbm.init_db()
        if dbm.get_db().execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            seed.run(dbm.get_db())
        _booted = True
    g.user = None
    uid = session.get("uid")
    if uid:
        g.user = dbm.get_db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()


@app.context_processor
def inject():
    nav = []
    if g.get("user"):
        role = g.user["role"]
        nav = STUDENT_NAV if role == "student" else STAFF_NAV + (ADMIN_NAV if role == "admin" else []) + [("settings", "Settings", "⚙️")]
    return {"nav": nav, "user": g.get("user"), "endpoint": request.endpoint,
            "band": lambda s: "good" if s >= 75 else ("ok" if s >= 55 else "low"),
            "lang_labels": LANG_LABELS}


@app.template_filter("mon")
def month_short(d):
    try:
        return ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][int(d[5:7]) - 1]
    except (ValueError, IndexError, TypeError):
        return ""


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not g.user:
            return redirect(url_for("login", next=request.path))
        return f(*a, **kw)
    return wrapper


def role_required(*roles):
    def deco(f):
        @wraps(f)
        def wrapper(*a, **kw):
            if not g.user:
                return redirect(url_for("login", next=request.path))
            if g.user["role"] not in roles:
                abort(403)
            return f(*a, **kw)
        return wrapper
    return deco


def home_for(role):
    return url_for("student_overview" if role == "student" else "staff_overview")


def all_rows():
    db = dbm.get_db()
    return [{"u": u, "m": scoring.student_metrics(db, u["id"])}
            for u in db.execute("SELECT * FROM users WHERE role='student' ORDER BY roll_no")]


def tests_with_status(sid):
    db = dbm.get_db()
    out = []
    for t in db.execute(
            "SELECT t.*, (SELECT COUNT(*) FROM questions WHERE test_id=t.id) AS qn, "
            "(SELECT COUNT(*) FROM problems WHERE test_id=t.id) AS pn, "
            "(SELECT COALESCE(SUM(points),0) FROM problems WHERE test_id=t.id) AS ptotal "
            "FROM tests t ORDER BY t.kind DESC, t.id"):
        d = dict(t)
        if t["kind"] == "mcq":
            a = db.execute("SELECT MAX(score) s, MAX(max_score) mx, COUNT(*) n FROM attempts WHERE test_id=? AND student_id=?",
                           (t["id"], sid)).fetchone()
            d["done"] = a["n"] > 0
            d["best"] = f"{a['s']:.0f}/{a['mx']:.0f}" if d["done"] else None
        else:
            c = db.execute("SELECT COALESCE(SUM(cb.score),0) s, COUNT(*) n FROM code_best cb JOIN problems p "
                           "ON p.id=cb.problem_id WHERE p.test_id=? AND cb.student_id=?", (t["id"], sid)).fetchone()
            d["done"] = c["n"] > 0
            d["best"] = f"{c['s']:.0f}/{d['ptotal']}" if d["done"] else None
        out.append(d)
    return out


# ------------------------------------------------------------------ auth
@app.route("/")
def index():
    if g.user:
        return redirect(home_for(g.user["role"]))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        u = dbm.get_db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if u and check_password_hash(u["password_hash"], request.form.get("password", "")):
            session.clear()
            session["uid"] = u["id"]
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else home_for(u["role"]))
        flash("Incorrect email or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ------------------------------------------------------------------ student pages
@app.route("/student")
@role_required("student")
def student_overview():
    db = dbm.get_db()
    m = scoring.student_metrics(db, g.user["id"])
    tests = tests_with_status(g.user["id"])
    pending = sum(1 for t in tests if not t["done"])
    upcoming = db.execute("SELECT e.* FROM events e WHERE e.event_date >= ? AND e.id NOT IN "
                          "(SELECT event_id FROM applications WHERE student_id=?) ORDER BY event_date LIMIT 3",
                          (date.today().isoformat(), g.user["id"])).fetchall()
    support = db.execute("SELECT * FROM interventions WHERE student_id=? ORDER BY id DESC", (g.user["id"],)).fetchall()
    tips = scoring.suggestions(m, pending, len(upcoming))
    chart = {"exams": m["exams"], "avgs": m["exam_avgs"],
             "subjects": [s["name"] for s in m["subjects"]], "latest": [s["latest"] for s in m["subjects"]]}
    return render_template("student_overview.html", m=m, pending=pending, upcoming=upcoming,
                           support=support, tips=tips, chart=chart)


@app.route("/student/academics")
@role_required("student")
def student_academics():
    m = scoring.student_metrics(dbm.get_db(), g.user["id"])
    return render_template("student_academics.html", m=m, plan=scoring.study_plan(m),
                           chart={"names": [s["name"] for s in m["subjects"]], "latest": [s["latest"] for s in m["subjects"]]})


@app.route("/student/attendance")
@role_required("student")
def student_attendance():
    m = scoring.student_metrics(dbm.get_db(), g.user["id"])
    return render_template("student_attendance.html", m=m)


@app.route("/student/lms")
@role_required("student")
def student_lms():
    m = scoring.student_metrics(dbm.get_db(), g.user["id"])
    return render_template("student_lms.html", m=m, res=scoring.resources(m, 6))


@app.route("/student/engagement")
@role_required("student")
def student_engagement():
    db = dbm.get_db()
    kind = request.args.get("kind", "")
    m = scoring.student_metrics(db, g.user["id"])
    rows = db.execute(
        "SELECT e.*, (SELECT status FROM applications WHERE event_id=e.id AND student_id=?) AS my_status, "
        "(SELECT COUNT(*) FROM applications WHERE event_id=e.id) AS n_apps FROM events e "
        "WHERE (?='' OR e.kind=?) ORDER BY e.event_date", (g.user["id"], kind, kind)).fetchall()
    today = date.today().isoformat()
    return render_template("student_engagement.html", m=m, upcoming=[e for e in rows if e["event_date"] >= today],
                           past=[e for e in rows if e["event_date"] < today][::-1], kind=kind, kinds=EVENT_KINDS)


@app.route("/student/engagement/apply/<int:eid>", methods=["POST"])
@role_required("student")
def student_apply(eid):
    db = dbm.get_db()
    if not db.execute("SELECT 1 FROM events WHERE id=?", (eid,)).fetchone():
        abort(404)
    db.execute("INSERT OR IGNORE INTO applications(event_id,student_id,status,applied_at) VALUES(?,?,?,?)",
               (eid, g.user["id"], "applied", now()))
    db.commit()
    flash("Application submitted. Good luck!", "ok")
    return redirect(request.referrer or url_for("student_engagement"))


@app.route("/student/placement")
@role_required("student")
def student_placement():
    m = scoring.student_metrics(dbm.get_db(), g.user["id"])
    return render_template("student_placement.html", m=m)


@app.route("/student/skills")
@role_required("student")
def student_skills():
    m = scoring.student_metrics(dbm.get_db(), g.user["id"])
    have = {s["skill"] for s in m["skills"]}
    return render_template("student_skills.html", m=m, missing=[s for s in scoring.SUGGESTED_SKILLS if s not in have][:4])


@app.route("/student/score")
@role_required("student")
def student_score():
    m = scoring.student_metrics(dbm.get_db(), g.user["id"])
    return render_template("student_score.html", m=m)


# ------------------------------------------------------------------ tests (student)
@app.route("/student/tests")
@role_required("student")
def student_tests():
    kind, lang = request.args.get("kind", ""), request.args.get("lang", "")
    tests = tests_with_status(g.user["id"])
    if kind:
        tests = [t for t in tests if t["kind"] == kind]
    if lang:
        tests = [t for t in tests if t["language"] == lang]
    return render_template("student_tests.html", tests=tests, kind=kind, lang=lang, avail=runner.availability())


@app.route("/student/tests/<int:tid>")
@role_required("student")
def student_take(tid):
    db = dbm.get_db()
    t = db.execute("SELECT * FROM tests WHERE id=?", (tid,)).fetchone()
    if not t:
        abort(404)
    if t["kind"] == "mcq":
        qs = [{"id": r["id"], "prompt": r["prompt"], "options": json.loads(r["options"])}
              for r in db.execute("SELECT * FROM questions WHERE test_id=? ORDER BY id", (tid,))]
        return render_template("test_mcq.html", t=t, qs=qs)
    probs = []
    for p in db.execute("SELECT * FROM problems WHERE test_id=? ORDER BY id", (tid,)):
        best = db.execute("SELECT * FROM code_best WHERE student_id=? AND problem_id=?", (g.user["id"], p["id"])).fetchone()
        cases = json.loads(p["cases"])
        probs.append({"id": p["id"], "title": p["title"], "statement": p["statement"], "points": p["points"],
                      "starter": best["code"] if best else p["starter"],
                      "best": best["score"] if best else 0, "passed": best["passed"] if best else 0,
                      "total": len(cases), "sample": [c for c in cases if not c.get("hidden")]})
    return render_template("test_code.html", t=t, probs=probs, available=runner.is_available(t["language"]),
                           lang_label=LANG_LABELS.get(t["language"], t["language"]))


@app.route("/student/tests/<int:tid>/submit", methods=["POST"])
@role_required("student")
def student_submit(tid):
    db = dbm.get_db()
    t = db.execute("SELECT * FROM tests WHERE id=? AND kind='mcq'", (tid,)).fetchone()
    if not t:
        abort(404)
    review, score, mx = [], 0, 0
    for r in db.execute("SELECT * FROM questions WHERE test_id=? ORDER BY id", (tid,)):
        opts = json.loads(r["options"])
        raw = request.form.get(f"q{r['id']}")
        chosen = int(raw) if raw is not None and raw.isdigit() else None
        right = chosen == r["answer"]
        mx += r["points"]
        score += r["points"] if right else 0
        review.append({"prompt": r["prompt"], "options": opts, "chosen": chosen, "answer": r["answer"], "right": right})
    db.execute("INSERT INTO attempts(test_id,student_id,score,max_score,submitted_at) VALUES(?,?,?,?,?)",
               (tid, g.user["id"], score, mx, now()))
    db.commit()
    return render_template("test_result.html", t=t, review=review, score=score, mx=mx)


# ------------------------------------------------------------------ code APIs
def _problem_and_test(pid):
    db = dbm.get_db()
    p = db.execute("SELECT * FROM problems WHERE id=?", (pid,)).fetchone()
    if not p:
        return None, None
    return p, db.execute("SELECT * FROM tests WHERE id=?", (p["test_id"],)).fetchone()


@app.route("/api/code/run", methods=["POST"])
@login_required
def api_run():
    data = request.get_json(silent=True) or {}
    p, t = _problem_and_test(data.get("problem_id"))
    if not p:
        return jsonify({"error": "Problem not found."}), 404
    code, custom = data.get("code", ""), data.get("stdin")
    if custom:
        res = runner.evaluate(t["language"], code, [{"in": custom, "out": None}])
        if "results" in res:
            r = res["results"][0]
            res["results"] = [{"label": "Custom input", "input": custom, "output": r["stdout"], "stderr": r["stderr"],
                               "status": r["status"], "ms": r["ms"], "passed": None}]
        return jsonify(res)
    cases = [c for c in json.loads(p["cases"]) if not c.get("hidden")]
    res = runner.evaluate(t["language"], code, cases)
    if "results" in res:
        res["results"] = [{"label": f"Sample {i + 1}", "input": c["in"], "expected": c["out"], "output": r["stdout"],
                           "stderr": r["stderr"], "status": r["status"], "ms": r["ms"], "passed": r.get("passed")}
                          for i, (c, r) in enumerate(zip(cases, res["results"]))]
    return jsonify(res)


@app.route("/api/code/submit", methods=["POST"])
@role_required("student")
def api_submit():
    data = request.get_json(silent=True) or {}
    p, t = _problem_and_test(data.get("problem_id"))
    if not p:
        return jsonify({"error": "Problem not found."}), 404
    code = data.get("code", "")
    cases = json.loads(p["cases"])
    db = dbm.get_db()
    before = scoring.student_metrics(db, g.user["id"])
    res = runner.evaluate(t["language"], code, cases)
    if "results" not in res:
        return jsonify(res)
    passed = sum(1 for r in res["results"] if r.get("passed"))
    total = len(cases)
    score = round(p["points"] * passed / total, 1) if total else 0
    old = db.execute("SELECT score FROM code_best WHERE student_id=? AND problem_id=?", (g.user["id"], p["id"])).fetchone()
    if old is None or score >= old["score"]:
        db.execute("INSERT OR REPLACE INTO code_best(student_id,problem_id,score,passed,total,code,updated_at) VALUES(?,?,?,?,?,?,?)",
                   (g.user["id"], p["id"], score, passed, total, code, now()))
        db.commit()
    after = scoring.student_metrics(db, g.user["id"])
    out = []
    for i, (c, r) in enumerate(zip(cases, res["results"])):
        item = {"label": f"Hidden test {i + 1}" if c.get("hidden") else f"Sample {i + 1}", "passed": r.get("passed"),
                "status": r["status"], "ms": r["ms"]}
        if not c.get("hidden"):
            item.update({"input": c["in"], "expected": c["out"], "output": r["stdout"], "stderr": r["stderr"]})
        out.append(item)
    return jsonify({"results": out, "passed": passed, "total": total, "score": score, "points": p["points"],
                    "best": max(score, old["score"] if old else 0),
                    "coding": after["placement"]["coding"], "success_before": before["success"],
                    "success_after": after["success"]})


# ------------------------------------------------------------------ copilot
@app.route("/copilot")
@login_required
def copilot_page():
    tips = []
    if g.user["role"] == "student":
        m = scoring.student_metrics(dbm.get_db(), g.user["id"])
        tips = scoring.suggestions(m)
    chips = copilot.CHIPS_STUDENT if g.user["role"] == "student" else copilot.CHIPS_STAFF
    return render_template("copilot.html", tips=tips, chips=chips)


@app.route("/api/copilot", methods=["POST"])
@login_required
def api_copilot():
    text = (request.get_json(silent=True) or {}).get("message", "").strip()[:500]
    if not text:
        return jsonify({"text": "Ask me something about your progress, studies or events.", "chips": []})
    db = dbm.get_db()
    if g.user["role"] == "student":
        res = copilot.reply(db, g.user, text, metrics=scoring.student_metrics(db, g.user["id"]))
    else:
        res = copilot.reply(db, g.user, text, staff_rows=all_rows())
    return jsonify(res)


# ------------------------------------------------------------------ settings
@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    db = dbm.get_db()
    if request.method == "POST":
        form = request.form.get("form")
        if form == "profile":
            name = request.form.get("name", "").strip()
            if name:
                db.execute("UPDATE users SET name=?, notify=? WHERE id=?",
                           (name, 1 if request.form.get("notify") else 0, g.user["id"]))
                db.commit()
                flash("Profile updated.", "ok")
        elif form == "password":
            if not check_password_hash(g.user["password_hash"], request.form.get("current", "")):
                flash("Current password is incorrect.", "error")
            elif len(request.form.get("new", "")) < 6:
                flash("New password must be at least 6 characters.", "error")
            else:
                db.execute("UPDATE users SET password_hash=? WHERE id=?",
                           (generate_password_hash(request.form["new"], method=seed.HASH_METHOD), g.user["id"]))
                db.commit()
                flash("Password changed.", "ok")
        return redirect(url_for("settings"))
    return render_template("settings.html")


# ------------------------------------------------------------------ staff (faculty + admin)
staff_only = role_required("faculty", "admin")


@app.route("/staff")
@staff_only
def staff_overview():
    db = dbm.get_db()
    rows = all_rows()
    n = len(rows) or 1
    seg = {}
    for r in rows:
        seg[r["m"]["segment"]] = seg.get(r["m"]["segment"], 0) + 1
    order = ["Star Performers", "Steady Progress", "Needs a Nudge", "At Risk"]
    risky = sorted([r for r in rows if r["m"]["risk"] == "high"], key=lambda r: r["m"]["success"])[:6]
    stats = {"students": len(rows), "avg": round(sum(r["m"]["success"] for r in rows) / n, 1),
             "att": round(sum(r["m"]["att_overall"] for r in rows) / n, 1),
             "high": sum(1 for r in rows if r["m"]["risk"] == "high"),
             "open_iv": db.execute("SELECT COUNT(*) c FROM interventions WHERE status!='done'").fetchone()["c"]}
    recent = db.execute("SELECT a.applied_at, u.name uname, e.title FROM applications a JOIN users u ON u.id=a.student_id "
                        "JOIN events e ON e.id=a.event_id ORDER BY a.id DESC LIMIT 5").fetchall()
    logs = db.execute("SELECT * FROM import_log ORDER BY id DESC LIMIT 4").fetchall() if g.user["role"] == "admin" else []
    return render_template("staff_overview.html", stats=stats, risky=risky, recent=recent, logs=logs,
                           chart={"labels": order, "vals": [seg.get(s, 0) for s in order]})


@app.route("/staff/students")
@staff_only
def staff_students():
    risk, qtext = request.args.get("risk", ""), request.args.get("q", "").strip().lower()
    rows = all_rows()
    if risk:
        rows = [r for r in rows if r["m"]["risk"] == risk]
    if qtext:
        rows = [r for r in rows if qtext in r["u"]["name"].lower() or qtext in (r["u"]["roll_no"] or "").lower()]
    return render_template("staff_students.html", rows=sorted(rows, key=lambda r: r["m"]["success"]), risk=risk, q=qtext)


@app.route("/staff/students/<int:sid>")
@staff_only
def staff_student(sid):
    db = dbm.get_db()
    s = db.execute("SELECT * FROM users WHERE id=? AND role='student'", (sid,)).fetchone()
    if not s:
        abort(404)
    m = scoring.student_metrics(db, sid)
    iv = db.execute("SELECT i.*, u.name AS by_name FROM interventions i LEFT JOIN users u ON u.id=i.created_by "
                    "WHERE student_id=? ORDER BY i.id DESC", (sid,)).fetchall()
    return render_template("staff_student.html", s=s, m=m, iv=iv)


@app.route("/staff/students/<int:sid>/intervention", methods=["POST"])
@staff_only
def staff_add_intervention(sid):
    action = request.form.get("action", "").strip()
    if action:
        dbm.ex("INSERT INTO interventions(student_id,created_by,action,status,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
               (sid, g.user["id"], action, "open", request.form.get("notes", "").strip(), now(), now()))
        flash("Intervention logged.", "ok")
    return redirect(url_for("staff_student", sid=sid))


@app.route("/staff/students/<int:sid>/feedback", methods=["POST"])
@staff_only
def staff_add_feedback(sid):
    comment = request.form.get("comment", "").strip()
    rating = int(request.form.get("rating", 3))
    if comment and 1 <= rating <= 5:
        dbm.ex("INSERT INTO feedback(student_id,from_name,comment,rating,created_at) VALUES(?,?,?,?,?)",
               (sid, g.user["name"], comment, rating, date.today().isoformat()))
        flash("Feedback saved.", "ok")
    return redirect(url_for("staff_student", sid=sid))


@app.route("/staff/interventions", methods=["GET", "POST"])
@staff_only
def staff_interventions():
    db = dbm.get_db()
    if request.method == "POST":
        status = request.form.get("status")
        if status in ("open", "in_progress", "done"):
            db.execute("UPDATE interventions SET status=?, updated_at=? WHERE id=?",
                       (status, now(), request.form.get("id")))
            db.commit()
        return redirect(url_for("staff_interventions", status=request.args.get("status", "")))
    flt = request.args.get("status", "")
    rows = db.execute("SELECT i.*, u.name AS sname, u.roll_no FROM interventions i JOIN users u ON u.id=i.student_id "
                      "WHERE (?='' OR i.status=?) ORDER BY i.id DESC", (flt, flt)).fetchall()
    counts = {r["status"]: r["c"] for r in db.execute("SELECT status, COUNT(*) c FROM interventions GROUP BY status")}
    return render_template("staff_interventions.html", rows=rows, flt=flt, counts=counts)


@app.route("/staff/tests")
@staff_only
def staff_tests():
    rows = dbm.get_db().execute(
        "SELECT t.*, u.name AS author, (SELECT COUNT(*) FROM questions WHERE test_id=t.id) qn, "
        "(SELECT COUNT(*) FROM problems WHERE test_id=t.id) pn, "
        "(SELECT COUNT(DISTINCT student_id) FROM attempts WHERE test_id=t.id) + "
        "(SELECT COUNT(DISTINCT cb.student_id) FROM code_best cb JOIN problems p ON p.id=cb.problem_id WHERE p.test_id=t.id) AS takers "
        "FROM tests t LEFT JOIN users u ON u.id=t.created_by ORDER BY t.id DESC").fetchall()
    return render_template("staff_tests.html", rows=rows)


@app.route("/staff/tests/new", methods=["GET", "POST"])
@staff_only
def staff_test_new():
    if request.method == "POST":
        f = request.form
        kind, title = f.get("kind"), f.get("title", "").strip()
        if not title or kind not in ("mcq", "coding"):
            flash("Please enter a title and choose a test type.", "error")
            return render_template("staff_test_new.html", langs=LANG_LABELS, subjects=bank.SUBJECTS, form=f)
        db = dbm.get_db()
        lang = f.get("language") if kind == "coding" else None
        items = []
        if kind == "mcq":
            for ln in f.get("mcq_text", "").splitlines():
                parts = [x.strip() for x in ln.split("|")]
                if len(parts) == 6 and parts[5].upper() in "ABCD" and parts[5]:
                    items.append((parts[0], parts[1:5], "ABCD".index(parts[5].upper())))
            if not items:
                flash("Add at least one question in the format: Question | A | B | C | D | correct letter", "error")
                return render_template("staff_test_new.html", langs=LANG_LABELS, subjects=bank.SUBJECTS, form=f)
        else:
            titles, stmts = f.getlist("p_title"), f.getlist("p_statement")
            ins, outs, starters = f.getlist("p_inputs"), f.getlist("p_outputs"), f.getlist("p_starter")
            for i, ptitle in enumerate(titles):
                if not ptitle.strip():
                    continue
                cin = [c.strip("\n") for c in ins[i].replace("\r", "").split("\n---\n")]
                cout = [c.strip("\n") for c in outs[i].replace("\r", "").split("\n---\n")]
                cases = [{"in": a, "out": b, "hidden": n > 0} for n, (a, b) in enumerate(zip(cin, cout))]
                if cases:
                    items.append((ptitle.strip(), stmts[i].strip(), starters[i], cases))
            if not items:
                flash("Add at least one coding problem with test cases.", "error")
                return render_template("staff_test_new.html", langs=LANG_LABELS, subjects=bank.SUBJECTS, form=f)
        tid = db.execute("INSERT INTO tests(title,kind,subject,language,duration,created_by,created_at,due_date) VALUES(?,?,?,?,?,?,?,?)",
                         (title, kind, f.get("subject") or "Coding", lang, int(f.get("duration") or 30), g.user["id"], now(),
                          f.get("due_date") or "")).lastrowid
        for it in items:
            if kind == "mcq":
                db.execute("INSERT INTO questions(test_id,prompt,options,answer,points) VALUES(?,?,?,?,1)",
                           (tid, it[0], json.dumps(it[1]), it[2]))
            else:
                db.execute("INSERT INTO problems(test_id,title,statement,starter,cases,points) VALUES(?,?,?,?,?,10)",
                           (tid, it[0], it[1], it[2], json.dumps(it[3])))
        db.commit()
        flash("Test posted. Students can see it right away.", "ok")
        return redirect(url_for("staff_tests"))
    return render_template("staff_test_new.html", langs=LANG_LABELS, subjects=bank.SUBJECTS, form={})


@app.route("/staff/tests/<int:tid>")
@staff_only
def staff_test_results(tid):
    db = dbm.get_db()
    t = db.execute("SELECT * FROM tests WHERE id=?", (tid,)).fetchone()
    if not t:
        abort(404)
    if t["kind"] == "mcq":
        rows = db.execute("SELECT u.name, u.roll_no, MAX(a.score) s, MAX(a.max_score) mx, COUNT(*) n, MAX(a.submitted_at) at_ "
                          "FROM attempts a JOIN users u ON u.id=a.student_id WHERE a.test_id=? GROUP BY u.id ORDER BY s DESC", (tid,)).fetchall()
    else:
        rows = db.execute("SELECT u.name, u.roll_no, SUM(cb.score) s, (SELECT SUM(points) FROM problems WHERE test_id=?) mx, "
                          "COUNT(*) n, MAX(cb.updated_at) at_ FROM code_best cb JOIN problems p ON p.id=cb.problem_id "
                          "JOIN users u ON u.id=cb.student_id WHERE p.test_id=? GROUP BY u.id ORDER BY s DESC", (tid, tid)).fetchall()
    return render_template("staff_test_results.html", t=t, rows=rows)


@app.route("/staff/tests/<int:tid>/delete", methods=["POST"])
@staff_only
def staff_test_delete(tid):
    db = dbm.get_db()
    db.execute("DELETE FROM code_best WHERE problem_id IN (SELECT id FROM problems WHERE test_id=?)", (tid,))
    for tbl in ("questions", "problems", "attempts"):
        db.execute(f"DELETE FROM {tbl} WHERE test_id=?", (tid,))
    db.execute("DELETE FROM tests WHERE id=?", (tid,))
    db.commit()
    flash("Test removed.", "ok")
    return redirect(url_for("staff_tests"))


@app.route("/staff/events", methods=["GET", "POST"])
@staff_only
def staff_events():
    db = dbm.get_db()
    if request.method == "POST":
        f = request.form
        if f.get("title", "").strip() and f.get("event_date"):
            db.execute("INSERT INTO events(title,kind,description,event_date,location,posted_by,created_at) VALUES(?,?,?,?,?,?,?)",
                       (f["title"].strip(), f.get("kind") if f.get("kind") in EVENT_KINDS else "event", f.get("description", "").strip(),
                        f["event_date"], f.get("location", "").strip(), g.user["id"], now()))
            db.commit()
            flash("Event posted. Students can apply now.", "ok")
        else:
            flash("Title and date are required.", "error")
        return redirect(url_for("staff_events"))
    rows = db.execute("SELECT e.*, (SELECT COUNT(*) FROM applications WHERE event_id=e.id) AS n_apps FROM events e "
                      "ORDER BY e.event_date DESC").fetchall()
    return render_template("staff_events.html", rows=rows, kinds=EVENT_KINDS, today=date.today().isoformat())


@app.route("/staff/events/<int:eid>", methods=["GET", "POST"])
@staff_only
def staff_event(eid):
    db = dbm.get_db()
    e = db.execute("SELECT * FROM events WHERE id=?", (eid,)).fetchone()
    if not e:
        abort(404)
    if request.method == "POST":
        if request.form.get("delete"):
            db.execute("DELETE FROM applications WHERE event_id=?", (eid,))
            db.execute("DELETE FROM events WHERE id=?", (eid,))
            db.commit()
            flash("Event deleted.", "ok")
            return redirect(url_for("staff_events"))
        if request.form.get("app_id") and request.form.get("status") in ("applied", "attended"):
            db.execute("UPDATE applications SET status=? WHERE id=? AND event_id=?",
                       (request.form["status"], request.form["app_id"], eid))
            db.commit()
        return redirect(url_for("staff_event", eid=eid))
    apps = db.execute("SELECT a.*, u.name, u.roll_no FROM applications a JOIN users u ON u.id=a.student_id "
                      "WHERE a.event_id=? ORDER BY a.id", (eid,)).fetchall()
    return render_template("staff_event.html", e=e, apps=apps)


@app.route("/staff/reports")
@staff_only
def staff_reports():
    db = dbm.get_db()
    rows = all_rows()
    seg, risk = {}, {"high": 0, "medium": 0, "low": 0}
    for r in rows:
        seg[r["m"]["segment"]] = seg.get(r["m"]["segment"], 0) + 1
        risk[r["m"]["risk"]] += 1
    iv = {r["status"]: r["c"] for r in db.execute("SELECT status, COUNT(*) c FROM interventions GROUP BY status")}
    total_iv = sum(iv.values()) or 1
    comp = {}
    for key, label in scoring.LABELS.items():
        comp[label] = round(sum(next(c["score"] for c in r["m"]["components"] if c["key"] == key) for r in rows) / (len(rows) or 1), 1)
    return render_template("staff_reports.html", rows=rows, seg=seg, risk=risk, iv=iv,
                           resolved=round(100 * iv.get("done", 0) / total_iv), comp=comp,
                           chart={"labels": list(comp.keys()), "vals": list(comp.values())})


@app.route("/staff/reports/export.csv")
@staff_only
def staff_export():
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["roll_no", "name", "success_score", "risk", "segment", "academics", "attendance", "lms",
                "placement", "engagement", "skills", "backlogs"])
    for r in all_rows():
        c = {x["key"]: x["score"] for x in r["m"]["components"]}
        w.writerow([r["u"]["roll_no"], r["u"]["name"], r["m"]["success"], r["m"]["risk"], r["m"]["segment"],
                    c["academics"], c["attendance"], c["lms"], c["placement"], c["engagement"], c["skills"], len(r["m"]["backlogs"])])
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=campus_success_report.csv"})


# ------------------------------------------------------------------ admin
admin_only = role_required("admin")


@app.route("/admin/integration", methods=["GET", "POST"])
@admin_only
def admin_integration():
    db = dbm.get_db()
    result = None
    if request.method == "POST":
        ds = request.form.get("dataset")
        if ds not in importer.SPECS:
            abort(400)
        f = request.files.get("file")
        text = f.read().decode("utf-8-sig", errors="replace") if f and f.filename else request.form.get("pasted", "")
        if not text.strip():
            flash("Upload a CSV file or paste CSV text.", "error")
        else:
            ok, errs = importer.import_csv(db, ds, text, g.user["name"])
            result = {"dataset": importer.SPECS[ds]["label"], "ok": ok, "errors": errs[:10], "n_err": len(errs)}
    counts = {
        "academic": db.execute("SELECT COUNT(*) c FROM marks").fetchone()["c"],
        "attendance": db.execute("SELECT COUNT(*) c FROM attendance").fetchone()["c"],
        "lms": db.execute("SELECT COUNT(*) c FROM lms").fetchone()["c"],
        "engagement": db.execute("SELECT COUNT(*) c FROM applications").fetchone()["c"],
        "placement": db.execute("SELECT COUNT(*) c FROM placement").fetchone()["c"],
        "skills": db.execute("SELECT COUNT(*) c FROM skills").fetchone()["c"],
        "feedback": db.execute("SELECT COUNT(*) c FROM feedback").fetchone()["c"],
    }
    last = {r["dataset"]: r["created_at"] for r in db.execute("SELECT dataset, MAX(created_at) created_at FROM import_log GROUP BY dataset")}
    logs = db.execute("SELECT * FROM import_log ORDER BY id DESC LIMIT 6").fetchall()
    return render_template("admin_integration.html", specs=importer.SPECS, counts=counts, last=last, logs=logs, result=result)


@app.route("/admin/integration/<dataset>/template.csv")
@admin_only
def admin_template(dataset):
    if dataset not in importer.SPECS:
        abort(404)
    return Response(importer.template_csv(dataset), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={dataset}_template.csv"})


@app.route("/admin/users", methods=["GET", "POST"])
@admin_only
def admin_users():
    db = dbm.get_db()
    if request.method == "POST":
        f = request.form
        try:
            if f.get("role") not in ("student", "faculty", "admin") or len(f.get("password", "")) < 6:
                raise ValueError("Pick a role and use a password of at least 6 characters.")
            db.execute("INSERT INTO users(name,email,password_hash,role,department,year,roll_no) VALUES(?,?,?,?,?,?,?)",
                       (f["name"].strip(), f["email"].strip().lower(), generate_password_hash(f["password"], method=seed.HASH_METHOD),
                        f["role"], f.get("department", "CSE"), int(f["year"]) if f.get("year") else None, f.get("roll_no") or None))
            db.commit()
            flash("User created.", "ok")
        except Exception as exc:  # noqa: BLE001
            flash(f"Could not create user: {exc}", "error")
        return redirect(url_for("admin_users"))
    users = db.execute("SELECT * FROM users ORDER BY CASE role WHEN 'admin' THEN 0 WHEN 'faculty' THEN 1 ELSE 2 END, name").fetchall()
    return render_template("admin_users.html", users=users)


@app.errorhandler(403)
def forbidden(_e):
    return render_template("error.html", code=403, msg="You don't have access to this page."), 403


@app.errorhandler(404)
def not_found(_e):
    return render_template("error.html", code=404, msg="That page drifted out of orbit."), 404


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
