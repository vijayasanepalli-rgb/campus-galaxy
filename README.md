# Campus Galaxy: Student Success Platform

Flask app with Student, Faculty and Administrator portals, a galaxy + white theme, tests with runnable
coding exams (Python, JavaScript, C, Java), faculty-posted events, and an AI Campus Copilot.

## Run locally
```bash
pip install -r requirements.txt
python app.py                # http://127.0.0.1:5000
python tests/smoke_test.py   # 88 end-to-end checks
```
The database seeds itself with demo data on first launch.

| Role | Email | Password |
|---|---|---|
| Student | aarav@campus.edu | student123 |
| Faculty | sunita@campus.edu | faculty123 |
| Admin | admin@campus.edu | admin123 |

## Deploy to Vercel
```bash
git remote add origin https://github.com/<you>/campus-galaxy.git
git push -u origin main
```
Then import the repo on vercel.com (or run `vercel`). Set the `SECRET_KEY` environment variable.
Optional: `ANTHROPIC_API_KEY` lets the Copilot answer free-form questions with an LLM.

### Important Vercel limits
- Vercel's filesystem is ephemeral, so SQLite lives in `/tmp` and **data resets** on cold starts. For persistent data,
  switch `db.py` to a hosted database (Neon/Supabase Postgres, Turso).
- Vercel's Python runtime has no Node, gcc or Java. **Python coding exams work there; JavaScript, C and Java run only
  where those runtimes exist** (the app tells students when one is missing). For all languages in production, host on
  Render/Railway with Docker, or call a code-execution service (Judge0, Piston).
- The code runner is a lightweight sandbox (timeouts and resource limits): fine for a campus project, not hardened.

## Structure
`app.py` routes · `scoring.py` success score, risk, study plans · `copilot.py` assistant · `runner.py` code runner ·
`bank.py` questions · `seed.py` demo data · `importer.py` CSV import · `api/index.py` Vercel entry
