"""CSV data integration for the admin Data Integration page."""
import csv
import io
from datetime import datetime

SPECS = {
    "academic": {"label": "Academic marks", "cols": ["roll_no", "subject", "exam", "exam_order", "score", "max_score"],
                 "sample": [["CG23001", "Mathematics", "Internal 1", "1", "72", "100"]]},
    "attendance": {"label": "Attendance", "cols": ["roll_no", "subject", "attended", "total"],
                   "sample": [["CG23001", "Mathematics", "52", "60"]]},
    "lms": {"label": "LMS activity", "cols": ["roll_no", "course", "videos_watched", "videos_total", "assignments_done", "assignments_total", "hours_week"],
            "sample": [["CG23001", "Python Programming", "20", "24", "7", "8", "5.5"]]},
    "engagement": {"label": "Engagement", "cols": ["roll_no", "event_title", "kind", "status"],
                   "sample": [["CG23001", "Galaxy Hack 2026", "hackathon", "applied"]]},
    "placement": {"label": "Placement readiness", "cols": ["roll_no", "aptitude", "coding", "communication", "mock_interview", "mock_count"],
                  "sample": [["CG23001", "70", "65", "72", "60", "2"]]},
    "skills": {"label": "Skills", "cols": ["roll_no", "skill", "level"], "sample": [["CG23001", "Python", "4"]]},
    "feedback": {"label": "Faculty feedback", "cols": ["roll_no", "from_name", "comment", "rating"],
                 "sample": [["CG23001", "Dr. Sunita Rao", "Good progress this month.", "4"]]},
}


def template_csv(dataset):
    spec = SPECS[dataset]
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(spec["cols"])
    w.writerows(spec["sample"])
    return out.getvalue()


def _sid(db, roll):
    r = db.execute("SELECT id FROM users WHERE roll_no=? AND role='student'", (roll,)).fetchone()
    if not r:
        raise ValueError(f"unknown roll_no '{roll}'")
    return r["id"]


def _subject(db, name):
    r = db.execute("SELECT id FROM subjects WHERE name=?", (name,)).fetchone()
    return r["id"] if r else db.execute("INSERT INTO subjects(name) VALUES(?)", (name,)).lastrowid


def import_csv(db, dataset, text, by_name):
    spec = SPECS[dataset]
    reader = csv.DictReader(io.StringIO(text))
    missing = [c for c in spec["cols"] if c not in (reader.fieldnames or [])]
    if missing:
        return 0, [f"Missing columns: {', '.join(missing)}"]
    ok, errors = 0, []
    for n, row in enumerate(reader, start=2):
        try:
            row = {k: (v or "").strip() for k, v in row.items()}
            sid = _sid(db, row["roll_no"])
            if dataset == "academic":
                sub = _subject(db, row["subject"])
                db.execute("DELETE FROM marks WHERE student_id=? AND subject_id=? AND exam=?", (sid, sub, row["exam"]))
                db.execute("INSERT INTO marks(student_id,subject_id,exam,exam_order,score,max_score) VALUES(?,?,?,?,?,?)",
                           (sid, sub, row["exam"], int(row["exam_order"]), float(row["score"]), float(row["max_score"])))
            elif dataset == "attendance":
                sub = _subject(db, row["subject"])
                a, t = int(row["attended"]), int(row["total"])
                if a > t:
                    raise ValueError("attended is greater than total")
                db.execute("DELETE FROM attendance WHERE student_id=? AND subject_id=?", (sid, sub))
                db.execute("INSERT INTO attendance(student_id,subject_id,attended,total) VALUES(?,?,?,?)", (sid, sub, a, t))
            elif dataset == "lms":
                db.execute("DELETE FROM lms WHERE student_id=? AND course=?", (sid, row["course"]))
                db.execute("INSERT INTO lms(student_id,course,videos_watched,videos_total,assignments_done,assignments_total,hours_week) VALUES(?,?,?,?,?,?,?)",
                           (sid, row["course"], int(row["videos_watched"]), int(row["videos_total"]),
                            int(row["assignments_done"]), int(row["assignments_total"]), float(row["hours_week"])))
            elif dataset == "engagement":
                ev = db.execute("SELECT id FROM events WHERE title=?", (row["event_title"],)).fetchone()
                eid = ev["id"] if ev else db.execute(
                    "INSERT INTO events(title,kind,description,event_date,location,created_at) VALUES(?,?,?,?,?,?)",
                    (row["event_title"], row["kind"] or "event", "Imported record", datetime.now().strftime("%Y-%m-%d"), "", datetime.now().strftime("%Y-%m-%d %H:%M"))).lastrowid
                status = row["status"] if row["status"] in ("applied", "attended") else "applied"
                db.execute("INSERT INTO applications(event_id,student_id,status,applied_at) VALUES(?,?,?,?) "
                           "ON CONFLICT(event_id,student_id) DO UPDATE SET status=excluded.status",
                           (eid, sid, status, datetime.now().strftime("%Y-%m-%d")))
            elif dataset == "placement":
                db.execute("INSERT OR REPLACE INTO placement VALUES(?,?,?,?,?,?)",
                           (sid, float(row["aptitude"]), float(row["coding"]), float(row["communication"]),
                            float(row["mock_interview"]), int(row["mock_count"])))
            elif dataset == "skills":
                lvl = int(row["level"])
                if not 1 <= lvl <= 5:
                    raise ValueError("level must be 1-5")
                db.execute("DELETE FROM skills WHERE student_id=? AND skill=?", (sid, row["skill"]))
                db.execute("INSERT INTO skills(student_id,skill,level) VALUES(?,?,?)", (sid, row["skill"], lvl))
            elif dataset == "feedback":
                r = int(row["rating"])
                if not 1 <= r <= 5:
                    raise ValueError("rating must be 1-5")
                db.execute("INSERT INTO feedback(student_id,from_name,comment,rating,created_at) VALUES(?,?,?,?,?)",
                           (sid, row["from_name"], row["comment"], r, datetime.now().strftime("%Y-%m-%d")))
            ok += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Row {n}: {exc}")
    db.execute("INSERT INTO import_log(dataset,rows_ok,rows_err,created_at,by_name) VALUES(?,?,?,?,?)",
               (dataset, ok, len(errors), datetime.now().strftime("%Y-%m-%d %H:%M"), by_name))
    db.commit()
    return ok, errors
