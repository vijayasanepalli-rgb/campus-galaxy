"""Demo data so the app is fully usable on first launch."""
import json
import random
from datetime import date, datetime, timedelta

from werkzeug.security import generate_password_hash

import bank

HASH_METHOD = "pbkdf2:sha256:60000"

NAMES = [
    "Aarav Sharma", "Ananya Reddy", "Rohan Mehta", "Sneha Iyer", "Karthik Nair", "Priya Das",
    "Vikram Singh", "Ishita Gupta", "Arjun Rao", "Divya Menon", "Rahul Verma", "Neha Kapoor",
    "Siddharth Jain", "Pooja Bhat", "Aditya Kulkarni", "Meera Pillai", "Harsh Vardhan", "Kavya Shetty",
    "Manish Yadav", "Lakshmi Prasad", "Naveen Kumar", "Tanvi Joshi", "Varun Chandra", "Swathi Reddy",
]
ARCH = ["good", "star", "avg", "atrisk", "good", "avg", "weak", "star", "avg", "good", "atrisk", "avg"]
Q = {"star": .90, "good": .78, "avg": .66, "weak": .54, "atrisk": .42}
TREND = {"star": 2, "good": 1, "avg": 0, "weak": -2, "atrisk": -5}
EXAMS = ["Internal 1", "Internal 2", "Midterm"]
ALL_SKILLS = ["Python", "SQL", "Git & GitHub", "Problem Solving", "Communication", "Teamwork",
              "Web Development", "Data Structures", "Java", "Cloud Basics"]
COMMENTS = {
    5: "Outstanding participation and consistent work. A role model for the class.",
    4: "Good progress. Keep pushing on problem solving and contest practice.",
    3: "Average performance. Needs more regular practice and revision.",
    2: "Struggling with fundamentals. Please attend the extra sessions.",
    1: "Very low engagement. Urgent mentoring required.",
}

TODAY = date.today()


def _d(offset):
    return (TODAY + timedelta(days=offset)).isoformat()


# dates are relative to today so the demo always has both past and upcoming events
EVENTS = [
    ("Hack the Orbit", "hackathon", "24-hour campus hackathon on student-success tools.", _d(-33), "Innovation Lab"),
    ("Robotics Club Meetup", "club", "Monthly meetup of the robotics club.", _d(-20), "Block C, Room 204"),
    ("Coding Club Weekly Contest", "club", "Weekly 90-minute coding contest with leaderboard.", _d(5), "Computer Lab 2"),
    ("Tech Talk: AI in Campus Placements", "event", "Industry speakers on how AI is changing hiring.", _d(7), "Main Auditorium"),
    ("Python for Data Science Workshop", "workshop", "Hands-on workshop with pandas and charts. Bring a laptop.", _d(10), "Seminar Hall"),
    ("Resume and Mock Interview Bootcamp", "workshop", "Resume reviews and live mock interviews with alumni.", _d(18), "Placement Cell"),
    ("Galaxy Hack", "hackathon", "36-hour hackathon. Teams of 3-4. Prizes for the top 3 teams.", _d(24), "Main Auditorium"),
    ("AWS Cloud Practitioner Certification Drive", "certification", "Subsidised exam vouchers with 4 prep sessions.", _d(31), "Online + Lab 1"),
]

PROBLEMS = [
    {"key": "sum", "title": "Sum of Two Numbers", "statement": "Read two integers a and b on one line. Print a + b.",
     "cases": [("3 4", "7"), ("10 -2", "8"), ("100 250", "350"), ("-5 -6", "-11")]},
    {"key": "rev", "title": "Reverse a String", "statement": "Read one word (no spaces). Print it reversed.",
     "cases": [("hello", "olleh"), ("galaxy", "yxalag"), ("a", "a"), ("racecar", "racecar")]},
    {"key": "fact", "title": "Factorial", "statement": "Read an integer n (0 <= n <= 12). Print n! (n factorial).",
     "cases": [("5", "120"), ("0", "1"), ("10", "3628800"), ("12", "479001600")]},
    {"key": "pal", "title": "Palindrome Check", "statement": "Read a lowercase word. Print YES if it reads the same backwards, otherwise print NO.",
     "cases": [("madam", "YES"), ("galaxy", "NO"), ("level", "YES"), ("ab", "NO")]},
]

