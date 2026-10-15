"""Student Success Score, risk detection, segmentation, study plans."""
import math
from collections import OrderedDict
from urllib.parse import quote_plus

WEIGHTS = OrderedDict([
    ("academics", 30), ("attendance", 20), ("lms", 15),
    ("placement", 15), ("engagement", 10), ("skills", 10),
])
LABELS = {
    "academics": "Academics", "attendance": "Attendance", "lms": "Learning (LMS)",
    "placement": "Placement readiness", "engagement": "Engagement", "skills": "Skills & feedback",
}
TOPICS = {
    "Mathematics": ["Differentiation rules", "Matrices and determinants", "Probability basics", "Integration techniques"],
    "Data Structures": ["Linked lists", "Stacks and queues", "Binary search trees", "Graph BFS and DFS"],
    "DBMS": ["SQL joins", "Normalization 1NF 2NF 3NF", "Transactions and ACID", "Indexing in databases"],
    "Operating Systems": ["CPU scheduling algorithms", "Deadlock handling", "Paging and virtual memory", "Process synchronization"],
    "Python Programming": ["Python lists and dictionaries", "Functions and recursion", "File handling in Python", "Object oriented Python"],
    "Computer Networks": ["OSI model", "TCP vs UDP", "IP addressing and subnetting", "DNS and HTTP"],
}
SUGGESTED_SKILLS = ["Python", "SQL", "Git & GitHub", "Problem Solving", "Communication", "Teamwork",
                    "Web Development", "Data Structures", "Java", "Cloud Basics"]


def _pct(a, b):
    return round(100.0 * a / b, 1) if b else 0.0


def yt(topic):
    return "https://www.youtube.com/results?search_query=" + quote_plus(topic + " tutorial")


