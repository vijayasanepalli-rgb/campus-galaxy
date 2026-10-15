"""End-to-end smoke test: run with `python tests/smoke_test.py` from the project root."""
import io
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["CAMPUS_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")

from app import app  # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if (extra and not cond) else ""))
    if not cond:
        fails.append(name)


def login(c, email, pw):
    c.get("/logout")
    return c.post("/login", data={"email": email, "password": pw}, follow_redirects=False)


def get_ok(c, path, must=None):
    r = c.get(path)
    body = r.get_data(as_text=True)
    ok = r.status_code == 200 and (must is None or must in body)
    check(f"GET {path}", ok, f"{r.status_code}" + ("" if must is None or must in body else f" missing '{must}'"))
    return body


with app.test_client() as c:
    # ---------- auth
    check("anonymous redirected to login", c.get("/student").status_code == 302)
    check("bad password rejected", "Incorrect email" in c.post("/login", data={"email": "aarav@campus.edu", "password": "x"}).get_data(as_text=True))
    r = login(c, "aarav@campus.edu", "student123")
    check("student login redirects", r.status_code == 302 and r.headers["Location"].endswith("/student"))
    check("student blocked from staff area", c.get("/staff").status_code == 403)
    check("student blocked from admin area", c.get("/admin/users").status_code == 403)

    # ---------- every student page
    for p, must in [("/student", "Success"), ("/student/academics", "7-day"), ("/student/attendance", "Subject-wise"),
                    ("/student/lms", "My courses"), ("/student/engagement", "Upcoming"), ("/student/placement", "Placement"),
                    ("/student/skills", "My skills"), ("/student/score", "How your score"), ("/student/tests", "Python Coding Exam"),
                    ("/student/tests?kind=coding&lang=java", "Java Coding Exam"), ("/copilot", "Copilot"), ("/settings", "Profile")]:
        get_ok(c, p, must)
    check("robot image on tests page", "robot.svg" in get_ok(c, "/student/tests"))

    # ---------- MCQ quiz
    body = get_ok(c, "/student/tests/1", "Submit quiz")
    form = {}
    for qid in range(1, 7):
        form[f"q{qid}"] = "1"
    r = c.post("/student/tests/1/submit", data=form)
    check("quiz submit graded", r.status_code == 200 and "Retake" in r.get_data(as_text=True))

    # ---------- coding exam: wrong then right
    body = get_ok(c, "/student/tests/7", "Python")  # python coding exam
    pid = json.loads(__import__("re").search(r"initIDE\((.*)\);", body, __import__("re").S).group(1))[0]["id"]
    r = c.post("/api/code/run", json={"problem_id": pid, "code": "print(1)"}).get_json()
    check("run: sample fails on wrong code", r["results"][0]["passed"] is False)
    r = c.post("/api/code/run", json={"problem_id": pid, "code": "print(input())", "stdin": "hello"}).get_json()
    check("run: custom input echoes", r["results"][0]["output"].strip() == "hello")
    r = c.post("/api/code/submit", json={"problem_id": pid, "code": "print(0)"}).get_json()
    check("submit: wrong code scores partial/zero", r["score"] < 10, r)
    before = r["success_after"]
    r = c.post("/api/code/submit", json={"problem_id": pid, "code": "a,b=map(int,input().split())\nprint(a+b)"}).get_json()
    check("submit: correct code full marks", r["passed"] == r["total"] and r["score"] == 10, r)
    check("submit: success score increases", r["success_after"] > before - 0.0001 and r["coding"] > 0, r)
    check("submit: hidden tests do not leak expected output", all("expected" not in x for x in r["results"] if x["label"].startswith("Hidden")))
    r = c.post("/api/code/submit", json={"problem_id": pid, "code": "print(1)"}).get_json()
    check("submit: best score is kept", r["best"] == 10, r)
    r = c.post("/api/code/submit", json={"problem_id": pid, "code": "while True: pass"}).get_json()
    check("submit: infinite loop times out", any(x["status"] == "timeout" for x in r["results"]))

    # other languages
    import re
    for tid, code in [(8, "const [a,b]=require('fs').readFileSync(0,'utf8').trim().split(/\\s+/).map(Number);console.log(a+b);"),
                      (9, '#include <stdio.h>\nint main(){long long a,b;scanf("%lld %lld",&a,&b);printf("%lld\\n",a+b);return 0;}'),
                      (10, "import java.util.*;public class Main{public static void main(String[] x){Scanner s=new Scanner(System.in);System.out.println(s.nextLong()+s.nextLong());}}")]:
        b = get_ok(c, f"/student/tests/{tid}")
        p = json.loads(re.search(r"initIDE\((.*)\);", b, re.S).group(1))[0]["id"]
        r = c.post("/api/code/submit", json={"problem_id": p, "code": code}).get_json()
        check(f"language test {tid} passes all", r.get("passed") == r.get("total") == 4, r)

    # ---------- engagement
    r = c.post("/student/engagement/apply/3", follow_redirects=True)
    check("apply to event", "Application submitted" in r.get_data(as_text=True))

    # ---------- copilot
    for msg, must in [("make my study plan", "7-day"), ("how is my attendance", "attendance"), ("explain deadlock", "Deadlock"),
                      ("give me practice questions on dbms", "Answers"), ("recommend videos", "youtube"),
                      ("which events should I join", "Engagement"), ("why is my success score like this", "Success Score"),
                      ("what are my marks", "Focus first"), ("placement tips", "readiness")]:
        r = c.post("/api/copilot", json={"message": msg}).get_json()
        check(f"copilot: {msg}", must.lower() in r["text"].lower(), r["text"][:80])

    # ---------- settings
    r = c.post("/settings", data={"form": "profile", "name": "Aarav S", "notify": "on"}, follow_redirects=True)
    check("profile update", "Profile updated" in r.get_data(as_text=True))
    r = c.post("/settings", data={"form": "password", "current": "student123", "new": "newpass1"}, follow_redirects=True)
    check("password change", "Password changed" in r.get_data(as_text=True))
    login(c, "aarav@campus.edu", "newpass1")
    check("login with new password", c.get("/student").status_code == 200)

    # ---------- faculty
    login(c, "sunita@campus.edu", "faculty123")
    for p, must in [("/staff", "Faculty dashboard"), ("/staff/students", "Students"), ("/staff/students?risk=high", "Students"),
                    ("/staff/students/4", "Explainable score"), ("/staff/tests", "Tests"), ("/staff/tests/new", "Publish test"),
                    ("/staff/tests/7", "results"), ("/staff/events", "Post a new event"), ("/staff/events/3", "Applicants"),
                    ("/staff/interventions", "Intervention tracking"), ("/staff/reports", "Reports"), ("/copilot", "Copilot")]:
        get_ok(c, p, must)
    check("faculty blocked from admin pages", c.get("/admin/integration").status_code == 403)
    check("CSV export", "roll_no,name" in c.get("/staff/reports/export.csv").get_data(as_text=True))
    for msg in ["which students are at risk", "who has low attendance", "class summary", "who needs coding help"]:
        r = c.post("/api/copilot", json={"message": msg}).get_json()
        check(f"staff copilot: {msg}", len(r["text"]) > 20)

    # post an MCQ test
    r = c.post("/staff/tests/new", data={"title": "Faculty Quiz", "kind": "mcq", "duration": "5", "subject": "DBMS",
               "mcq_text": "What is SQL? | A language | A fruit | A car | A city | A\nCapital of France? | Rome | Paris | Berlin | Madrid | B"}, follow_redirects=True)
    check("faculty posts quiz", "Test posted" in r.get_data(as_text=True))
    # post a coding test
    r = c.post("/staff/tests/new", data={"title": "Double It", "kind": "coding", "duration": "20", "language": "python",
               "p_title": "Double", "p_statement": "Print 2*n", "p_inputs": "2\n---\n5\n---\n0", "p_outputs": "4\n---\n10\n---\n0",
               "p_starter": "n=int(input())\n"}, follow_redirects=True)
    check("faculty posts coding exam", "Test posted" in r.get_data(as_text=True))
    # post event
    r = c.post("/staff/events", data={"title": "Faculty Hackathon", "kind": "hackathon", "event_date": "2099-01-01", "location": "Lab", "description": "x"}, follow_redirects=True)
    check("faculty posts event", "Event posted" in r.get_data(as_text=True))
    # intervention + feedback
    r = c.post("/staff/students/8/intervention", data={"action": "Mentor call", "notes": "weekly"}, follow_redirects=True)
    check("log intervention", "Mentor call" in r.get_data(as_text=True))
    r = c.post("/staff/students/8/feedback", data={"comment": "Great effort lately", "rating": "5"}, follow_redirects=True)
    check("add feedback", "Great effort lately" in r.get_data(as_text=True))
    r = c.post("/staff/interventions", data={"id": "1", "status": "done"}, follow_redirects=True)
    check("update intervention status", r.status_code == 200)

    # student sees posted items and can take them
    login(c, "aarav@campus.edu", "newpass1")
    b = get_ok(c, "/student/tests", "Faculty Quiz")
    check("student sees faculty coding exam", "Double It" in b)
    b = get_ok(c, "/student/engagement", "Faculty Hackathon")
    # find the new coding problem and solve it
    ids = re.findall(r'/student/tests/(\d+)"', b + get_ok(c, "/student/tests"))
    newest = max(int(i) for i in ids)
    body = get_ok(c, f"/student/tests/{newest}")
    probs = json.loads(re.search(r"initIDE\((.*)\);", body, re.S).group(1)) if "initIDE" in body else None
    if probs:
        r = c.post("/api/code/submit", json={"problem_id": probs[0]["id"], "code": "n=int(input())\nprint(2*n)"}).get_json()
        check("faculty-posted coding problem is gradable", r["passed"] == 3, r)
    else:
        check("faculty-posted coding problem is gradable", False, "no IDE found")

    # ---------- admin
    login(c, "admin@campus.edu", "admin123")
    for p, must in [("/staff", "Administrator console"), ("/admin/integration", "Data Integration"), ("/admin/users", "Add a user"),
                    ("/admin/integration/attendance/template.csv", "roll_no")]:
        get_ok(c, p, must)
    csvtext = "roll_no,subject,attended,total\nCG23001,Mathematics,10,60\nCG23001,DBMS,12,60\nBAD99,DBMS,1,2\nCG23002,DBMS,70,60\n"
    r = c.post("/admin/integration", data={"dataset": "attendance", "file": (io.BytesIO(csvtext.encode()), "a.csv")},
               content_type="multipart/form-data")
    t = r.get_data(as_text=True)
    check("CSV import: 2 ok, 2 rejected", "2 row(s) imported" in t and "2 skipped" in t and "unknown roll_no" in t, t[t.find("flash"):t.find("flash") + 300])
    r = c.post("/admin/integration", data={"dataset": "attendance", "pasted": "wrong,cols\n1,2"})
    check("CSV import: missing columns reported", "Missing columns" in r.get_data(as_text=True))
    r = c.post("/admin/users", data={"name": "New Student", "email": "new@campus.edu", "role": "student", "password": "secret12", "roll_no": "CG23099", "year": "2"}, follow_redirects=True)
    check("admin creates user", "User created" in r.get_data(as_text=True))
    login(c, "new@campus.edu", "secret12")
    check("new user can log in", c.get("/student").status_code == 200)
    check("404 page", c.get("/nope").status_code == 404)

print("\n" + ("ALL TESTS PASSED" if not fails else f"{len(fails)} FAILED: {fails}"))
sys.exit(1 if fails else 0)
