"""SQLite helpers. On Vercel the filesystem is read-only except /tmp."""
import os
import sqlite3

from flask import g

BASE = os.path.dirname(os.path.abspath(__file__))


def db_path():
    if os.environ.get("CAMPUS_DB"):
        return os.environ["CAMPUS_DB"]
    if os.environ.get("VERCEL") or os.environ.get("DB_IN_TMP"):
        return "/tmp/campus_galaxy.db"
    d = os.path.join(BASE, "instance")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "campus.db")


SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, name TEXT, email TEXT UNIQUE, password_hash TEXT,
  role TEXT, department TEXT, year INTEGER, roll_no TEXT, notify INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS subjects(id INTEGER PRIMARY KEY, name TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS marks(
  id INTEGER PRIMARY KEY, student_id INTEGER, subject_id INTEGER, exam TEXT,
  exam_order INTEGER, score REAL, max_score REAL);
CREATE TABLE IF NOT EXISTS attendance(
  id INTEGER PRIMARY KEY, student_id INTEGER, subject_id INTEGER,
  attended INTEGER, total INTEGER);
CREATE TABLE IF NOT EXISTS lms(
  id INTEGER PRIMARY KEY, student_id INTEGER, course TEXT, videos_watched INTEGER,
  videos_total INTEGER, assignments_done INTEGER, assignments_total INTEGER, hours_week REAL);
CREATE TABLE IF NOT EXISTS placement(
  student_id INTEGER PRIMARY KEY, aptitude REAL, coding REAL, communication REAL,
  mock_interview REAL, mock_count INTEGER);
CREATE TABLE IF NOT EXISTS skills(
  id INTEGER PRIMARY KEY, student_id INTEGER, skill TEXT, level INTEGER);
CREATE TABLE IF NOT EXISTS feedback(
  id INTEGER PRIMARY KEY, student_id INTEGER, from_name TEXT, comment TEXT,
  rating INTEGER, created_at TEXT);
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY, title TEXT, kind TEXT, description TEXT, event_date TEXT,
  location TEXT, posted_by INTEGER, created_at TEXT);
CREATE TABLE IF NOT EXISTS applications(
  id INTEGER PRIMARY KEY, event_id INTEGER, student_id INTEGER, status TEXT,
  applied_at TEXT, UNIQUE(event_id, student_id));
CREATE TABLE IF NOT EXISTS tests(
  id INTEGER PRIMARY KEY, title TEXT, kind TEXT, subject TEXT, language TEXT,
  duration INTEGER, created_by INTEGER, created_at TEXT, due_date TEXT);
CREATE TABLE IF NOT EXISTS questions(
  id INTEGER PRIMARY KEY, test_id INTEGER, prompt TEXT, options TEXT,
  answer INTEGER, points INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS problems(
  id INTEGER PRIMARY KEY, test_id INTEGER, title TEXT, statement TEXT,
  starter TEXT, cases TEXT, points INTEGER DEFAULT 10);
CREATE TABLE IF NOT EXISTS attempts(
  id INTEGER PRIMARY KEY, test_id INTEGER, student_id INTEGER, score REAL,
  max_score REAL, submitted_at TEXT);
CREATE TABLE IF NOT EXISTS code_best(
  student_id INTEGER, problem_id INTEGER, score REAL, passed INTEGER, total INTEGER,
  code TEXT, updated_at TEXT, PRIMARY KEY(student_id, problem_id));
CREATE TABLE IF NOT EXISTS interventions(
  id INTEGER PRIMARY KEY, student_id INTEGER, created_by INTEGER, action TEXT,
  status TEXT, notes TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS import_log(
  id INTEGER PRIMARY KEY, dataset TEXT, rows_ok INTEGER, rows_err INTEGER,
  created_at TEXT, by_name TEXT);
"""


def get_db():
    if "db" not in g:
        conn = sqlite3.connect(db_path())
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db():
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.commit()


def q(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rows = cur.fetchall()
    return (rows[0] if rows else None) if one else rows


def ex(sql, args=()):
    conn = get_db()
    cur = conn.execute(sql, args)
    conn.commit()
    return cur.lastrowid
