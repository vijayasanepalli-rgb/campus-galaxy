"""Question bank used for seeded quizzes and for fresh practice questions."""
import random

SUBJECTS = [
    "Mathematics",
    "Data Structures",
    "DBMS",
    "Operating Systems",
    "Python Programming",
    "Computer Networks",
]

# (prompt, options, index of correct option)
BANK = {
    "Mathematics": [
        ("What is the derivative of x^3?", ["x^2", "3x^2", "3x", "x^3/3"], 1),
        ("The determinant of [[2,1],[4,3]] is?", ["2", "10", "-2", "6"], 0),
        ("The integral of 2x dx is?", ["x^2 + C", "2x^2 + C", "x + C", "2 + C"], 0),
        ("A and B are independent, P(A)=0.3, P(B)=0.5. What is P(A and B)?", ["0.8", "0.15", "0.2", "0.5"], 1),
        ("Sum of the first 10 natural numbers?", ["45", "55", "50", "60"], 1),
        ("The rank of a 3x3 identity matrix is?", ["1", "2", "3", "0"], 2),
    ],
    "Data Structures": [
        ("Which data structure follows LIFO order?", ["Queue", "Stack", "Tree", "Graph"], 1),
        ("Worst-case time of binary search on n sorted items?", ["O(n)", "O(log n)", "O(n log n)", "O(1)"], 1),
        ("Which BST traversal gives sorted output?", ["Preorder", "Postorder", "Inorder", "Level order"], 2),
        ("Average-case lookup time in a hash table?", ["O(1)", "O(n)", "O(log n)", "O(n^2)"], 0),
        ("Which structure is used for BFS?", ["Stack", "Queue", "Heap", "Matrix"], 1),
        ("Inserting at the head of a singly linked list takes?", ["O(1)", "O(n)", "O(log n)", "O(n^2)"], 0),
    ],
    "DBMS": [
        ("Which key uniquely identifies each row in a table?", ["Foreign key", "Primary key", "Composite index", "Alternate view"], 1),
        ("Which SQL clause filters grouped results?", ["WHERE", "HAVING", "ORDER BY", "LIMIT"], 1),
        ("In ACID, the letter I stands for?", ["Integrity", "Isolation", "Indexing", "Inheritance"], 1),
        ("Which normal form removes partial dependencies?", ["1NF", "2NF", "3NF", "BCNF"], 1),
        ("Which join returns every row from the left table?", ["INNER JOIN", "LEFT JOIN", "CROSS JOIN", "NATURAL JOIN"], 1),
        ("An index mainly speeds up?", ["Inserts", "Lookups and reads", "Backups", "Schema changes"], 1),
    ],
    "Operating Systems": [
        ("Which scheduling algorithm is non-preemptive?", ["Round Robin", "FCFS", "SRTF", "Multilevel feedback"], 1),
        ("Which condition is required for deadlock?", ["Preemption", "Circular wait", "Spooling", "Paging"], 1),
        ("Virtual memory is commonly implemented using?", ["Paging", "Pipelining", "Polling", "Spooling"], 0),
        ("The smallest unit of CPU scheduling is a?", ["Process", "Thread", "Program", "File"], 1),
        ("Semaphores are mainly used for?", ["Synchronization", "Compilation", "Encryption", "Rendering"], 0),
        ("Which is NOT a standard process state?", ["Ready", "Running", "Blocked", "Compiled"], 3),
    ],
    "Python Programming": [
        ("What does len([1, 2, 3]) return?", ["2", "3", "4", "Error"], 1),
        ("Which of these is immutable?", ["list", "dict", "tuple", "set"], 2),
        ("Which keyword defines a function?", ["func", "def", "function", "fn"], 1),
        ("What is 2 ** 3 in Python?", ["6", "8", "9", "5"], 1),
        ("Which literal creates a dictionary?", ["[1, 2]", "{'a': 1}", "(1, 2)", "<a:1>"], 1),
        ("What does 'abc'[::-1] give?", ["abc", "cba", "bac", "Error"], 1),
    ],
    "Computer Networks": [
        ("Which OSI layer handles routing?", ["Data link", "Network", "Transport", "Session"], 1),
        ("Which protocol is connectionless?", ["TCP", "UDP", "FTP", "SMTP"], 1),
        ("Default port for HTTPS?", ["80", "443", "21", "25"], 1),
        ("How long is an IPv4 address?", ["32 bits", "64 bits", "128 bits", "48 bits"], 0),
        ("DNS translates?", ["IP to MAC", "Domain names to IPs", "Ports to IPs", "URLs to files"], 1),
        ("Which device works at layer 2?", ["Hub", "Switch", "Repeater", "Modem"], 1),
    ],
}


