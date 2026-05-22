# database.py — SQLite 数据层
# 负责：锁定规则存档、筛选结果、HR 覆盖留痕、备选池、申诉记录

import sqlite3
import json
import os
from datetime import datetime
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "screening.db")


def _ensure_dir():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


@contextmanager
def _conn():
    _ensure_dir()
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


# ─── 初始化 ────────────────────────────────────────────────────────────────────

def init_db():
    """创建所有表（幂等）。"""
    with _conn() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS locked_rules (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            job_key     TEXT    NOT NULL,
            job_label   TEXT    NOT NULL,
            dims_json   TEXT    NOT NULL,
            fingerprint TEXT    NOT NULL,
            locked_at   TEXT    NOT NULL,
            created_at  TEXT    DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS screening_results (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id  TEXT NOT NULL,
            rule_id       INTEGER NOT NULL,
            scores_json   TEXT NOT NULL,
            reasons_json  TEXT NOT NULL,
            ai_result     TEXT NOT NULL,
            source        TEXT NOT NULL DEFAULT 'preset',
            created_at    TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS hr_overrides (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id    TEXT NOT NULL,
            rule_id         INTEGER NOT NULL,
            original_result TEXT NOT NULL,
            override_result TEXT NOT NULL,
            override_note   TEXT NOT NULL,
            created_at      TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS talent_pool (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id   TEXT NOT NULL UNIQUE,
            from_job_label TEXT NOT NULL,
            added_at       TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS appeals (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id  TEXT NOT NULL,
            candidate_name TEXT NOT NULL,
            appeal_text   TEXT NOT NULL,
            status        TEXT NOT NULL DEFAULT 'pending',
            submitted_at  TEXT DEFAULT (datetime('now','localtime'))
        );
        """)


# ─── 锁定规则 ──────────────────────────────────────────────────────────────────

def save_rule(job_key: str, job_label: str, dims: list,
              fingerprint: str, locked_at: str) -> int:
    """保存一条锁定规则，返回 row id。"""
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO locked_rules (job_key, job_label, dims_json, fingerprint, locked_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (job_key, job_label, json.dumps(dims, ensure_ascii=False),
             fingerprint, locked_at),
        )
        return cur.lastrowid


def get_all_rules() -> list:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM locked_rules ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


# ─── 筛选结果 ──────────────────────────────────────────────────────────────────

def save_screening_result(candidate_id: str, rule_id: int,
                          scores: dict, reasons: dict,
                          ai_result: str, source: str = "preset"):
    with _conn() as con:
        # upsert：同一候选人 + 规则只保留最新一条
        con.execute(
            "DELETE FROM screening_results "
            "WHERE candidate_id = ? AND rule_id = ?",
            (candidate_id, rule_id),
        )
        con.execute(
            "INSERT INTO screening_results "
            "(candidate_id, rule_id, scores_json, reasons_json, ai_result, source) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (candidate_id, rule_id,
             json.dumps(scores, ensure_ascii=False),
             json.dumps(reasons, ensure_ascii=False),
             ai_result, source),
        )


def get_screening_results(rule_id: int) -> dict:
    """返回 {candidate_id: {scores, reasons, ai_result, source}}。"""
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM screening_results WHERE rule_id = ?",
            (rule_id,),
        ).fetchall()
    result = {}
    for r in rows:
        result[r["candidate_id"]] = {
            "scores":    json.loads(r["scores_json"]),
            "reasons":   json.loads(r["reasons_json"]),
            "ai_result": r["ai_result"],
            "source":    r["source"],
        }
    return result


# ─── HR 覆盖留痕 ───────────────────────────────────────────────────────────────

def save_hr_override(candidate_id: str, rule_id: int,
                     original_result: str, override_result: str,
                     override_note: str):
    with _conn() as con:
        con.execute(
            "INSERT INTO hr_overrides "
            "(candidate_id, rule_id, original_result, override_result, override_note) "
            "VALUES (?, ?, ?, ?, ?)",
            (candidate_id, rule_id, original_result,
             override_result, override_note),
        )


def get_hr_overrides(rule_id: int) -> list:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM hr_overrides WHERE rule_id = ? ORDER BY created_at",
            (rule_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# ─── 备选池 ───────────────────────────────────────────────────────────────────

def add_to_pool_db(candidate_id: str, from_job_label: str):
    with _conn() as con:
        con.execute(
            "INSERT OR IGNORE INTO talent_pool (candidate_id, from_job_label) "
            "VALUES (?, ?)",
            (candidate_id, from_job_label),
        )


def remove_from_pool_db(candidate_id: str):
    with _conn() as con:
        con.execute(
            "DELETE FROM talent_pool WHERE candidate_id = ?",
            (candidate_id,),
        )


def get_pool_db() -> list:
    with _conn() as con:
        rows = con.execute(
            "SELECT candidate_id, from_job_label, added_at FROM talent_pool "
            "ORDER BY added_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


# ─── 申诉记录 ─────────────────────────────────────────────────────────────────

def save_appeal(candidate_id: str, candidate_name: str, appeal_text: str):
    with _conn() as con:
        con.execute(
            "INSERT INTO appeals (candidate_id, candidate_name, appeal_text) "
            "VALUES (?, ?, ?)",
            (candidate_id, candidate_name, appeal_text),
        )


def get_all_appeals() -> list:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM appeals ORDER BY submitted_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