C_STR = '#include <stdio.h>\n#include <string.h>\n\nint main() {\n    char s[1001];\n    scanf("%1000s", s);\n    // TODO: @@\n    return 0;\n}\n'
JAVA_HEAD = 'import java.util.*;\n\npublic class Main {\n    public static void main(String[] args) {\n        Scanner sc = new Scanner(System.in);\n'
STARTERS = {
    "python": {
        "sum": "a, b = map(int, input().split())\n# TODO: print the sum\n",
        "rev": "s = input().strip()\n# TODO: print the reversed string\n",
        "fact": "n = int(input())\n# TODO: print n factorial\n",
        "pal": "s = input().strip()\n# TODO: print YES or NO\n",
    },
    "javascript": {
        "sum": "const [a, b] = require('fs').readFileSync(0, 'utf8').trim().split(/\\s+/).map(Number);\n// TODO: console.log the sum\n",
        "rev": "const s = require('fs').readFileSync(0, 'utf8').trim();\n// TODO: console.log the reversed string\n",
        "fact": "const n = parseInt(require('fs').readFileSync(0, 'utf8').trim());\n// TODO: console.log n factorial\n",
        "pal": "const s = require('fs').readFileSync(0, 'utf8').trim();\n// TODO: console.log YES or NO\n",
    },
    "c": {
        "sum": '#include <stdio.h>\n\nint main() {\n    long long a, b;\n    scanf("%lld %lld", &a, &b);\n    // TODO: print the sum\n    return 0;\n}\n',
        "rev": C_STR.replace("@@", "print the reversed string"),
        "fact": '#include <stdio.h>\n\nint main() {\n    int n;\n    scanf("%d", &n);\n    // TODO: print n factorial\n    return 0;\n}\n',
        "pal": C_STR.replace("@@", "print YES or NO"),
    },
    "java": {
        "sum": JAVA_HEAD + "        long a = sc.nextLong(), b = sc.nextLong();\n        // TODO: print the sum\n    }\n}\n",
        "rev": JAVA_HEAD + "        String s = sc.next();\n        // TODO: print the reversed string\n    }\n}\n",
        "fact": JAVA_HEAD + "        int n = sc.nextInt();\n        // TODO: print n factorial\n    }\n}\n",
        "pal": JAVA_HEAD + "        String s = sc.next();\n        // TODO: print YES or NO\n    }\n}\n",
    },
}
LANG_TITLES = {"python": "Python", "javascript": "JavaScript", "c": "C", "java": "Java"}


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def run(db):
    rng = random.Random(11)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    ph = {p: generate_password_hash(p, method=HASH_METHOD) for p in ("student123", "faculty123", "admin123")}

    def add_user(name, email, role, pw, dept="CSE", year=None, roll=None):
        cur = db.execute("INSERT INTO users(name,email,password_hash,role,department,year,roll_no) VALUES(?,?,?,?,?,?,?)",
                         (name, email, ph[pw], role, dept, year, roll))
        return cur.lastrowid

    admin = add_user("Admin Office", "admin@campus.edu", "admin", "admin123", "Administration")
    fac1 = add_user("Dr. Sunita Rao", "sunita@campus.edu", "faculty", "faculty123")
    fac2 = add_user("Prof. Rajesh Kumar", "rajesh@campus.edu", "faculty", "faculty123")
    sub_ids = {}
    for s in bank.SUBJECTS:
        sub_ids[s] = db.execute("INSERT INTO subjects(name) VALUES(?)", (s,)).lastrowid

    ev_ids = []
    for t, k, d, dt, loc in EVENTS:
        ev_ids.append((db.execute("INSERT INTO events(title,kind,description,event_date,location,posted_by,created_at) VALUES(?,?,?,?,?,?,?)",
                                  (t, k, d, dt, loc, fac1 if k != "club" else fac2, now)).lastrowid, dt))

    for i, name in enumerate(NAMES):
        arche = ARCH[i % len(ARCH)]
        q = Q[arche]
        first = name.split()[0].lower()
        sid = add_user(name, f"{first}@campus.edu", "student", "student123", "CSE", 3 if i % 2 else 2, f"CG23{i + 1:03d}")
        for subj, subj_id in sub_ids.items():
            base = q * 100 + rng.gauss(0, 7)
            if i == 0 and subj == "DBMS":
                base -= 30
            for e, exam in enumerate(EXAMS):
                p = _clamp(base + TREND[arche] * e + rng.gauss(0, 4), 18, 99)
                db.execute("INSERT INTO marks(student_id,subject_id,exam,exam_order,score,max_score) VALUES(?,?,?,?,?,100)",
                           (sid, subj_id, exam, e + 1, round(p, 1)))
            frac = _clamp(q + .12 + rng.gauss(0, .07), .45, .99)
            if i == 0 and subj == "Operating Systems":
                frac = .68
            db.execute("INSERT INTO attendance(student_id,subject_id,attended,total) VALUES(?,?,?,60)",
                       (sid, subj_id, int(60 * frac)))
        for course, vt, at in (("Python Programming", 24, 8), ("Data Structures", 20, 6), ("DBMS", 22, 6)):
            f = _clamp(q + .05 + rng.gauss(0, .1), .1, 1)
            g = _clamp(q + .02 + rng.gauss(0, .1), .05, 1)
            db.execute("INSERT INTO lms(student_id,course,videos_watched,videos_total,assignments_done,assignments_total,hours_week) VALUES(?,?,?,?,?,?,?)",
                       (sid, course, int(vt * f), vt, int(round(at * g)), at, round(max(.5, q * 3 + rng.gauss(0, .5)), 1)))
        vals = [_clamp(q * 100 + rng.gauss(0, 10), 20, 98) for _ in range(4)]
        db.execute("INSERT INTO placement VALUES(?,?,?,?,?,?)",
                   (sid, *[round(v, 1) for v in vals], int(q * 5) + rng.randint(0, 1)))
        for sk in rng.sample(ALL_SKILLS, 6):
            db.execute("INSERT INTO skills(student_id,skill,level) VALUES(?,?,?)",
                       (sid, sk, int(_clamp(round(q * 5 + rng.gauss(0, .9)), 1, 5))))
        for k in range(2):
            rating = int(_clamp(round(q * 5 + rng.gauss(0, .6)), 1, 5))
            db.execute("INSERT INTO feedback(student_id,from_name,comment,rating,created_at) VALUES(?,?,?,?,?)",
                       (sid, "Dr. Sunita Rao" if k == 0 else "Prof. Rajesh Kumar", COMMENTS[rating], rating, f"2026-09-{10 + k * 7}"))
        for eid, dt in ev_ids:
            if dt < TODAY.isoformat():
                if rng.random() < q - .1:
                    db.execute("INSERT OR IGNORE INTO applications(event_id,student_id,status,applied_at) VALUES(?,?,?,?)",
                               (eid, sid, "attended", "2026-09-01"))
            elif rng.random() < q * .5:
                db.execute("INSERT OR IGNORE INTO applications(event_id,student_id,status,applied_at) VALUES(?,?,?,?)",
                           (eid, sid, "applied", "2026-10-10"))
        if arche in ("atrisk", "weak") or i == 0:
            items = [("Mentor meeting scheduled", "in_progress", "Weekly 20-minute check-in with the class mentor.")]
            if i == 0:
                items = [("DBMS remedial class enrolment", "open", "Join Tuesday and Thursday 4 PM remedial sessions.")]
            if arche == "atrisk":
                items.append(("Attendance alert sent to parents", "done", "Parents informed about low attendance."))
                items.append(("Remedial class enrolment", "open", "Extra classes for the weakest subjects."))
            for action, status, notes in items:
                db.execute("INSERT INTO interventions(student_id,created_by,action,status,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                           (sid, fac1, action, status, notes, "2026-10-05 10:00", now))

    # quizzes
    for subj in bank.SUBJECTS:
        tid = db.execute("INSERT INTO tests(title,kind,subject,language,duration,created_by,created_at,due_date) VALUES(?,?,?,?,?,?,?,?)",
                         (f"{subj} Quiz", "mcq", subj, None, 10, fac1, now, _d(60))).lastrowid
        for prompt, opts, ans in bank.BANK[subj]:
            db.execute("INSERT INTO questions(test_id,prompt,options,answer,points) VALUES(?,?,?,?,1)",
                       (tid, prompt, json.dumps(opts), ans))
    # coding exams, one per language, questions already loaded
    for lang, label in LANG_TITLES.items():
        tid = db.execute("INSERT INTO tests(title,kind,subject,language,duration,created_by,created_at,due_date) VALUES(?,?,?,?,?,?,?,?)",
                         (f"{label} Coding Exam", "coding", "Coding", lang, 45, fac1, now, _d(60))).lastrowid
        for p in PROBLEMS:
            cases = [{"in": i_, "out": o_, "hidden": n > 0} for n, (i_, o_) in enumerate(p["cases"])]
            db.execute("INSERT INTO problems(test_id,title,statement,starter,cases,points) VALUES(?,?,?,?,?,10)",
                       (tid, p["title"], p["statement"], STARTERS[lang][p["key"]], json.dumps(cases)))
    db.commit()