def _gen_math(rng):
    kind = rng.choice(["deriv", "linear", "det", "ap", "comb"])
    if kind == "deriv":
        a, n = rng.randint(2, 9), rng.randint(2, 6)
        ans = f"{a * n}x^{n - 1}" if n > 2 else f"{a * n}x"
        wrong = {f"{a}x^{n - 1}", f"{a * n}x^{n}", f"{a * (n - 1)}x^{n - 1}", f"{n}x^{n - 1}"}
        wrong.discard(ans)
        return (f"What is the derivative of {a}x^{n}?", ans, sorted(wrong)[:3])
    if kind == "linear":
        a, x, b = rng.randint(2, 9), rng.randint(2, 12), rng.randint(1, 15)
        c = a * x + b
        wrong = {x + 1, x - 1, x + 2, c - b}
        wrong.discard(x)
        return (f"Solve for x: {a}x + {b} = {c}", str(x), [str(w) for w in sorted(wrong)[:3]])
    if kind == "det":
        a, b, c, d = (rng.randint(1, 9) for _ in range(4))
        ans = a * d - b * c
        wrong = {a * d + b * c, a * c - b * d, ans + 2, -ans}
        wrong.discard(ans)
        return (f"Determinant of [[{a},{b}],[{c},{d}]] is?", str(ans), [str(w) for w in sorted(wrong)[:3]])
    if kind == "ap":
        a, d, n = rng.randint(2, 9), rng.randint(2, 6), rng.randint(5, 12)
        ans = a + (n - 1) * d
        wrong = {ans + d, ans - d, a + n * d + 1}
        wrong.discard(ans)
        return (f"In an AP with first term {a} and common difference {d}, what is term {n}?", str(ans), [str(w) for w in sorted(wrong)[:3]])
    n, r = rng.randint(5, 8), rng.randint(2, 3)
    from math import comb
    ans = comb(n, r)
    wrong = {ans + n, ans - 1, comb(n, r) * r}
    wrong.discard(ans)
    return (f"How many ways can you choose {r} items from {n}?", str(ans), [str(w) for w in sorted(wrong)[:3]])


def fresh_questions(subject, n=5, seed=None):
    """Return n practice questions with shuffled options."""
    rng = random.Random(seed)
    items = []
    pool = list(BANK.get(subject, []))
    rng.shuffle(pool)
    for prompt, opts, ans in pool[: n if subject != "Mathematics" else max(1, n - 3)]:
        correct = opts[ans]
        shuffled = opts[:]
        rng.shuffle(shuffled)
        items.append({"prompt": prompt, "options": shuffled, "answer": shuffled.index(correct)})
    if subject == "Mathematics":
        while len(items) < n:
            prompt, correct, wrong = _gen_math(rng)
            opts = [correct] + wrong
            while len(opts) < 4:
                opts.append(str(int(rng.random() * 100)))
            opts = list(dict.fromkeys(opts))[:4]
            rng.shuffle(opts)
            if correct in opts:
                items.append({"prompt": prompt, "options": opts, "answer": opts.index(correct)})
    return items
