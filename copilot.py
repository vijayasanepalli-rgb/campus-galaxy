"""AI Campus Copilot: a rule-based assistant grounded in the student's real data.

If ANTHROPIC_API_KEY is set, unmatched questions fall back to an LLM that is given
a summary of the student's data. Without a key everything still works offline.
"""
import json
import os
import re
import urllib.request

import bank
import scoring

CONCEPTS = [
    (("array",), "**Array**: a fixed-size block of elements stored contiguously. Index access is O(1); inserting or deleting in the middle is O(n) because elements must shift."),
    (("linked list",), "**Linked list**: nodes that each hold a value and a pointer to the next node. Insert/delete at a known node is O(1), but searching is O(n) since there is no random access."),
    (("stack",), "**Stack**: Last-In-First-Out. Operations are push, pop and peek, all O(1). Used for undo, recursion and expression evaluation."),
    (("queue",), "**Queue**: First-In-First-Out. Enqueue at the back, dequeue at the front. Used in scheduling and BFS."),
    (("binary search",), "**Binary search**: on a sorted array, compare with the middle element and discard half each step. Time O(log n)."),
    (("recursion",), "**Recursion**: a function calling itself on a smaller input. It needs a base case to stop and a recursive case to make progress. Example: factorial(n) = n * factorial(n-1)."),
    (("sorting", "bubble sort", "merge sort", "quick sort"), "**Sorting**: bubble sort is simple but O(n^2); merge sort is O(n log n) and stable; quick sort is O(n log n) on average with O(n^2) worst case. Python's built-in sort is Timsort."),
    (("hash table", "hashing", "hash map"), "**Hash table**: a hash function maps a key to a bucket, giving average O(1) insert and lookup. Collisions are handled by chaining or open addressing."),
    (("tree", "bst"), "**Binary search tree**: left subtree values are smaller, right subtree values are larger. Inorder traversal gives sorted order. Search is O(h), where h is height (log n if balanced)."),
    (("bfs", "dfs", "graph"), "**Graph traversal**: BFS explores level by level using a queue (shortest path in unweighted graphs). DFS goes deep first using a stack or recursion. Both run in O(V+E)."),
    (("big o", "complexity", "time complexity"), "**Big-O**: describes how running time grows with input size n, ignoring constants. Common orders: O(1) < O(log n) < O(n) < O(n log n) < O(n^2)."),
    (("normalization", "normal form", "1nf", "2nf", "3nf"), "**Normalization**: organising tables to cut redundancy. 1NF: atomic values. 2NF: no partial dependency on part of a composite key. 3NF: no transitive dependency between non-key columns."),
    (("join",), "**SQL joins**: INNER keeps matching rows only; LEFT keeps all left rows plus matches; RIGHT is the mirror; FULL keeps everything; CROSS gives every combination."),
    (("primary key", "foreign key"), "**Keys**: a primary key uniquely identifies each row and cannot be NULL. A foreign key points to a primary key in another table to enforce relationships."),
    (("acid", "transaction"), "**ACID**: Atomicity (all or nothing), Consistency (valid state to valid state), Isolation (concurrent transactions don't interfere), Durability (committed data survives crashes)."),
    (("index",), "**Index**: an extra structure (often a B-tree) that lets the database find rows without scanning the whole table. Speeds up reads, slows down writes slightly."),
    (("process", "thread"), "**Process vs thread**: a process has its own memory space; threads inside a process share memory and are cheaper to create and switch between."),
    (("deadlock",), "**Deadlock**: processes wait on each other forever. Four conditions must hold: mutual exclusion, hold and wait, no preemption, circular wait. Break any one to prevent it."),
    (("paging", "virtual memory"), "**Paging**: memory is split into fixed-size pages mapped to frames. Virtual memory lets programs use more memory than RAM by swapping pages to disk, with page faults when a page is missing."),
    (("scheduling", "round robin", "fcfs"), "**CPU scheduling**: FCFS runs in arrival order; SJF picks the shortest job; Round Robin gives each process a time slice, which is fair for interactive systems."),
    (("tcp", "udp"), "**TCP vs UDP**: TCP is connection-oriented, reliable and ordered (web, email). UDP is connectionless and faster but offers no delivery guarantee (video calls, DNS, games)."),
    (("osi",), "**OSI model**: 7 layers: Physical, Data Link, Network, Transport, Session, Presentation, Application. Routing happens at Network; TCP/UDP at Transport."),
    (("dns",), "**DNS**: the internet's phonebook; it translates domain names like example.com into IP addresses."),
    (("ip address", "subnet"), "**IP addressing**: IPv4 uses 32 bits (e.g. 192.168.1.10); IPv6 uses 128. A subnet mask splits an address into network and host parts."),
    (("list", "dictionary", "dict"), "**Python list vs dict**: a list is an ordered, mutable sequence accessed by index; a dict maps keys to values with average O(1) lookup."),
    (("oop", "object oriented", "class"), "**OOP**: organising code into classes and objects using encapsulation, inheritance, polymorphism and abstraction."),
    (("derivative", "differentiation"), "**Derivative**: the rate of change of a function. Power rule: d/dx of x^n is n*x^(n-1). Example: d/dx of 3x^4 = 12x^3."),
    (("integral", "integration"), "**Integral**: the reverse of differentiation / area under a curve. Power rule: integral of x^n dx = x^(n+1)/(n+1) + C."),
    (("matrix", "determinant"), "**Matrix determinant (2x2)**: for [[a,b],[c,d]] it is ad - bc. A matrix is invertible only if its determinant is non-zero."),
    (("probability",), "**Probability**: P(event) = favourable outcomes / total outcomes. For independent events P(A and B) = P(A) * P(B)."),
]