def student_metrics(db, sid):
    # ---------- academics
    rows = db.execute(
        "SELECT m.score, m.max_score, m.exam, m.exam_order, s.name AS sname FROM marks m "
        "JOIN subjects s ON s.id=m.subject_id WHERE m.student_id=? ORDER BY m.exam_order, s.id", (sid,)).fetchall()
    by, exams = OrderedDict(), []
    for r in rows:
        by.setdefault(r["sname"], []).append(_pct(r["score"], r["max_score"]))
        if r["exam"] not in exams:
            exams.append(r["exam"])
    subjects = []
    for name, p in by.items():
        latest, avg = p[-1], round(sum(p) / len(p), 1)
        subjects.append({"name": name, "latest": latest, "avg": avg, "trend": p,
                         "blend": round(.6 * latest + .4 * avg, 1)})
    marks_pct = round(sum(s["blend"] for s in subjects) / len(subjects), 1) if subjects else 0.0
    backlogs = [s for s in subjects if s["latest"] < 40]
    exam_avgs = []
    for i in range(len(exams)):
        vals = [s["trend"][i] for s in subjects if i < len(s["trend"])]
        exam_avgs.append(round(sum(vals) / len(vals), 1) if vals else 0)

    mq = db.execute(
        "SELECT t.id, t.title, MAX(100.0*a.score/a.max_score) AS p FROM attempts a "
        "JOIN tests t ON t.id=a.test_id WHERE a.student_id=? AND a.max_score>0 GROUP BY t.id", (sid,)).fetchall()
    mcq_pct = round(sum(r["p"] for r in mq) / len(mq), 1) if mq else None
    academics = round(.85 * marks_pct + .15 * mcq_pct, 1) if mcq_pct is not None else marks_pct

    # ---------- attendance
    att = []
    for r in db.execute("SELECT a.attended, a.total, s.name FROM attendance a JOIN subjects s ON s.id=a.subject_id "
                        "WHERE a.student_id=? ORDER BY s.id", (sid,)):
        p = _pct(r["attended"], r["total"])
        need = max(0, math.ceil((0.75 * r["total"] - r["attended"]) / 0.25)) if p < 75 else 0
        can_miss = max(0, int((r["attended"] - 0.75 * r["total"]) / 0.75)) if p >= 75 else 0
        att.append({"name": r["name"], "attended": r["attended"], "total": r["total"], "pct": p,
                    "need": need, "can_miss": can_miss})
    att_overall = _pct(sum(a["attended"] for a in att), sum(a["total"] for a in att))

    # ---------- LMS
    lms_rows = [dict(r) for r in db.execute("SELECT * FROM lms WHERE student_id=?", (sid,))]
    vw, vt = sum(r["videos_watched"] for r in lms_rows), sum(r["videos_total"] for r in lms_rows)
    ad, at = sum(r["assignments_done"] for r in lms_rows), sum(r["assignments_total"] for r in lms_rows)
    hours = round(sum(r["hours_week"] for r in lms_rows), 1)
    video_pct, assign_pct = _pct(vw, vt), _pct(ad, at)
    lms_score = round(.4 * video_pct + .5 * assign_pct + .1 * min(100, hours / 8 * 100), 1) if lms_rows else 0.0

    # ---------- engagement
    eng = [dict(r) for r in db.execute(
        "SELECT a.status, e.kind, e.title, e.event_date, e.id AS eid FROM applications a "
        "JOIN events e ON e.id=a.event_id WHERE a.student_id=? ORDER BY e.event_date DESC", (sid,))]
    attended = sum(1 for e in eng if e["status"] == "attended")
    applied = sum(1 for e in eng if e["status"] == "applied")
    eng_score = float(min(100, attended * 22 + applied * 8))
    by_kind = {}
    for e in eng:
        by_kind[e["kind"]] = by_kind.get(e["kind"], 0) + 1

    # ---------- placement (coding practice boosts coding readiness)
    pl = db.execute("SELECT * FROM placement WHERE student_id=?", (sid,)).fetchone()
    base = dict(pl) if pl else {"aptitude": 0, "coding": 0, "communication": 0, "mock_interview": 0, "mock_count": 0}
    cb = db.execute("SELECT COALESCE(SUM(score),0) AS s, COALESCE(SUM(passed),0) AS p, COUNT(*) AS n, "
                    "SUM(CASE WHEN passed=total AND total>0 THEN 1 ELSE 0 END) AS solved "
                    "FROM code_best WHERE student_id=?", (sid,)).fetchone()
    solved = cb["solved"] or 0
    coding_bonus = round(min(20.0, (cb["s"] or 0) / 2.0), 1)
    coding = round(min(100.0, base["coding"] + coding_bonus), 1)
    placement_score = round(.30 * base["aptitude"] + .35 * coding + .20 * base["communication"]
                            + .15 * base["mock_interview"], 1)
    placement = {"aptitude": base["aptitude"], "coding": coding, "coding_base": base["coding"],
                 "coding_bonus": coding_bonus, "solved": solved, "communication": base["communication"],
                 "mock_interview": base["mock_interview"], "mock_count": base["mock_count"],
                 "score": placement_score}

    # ---------- skills & feedback
    skills = [dict(r) for r in db.execute("SELECT skill, level FROM skills WHERE student_id=? ORDER BY level DESC", (sid,))]
    fb = [dict(r) for r in db.execute("SELECT * FROM feedback WHERE student_id=? ORDER BY id DESC", (sid,))]
    skill_pct = round(sum(s["level"] for s in skills) / (5 * len(skills)) * 100, 1) if skills else 0.0
    fb_pct = round(sum(f["rating"] for f in fb) / (5 * len(fb)) * 100, 1) if fb else skill_pct
    skills_score = round(.6 * skill_pct + .4 * fb_pct, 1)

    scores = {"academics": academics, "attendance": att_overall, "lms": lms_score,
              "placement": placement_score, "engagement": eng_score, "skills": skills_score}
    weakest = sorted(subjects, key=lambda s: s["latest"])[:1]
    notes = {
        "academics": f"Blend of latest and average marks across {len(subjects)} subjects"
                     + (f"; weakest is {weakest[0]['name']} at {weakest[0]['latest']:.0f}%." if weakest else "."),
        "attendance": f"{sum(a['attended'] for a in att)} of {sum(a['total'] for a in att)} classes attended; 75% is the minimum.",
        "lms": f"{video_pct:.0f}% videos watched, {assign_pct:.0f}% assignments done, {hours} study hrs/week.",
        "placement": f"Aptitude {base['aptitude']:.0f}, coding {coding:.0f}, communication {base['communication']:.0f}, mock interviews {base['mock_interview']:.0f}.",
        "engagement": f"{attended} activities attended and {applied} applied; each attended activity adds 22 points.",
        "skills": f"Average skill level {skill_pct:.0f}% combined with faculty feedback {fb_pct:.0f}%.",
    }
    components = []
    for key, w in WEIGHTS.items():
        s = scores[key]
        components.append({"key": key, "label": LABELS[key], "score": round(s, 1), "weight": w,
                           "points": round(s * w / 100, 1),
                           "gain": round(w * max(0, 80 - s) / 100, 1), "note": notes[key]})
    success = round(sum(c["points"] for c in components), 1)

    # ---------- risk
    reasons = []
    if att and att_overall < 75:
        reasons.append(f"Attendance is {att_overall:.0f}%, below the 75% minimum")
    if backlogs:
        reasons.append(f"{len(backlogs)} subject(s) below pass mark: " + ", ".join(b["name"] for b in backlogs))
    if lms_rows and assign_pct < 50:
        reasons.append(f"Only {assign_pct:.0f}% of LMS assignments completed")
    if len(exam_avgs) >= 2 and exam_avgs[-1] < exam_avgs[0] - 8:
        reasons.append("Marks are trending downward across exams")
    if placement_score < 45:
        reasons.append("Placement readiness is low")
    if success < 55:
        reasons.append(f"Overall success score is low ({success:.0f})")
    risk = "high" if (success < 55 or len(reasons) >= 3) else ("medium" if (success < 70 or reasons) else "low")
    segment = ("Star Performers" if success >= 82 else "Steady Progress" if success >= 68
               else "Needs a Nudge" if success >= 55 else "At Risk")

    return {
        "success": success, "components": components, "risk": risk, "segment": segment, "reasons": reasons,
        "subjects": subjects, "exams": exams, "exam_avgs": exam_avgs, "marks_pct": marks_pct,
        "academics": academics, "backlogs": backlogs, "mcq": [dict(r) for r in mq], "mcq_pct": mcq_pct,
        "attendance": att, "att_overall": att_overall,
        "lms": lms_rows, "video_pct": video_pct, "assign_pct": assign_pct, "hours": hours,
        "pending_assignments": at - ad,
        "engagement": eng, "eng_by_kind": by_kind, "attended": attended, "applied": applied,
        "placement": placement, "skills": skills, "feedback": fb,
        "skill_pct": skill_pct, "feedback_pct": fb_pct,
    }


def study_plan(m):
    subs = sorted(m["subjects"], key=lambda s: s["latest"])
    if not subs:
        return []
    w = (subs + subs + subs)[:3]
    topics = [TOPICS.get(s["name"], ["Core concepts"]) for s in w]

    def pick(i, k):
        t = topics[i]
        return t[k % len(t)]
    plan = [
        ("Mon", f"{w[0]['name']}: concept revision", f"Study '{pick(0, 0)}' for 60 min, then write a one-page summary.", pick(0, 0)),
        ("Tue", f"{w[1]['name']}: concept revision", f"Study '{pick(1, 0)}' for 60 min and solve 5 textbook problems.", pick(1, 0)),
        ("Wed", f"{w[0]['name']}: practice", "Ask the AI Copilot for fresh practice questions and aim for 4/5.", None),
        ("Thu", f"{w[2]['name']}: concept revision", f"Study '{pick(2, 0)}' for 45 min and note down doubts for faculty.", pick(2, 0)),
        ("Fri", "Coding practice", "Solve 2 problems in the Coding Exams section (45 min). Each solved problem raises your coding readiness.", None),
        ("Sat", f"{w[1]['name']}: timed quiz", f"Take a quiz on {w[1]['name']} in Tests, then review every wrong answer.", None),
        ("Sun", "Review and rest", f"Revisit weak points in {w[0]['name']}, plan the next week, and rest well.", pick(0, 1)),
    ]
    return [{"day": d, "title": t, "detail": de, "link": yt(tp) if tp else None} for d, t, de, tp in plan]


def resources(m, limit=6):
    out = []
    for s in sorted(m["subjects"], key=lambda s: s["latest"])[:3]:
        for t in TOPICS.get(s["name"], [])[:2]:
            out.append({"subject": s["name"], "title": t, "url": yt(t), "score": s["latest"]})
    return out[:limit]


def suggestions(m, pending_tests=0, open_events=0):
    items = []
    if m["attendance"] and m["att_overall"] < 75:
        worst = min(m["attendance"], key=lambda a: a["pct"])
        items.append(("Attendance", f"Attend the next {worst['need']} {worst['name']} classes to reach 75%."))
    if m["subjects"]:
        w = min(m["subjects"], key=lambda s: s["latest"])
        if w["latest"] < 65:
            items.append(("Academics", f"{w['name']} is your weakest subject ({w['latest']:.0f}%). Follow the study plan and try 5 practice questions."))
    if m["placement"]["solved"] < 3:
        items.append(("Coding", "Solve a few Coding Exam problems. Each fully solved problem adds +5 to coding readiness."))
    if m["pending_assignments"] > 0:
        items.append(("LMS", f"You have {m['pending_assignments']} pending assignments. Finish the oldest first."))
    if pending_tests:
        items.append(("Tests", f"{pending_tests} test(s) are waiting for you."))
    if open_events:
        items.append(("Engagement", f"{open_events} upcoming event(s) are open for applications."))
    if not items:
        items.append(("Great work", "You are on track. Keep the streak going and try a hackathon this month."))
    return items[:5]