SUBJECT_KEYS = [
    (("math", "calculus", "matrix", "probability", "algebra"), "Mathematics"),
    (("data structure", "dsa", "stack", "queue", "linked list", "tree", "graph"), "Data Structures"),
    (("dbms", "sql", "database", "normaliz"), "DBMS"),
    (("operating system", "deadlock", "scheduling", "paging", " os "), "Operating Systems"),
    (("python",), "Python Programming"),
    (("network", "tcp", "osi", "dns", "ip address"), "Computer Networks"),
]


def _find_subject(t):
    t = f" {t} "
    for keys, subj in SUBJECT_KEYS:
        if any(k in t for k in keys):
            return subj
    return None


def _has(t, *words):
    return any(w in t for w in words)


def _practice(subject):
    qs = bank.fresh_questions(subject, 5)
    lines = [f"Here are **5 fresh practice questions on {subject}**. Try them first, answers are at the bottom.\n"]
    for i, q in enumerate(qs, 1):
        lines.append(f"**Q{i}.** {q['prompt']}")
        for j, o in enumerate(q["options"]):
            lines.append(f"{'ABCD'[j]}) {o}")
        lines.append("")
    lines.append("**Answers:** " + ", ".join(f"Q{i}-{'ABCD'[q['answer']]}" for i, q in enumerate(qs, 1)))
    lines.append("\nWant a graded attempt? Open **Tests** and take the quiz.")
    return "\n".join(lines)


def _llm(system_ctx, message):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    body = json.dumps({
        "model": os.environ.get("COPILOT_MODEL", "claude-sonnet-5-5"), "max_tokens": 600,
        "system": "You are the AI Campus Copilot for a student-success platform. Be concise, kind and practical. "
                  "Use only this context about the user when personalising:\n" + system_ctx,
        "messages": [{"role": "user", "content": message}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
        return "".join(b.get("text", "") for b in data.get("content", []))
    except Exception:  # noqa: BLE001
        return None


HELP_STUDENT = ("I can help you with:\n- **Progress**: marks, weak subjects, backlogs, attendance, success score\n"
                "- **Study plan** for the week based on your weak areas\n- **Practice questions** with answers on any subject\n"
                "- **Explain concepts** (e.g. \"explain deadlock\")\n- **Resources**: video recommendations\n"
                "- **Events**, hackathons, placement and coding preparation")
CHIPS_STUDENT = ["Make my study plan", "How is my attendance?", "Give me practice questions", "Recommend videos",
                 "Which events should I join?", "Why is my success score like this?"]
CHIPS_STAFF = ["Which students are at risk?", "Who has low attendance?", "Class summary", "Who needs coding help?"]


def reply(db, user, text, metrics=None, staff_rows=None):
    t = " " + text.lower().strip() + " "
    role = user["role"]
    if role in ("faculty", "admin"):
        return _staff_reply(t, text, staff_rows or [])
    m = metrics
    subj = _find_subject(t)
    weakest = min(m["subjects"], key=lambda s: s["latest"]) if m["subjects"] else None

    if _has(t, "explain", "what is", "what are", "define", "meaning of", "difference between", "how does", "teach me"):
        for keys, expl in CONCEPTS:
            if any(k in t for k in keys):
                return {"text": expl + "\n\nWant practice questions on this? Just ask.", "chips": ["Give me practice questions", "Make my study plan"]}
    if _has(t, "practice", "quiz me", "questions", "mcq", "test me", "question paper"):
        s = subj or (weakest["name"] if weakest else "Data Structures")
        return {"text": _practice(s), "chips": [f"Explain {s.lower()} basics", "Make my study plan"]}
    if _has(t, "study plan", "plan", "schedule", "timetable"):
        plan = scoring.study_plan(m)
        lines = ["Here is a **7-day plan** built from your weakest subjects:\n"]
        for p in plan:
            lines.append(f"**{p['day']}** - {p['title']}: {p['detail']}")
        return {"text": "\n".join(lines), "chips": ["Recommend videos", "Give me practice questions"]}
    if _has(t, "attendance", "absent", "bunk", "75", "classes"):
        low = [a for a in m["attendance"] if a["pct"] < 75]
        if not m["attendance"]:
            return {"text": "I don't have attendance data for you yet.", "chips": CHIPS_STUDENT[:3]}
        msg = f"Your overall attendance is **{m['att_overall']:.0f}%**."
        if low:
            msg += " Subjects below 75%:\n" + "\n".join(f"- {a['name']}: {a['pct']:.0f}% (attend the next {a['need']} classes to reach 75%)" for a in low)
        else:
            msg += " Every subject is above the 75% minimum. Nice work."
        return {"text": msg, "chips": ["Make my study plan", "Why is my success score like this?"]}
    if _has(t, "event", "hackathon", "workshop", "club", "certif", "join"):
        ev = db.execute("SELECT e.* FROM events e WHERE e.event_date >= date('now') AND e.id NOT IN "
                        "(SELECT event_id FROM applications WHERE student_id=?) ORDER BY e.event_date LIMIT 4", (user["id"],)).fetchall()
        if not ev:
            return {"text": "You've already applied to every upcoming event. Check the Engagement page for updates.", "chips": CHIPS_STUDENT[:3]}
        lines = ["Open events I'd suggest, based on your profile:\n"]
        for e in ev:
            why = "boosts your coding and teamwork" if e["kind"] == "hackathon" else "adds to your engagement score"
            lines.append(f"- **{e['title']}** ({e['kind']}, {e['event_date']}): {why}.")
        lines.append("\nApply from the **Engagement** page.")
        return {"text": "\n".join(lines), "chips": ["Make my study plan"]}
    if _has(t, "video", "resource", "recommend", "learn", "course", "tutorial", "material"):
        res = scoring.resources(m)
        lines = ["Based on your weakest subjects, start with these:\n"]
        for r in res:
            lines.append(f"- {r['subject']} ({r['score']:.0f}%): [{r['title']}]({r['url']})")
        return {"text": "\n".join(lines), "chips": ["Make my study plan", "Give me practice questions"]}
    if _has(t, "placement", "interview", "aptitude", "career", "job", "resume"):
        p = m["placement"]
        parts = {"aptitude": p["aptitude"], "coding": p["coding"], "communication": p["communication"], "mock interviews": p["mock_interview"]}
        low = min(parts, key=parts.get)
        tips = {"aptitude": "practise 20 aptitude questions daily (quant + logical).",
                "coding": "solve problems in the Coding Exams section; each solved problem adds +5.",
                "communication": "record a 2-minute self-introduction and join the Mock Interview Bootcamp.",
                "mock interviews": "book mock interviews; two a month builds confidence quickly."}
        return {"text": f"Your placement readiness is **{p['score']:.0f}/100**. Your lowest area is **{low}** ({parts[low]:.0f}). Next step: {tips[low]}",
                "chips": ["Which events should I join?", "Make my study plan"]}
    if _has(t, "coding", "code", "programming exam"):
        n = db.execute("SELECT COUNT(*) c FROM problems").fetchone()["c"]
        return {"text": f"There are **{n} coding problems** across Python, JavaScript, C and Java. Write your code, click Run to test it, then Submit. You've fully solved **{m['placement']['solved']}** so far, which added **+{m['placement']['coding_bonus']}** to your coding readiness (max +20).",
                "chips": ["Give me practice questions", "Placement readiness"]}
    if _has(t, "success score", "why", "improve", "boost", "risk", "explain my", "increase"):
        c = sorted(m["components"], key=lambda c: -c["gain"])[:3]
        lines = [f"Your **Success Score is {m['success']:.0f}/100** ({m['segment']}, {m['risk']} risk). Biggest opportunities:\n"]
        for x in c:
            lines.append(f"- **{x['label']}** is {x['score']:.0f}/100. Raising it to 80 adds about +{x['gain']} points.")
        if m["reasons"]:
            lines.append("\nWatch-outs: " + "; ".join(m["reasons"]) + ".")
        return {"text": "\n".join(lines), "chips": ["Make my study plan", "How is my attendance?"]}
    if _has(t, "marks", "score", "grade", "weak", "subject", "backlog", "performance", "result", "progress"):
        if not m["subjects"]:
            return {"text": "No marks are recorded for you yet.", "chips": CHIPS_STUDENT[:3]}
        lines = [f"Your academic average is **{m['academics']:.0f}%**. Subject scores (latest):\n"]
        for s in sorted(m["subjects"], key=lambda s: s["latest"]):
            lines.append(f"- {s['name']}: {s['latest']:.0f}%" + (" (backlog risk)" if s["latest"] < 40 else ""))
        lines.append(f"\nFocus first on **{weakest['name']}**.")
        return {"text": "\n".join(lines), "chips": ["Make my study plan", f"Give me practice questions on {weakest['name']}"]}
    if _has(t, "test", "exam"):
        pend = db.execute("SELECT title, kind, due_date FROM tests WHERE id NOT IN (SELECT test_id FROM attempts WHERE student_id=?) "
                          "ORDER BY due_date LIMIT 5", (user["id"],)).fetchall()
        lines = ["Tests available for you:\n"] + [f"- {p['title']} ({p['kind']}, due {p['due_date']})" for p in pend]
        return {"text": "\n".join(lines) + "\n\nOpen the **Tests** page to start.", "chips": CHIPS_STUDENT[:3]}
    if _has(t, "hello", "hi ", "hey", "help", "what can you do"):
        return {"text": f"Hi {user['name'].split()[0]}! I'm your Campus Copilot.\n\n{HELP_STUDENT}", "chips": CHIPS_STUDENT}
    ctx = f"Student {user['name']}; success {m['success']}; attendance {m['att_overall']}%; weakest {weakest['name'] if weakest else 'n/a'}."
    ans = _llm(ctx, text)
    if ans:
        return {"text": ans, "chips": CHIPS_STUDENT[:3]}
    if subj:
        return {"text": f"I can explain {subj} concepts or give you practice questions. Try \"explain deadlock\" or \"practice {subj}\".", "chips": [f"Practice {subj}"]}
    return {"text": "I'm not sure about that one yet.\n\n" + HELP_STUDENT, "chips": CHIPS_STUDENT}


def _staff_reply(t, raw, rows):
    if not rows:
        return {"text": "There is no student data yet.", "chips": []}
    n = len(rows)
    if _has(t, "at risk", "at-risk", "risk", "struggling", "weak students"):
        risky = sorted([r for r in rows if r["m"]["risk"] == "high"], key=lambda r: r["m"]["success"])[:6]
        if not risky:
            return {"text": "No students are currently high-risk.", "chips": CHIPS_STAFF}
        lines = [f"**{len(risky)} high-risk students** (lowest scores first):\n"]
        for r in risky:
            lines.append(f"- **{r['u']['name']}** ({r['m']['success']:.0f}): " + "; ".join(r["m"]["reasons"][:2]))
        lines.append("\nOpen the Students page to log an intervention.")
        return {"text": "\n".join(lines), "chips": CHIPS_STAFF}
    if _has(t, "attendance"):
        low = sorted([r for r in rows if r["m"]["att_overall"] < 75], key=lambda r: r["m"]["att_overall"])[:8]
        if not low:
            return {"text": "Everyone is above 75% attendance.", "chips": CHIPS_STAFF}
        return {"text": "**Students below 75% attendance:**\n\n" + "\n".join(f"- {r['u']['name']}: {r['m']['att_overall']:.0f}%" for r in low), "chips": CHIPS_STAFF}
    if _has(t, "coding"):
        low = sorted(rows, key=lambda r: r["m"]["placement"]["coding"])[:6]
        return {"text": "**Students who need coding help:**\n\n" + "\n".join(f"- {r['u']['name']}: coding readiness {r['m']['placement']['coding']:.0f}" for r in low), "chips": CHIPS_STAFF}
    if _has(t, "summary", "overview", "class", "how are"):
        avg = sum(r["m"]["success"] for r in rows) / n
        hi = sum(1 for r in rows if r["m"]["risk"] == "high")
        att = sum(r["m"]["att_overall"] for r in rows) / n
        return {"text": f"**Class summary**: {n} students, average success score **{avg:.0f}**, average attendance **{att:.0f}%**, **{hi}** high-risk.", "chips": CHIPS_STAFF}
    return {"text": "Ask me about at-risk students, low attendance, coding help or a class summary.", "chips": CHIPS_STAFF}
