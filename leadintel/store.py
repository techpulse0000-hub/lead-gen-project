"""Versioned evidence, full-text retrieval, budgets and qualification state."""
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS sources(
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, url TEXT UNIQUE NOT NULL,
          origin TEXT NOT NULL, prefix TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS documents(
          id INTEGER PRIMARY KEY, source_id INTEGER REFERENCES sources(id),
          url TEXT UNIQUE NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,
          content_hash TEXT NOT NULL, retrieved_at TEXT NOT NULL, checked_at TEXT NOT NULL,
          publication_date TEXT, signals TEXT NOT NULL, geography TEXT NOT NULL,
          access_method TEXT NOT NULL, is_demo INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS versions(
          id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL REFERENCES documents(id),
          content_hash TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,
          retrieved_at TEXT NOT NULL, publication_date TEXT, UNIQUE(document_id,content_hash));
        CREATE VIRTUAL TABLE IF NOT EXISTS evidence_fts USING fts5(title,body);
        CREATE TABLE IF NOT EXISTS jobs(
          id INTEGER PRIMARY KEY, source_id INTEGER NOT NULL REFERENCES sources(id),
          status TEXT NOT NULL, created_at TEXT NOT NULL, lease_until REAL NOT NULL DEFAULT 0,
          owner TEXT, note TEXT);
        CREATE TABLE IF NOT EXISTS frontier(
          job_id INTEGER NOT NULL REFERENCES jobs(id), url TEXT NOT NULL,
          depth INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending', error TEXT,
          PRIMARY KEY(job_id,url));
        CREATE TABLE IF NOT EXISTS fetch_attempts(
          id INTEGER PRIMARY KEY, job_id INTEGER NOT NULL REFERENCES jobs(id),
          origin TEXT NOT NULL, url TEXT NOT NULL, started_at TEXT NOT NULL,
          status TEXT NOT NULL, detail TEXT);
        CREATE TABLE IF NOT EXISTS leads(
          id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL REFERENCES documents(id),
          company TEXT NOT NULL, reason TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'flagged',
          created_at TEXT NOT NULL, UNIQUE(document_id,company));
        CREATE TABLE IF NOT EXISTS enrichment_queue(
          id INTEGER PRIMARY KEY, lead_id INTEGER UNIQUE NOT NULL REFERENCES leads(id),
          status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS transitions(
          id INTEGER PRIMARY KEY, lead_id INTEGER NOT NULL REFERENCES leads(id),
          previous_status TEXT NOT NULL, next_status TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TRIGGER IF NOT EXISTS qualification_queue_gate
        BEFORE INSERT ON enrichment_queue
        WHEN NOT EXISTS(SELECT 1 FROM leads WHERE id=NEW.lead_id AND status='qualification_in_progress')
        BEGIN SELECT RAISE(ABORT,'Enrichment requires active qualification'); END;
        """)

    def close(self):
        self.db.close()

    def rows(self, sql, args=()):
        return [dict(r) for r in self.db.execute(sql, args)]

    def ingest(self, source_id, url, title, body, publication_date=None,
               signals=(), geography=(), access_method="direct_http", is_demo=False):
        stamp = now()
        digest = hashlib.sha256(json.dumps([title,body,publication_date],ensure_ascii=False).encode()).hexdigest()
        with self.db:
            row = self.db.execute("SELECT * FROM documents WHERE url=?", (url,)).fetchone()
            values = (source_id, title, body, digest, stamp, stamp, publication_date,
                      json.dumps(sorted(set(signals))), json.dumps(sorted(set(geography))),
                      access_method, int(is_demo))
            if row and row["content_hash"] == digest and row["publication_date"] == publication_date:
                self.db.execute("UPDATE documents SET checked_at=?,signals=?,geography=? WHERE id=?", (stamp,json.dumps(sorted(set(signals))),json.dumps(sorted(set(geography))),row["id"]))
                return row["id"]
            if row:
                ident = row["id"]
                self.db.execute("""UPDATE documents SET source_id=?,title=?,body=?,content_hash=?,
                retrieved_at=?,checked_at=?,publication_date=?,signals=?,geography=?,access_method=?,
                is_demo=? WHERE id=?""", (*values, ident))
                self.db.execute("DELETE FROM evidence_fts WHERE rowid=?", (ident,))
            else:
                ident = self.db.execute("""INSERT INTO documents(source_id,title,body,content_hash,
                retrieved_at,checked_at,publication_date,signals,geography,access_method,is_demo,url)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", (*values, url)).lastrowid
            self.db.execute("""INSERT OR IGNORE INTO versions(document_id,content_hash,title,body,
              retrieved_at,publication_date) VALUES(?,?,?,?,?,?)""",
                            (ident, digest, title, body, stamp, publication_date))
            self.db.execute("INSERT INTO evidence_fts(rowid,title,body) VALUES(?,?,?)", (ident,title,body))
        return ident

    def search(self, query="", signal=None, geography=None, limit=20, source_id=None):
        if not 1 <= limit <= 100 or len(query) > 500:
            raise ValueError("Search limit 1–100; query at most 500 characters")
        tokens = re.findall(r"[\w'-]+", query, re.UNICODE)[:25]
        params = []
        if tokens:
            # Quote every token; user input cannot become FTS syntax or SQL.
            expr = " AND ".join('"' + t.replace('"','""') + '"' for t in tokens)
            sql = """SELECT d.*,bm25(evidence_fts,3.0,1.0) AS rank,
            snippet(evidence_fts,1,'[',']',' … ',30) AS excerpt FROM evidence_fts
            JOIN documents d ON d.id=evidence_fts.rowid WHERE evidence_fts MATCH ?"""
            params.append(expr)
        else:
            sql = "SELECT d.*,0 AS rank,substr(body,1,320) AS excerpt FROM documents d WHERE 1=1"
        if signal:
            sql += " AND EXISTS(SELECT 1 FROM json_each(d.signals) WHERE value=?)"
            params.append(signal)
        if geography:
            sql += " AND EXISTS(SELECT 1 FROM json_each(d.geography) WHERE value=?)"
            params.append(geography)
        if source_id is not None:
            sql += " AND d.source_id=?"
            params.append(source_id)
        sql += " ORDER BY rank,d.retrieved_at DESC,d.id LIMIT ?"
        params.append(limit)
        results = self.rows(sql, params)
        for r in results:
            r.pop("body")
            r["signals"] = json.loads(r["signals"])
            r["geography"] = json.loads(r["geography"])
            r["verification_status"] = "unverified_evidence"
            r["event_date"] = None
            r["match_reason"] = {"terms": tokens, "signal_filter":signal,
                                 "geography_mentions":r["geography"]}
        return results

    def reserve_fetch(self, job_id, origin, url, daily=200, per_origin=30, per_job=50):
        stamp = now()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            total = self.db.execute("SELECT COUNT(*) FROM fetch_attempts WHERE substr(started_at,1,10)=?", (stamp[:10],)).fetchone()[0]
            host = self.db.execute("SELECT COUNT(*) FROM fetch_attempts WHERE substr(started_at,1,10)=? AND origin=?", (stamp[:10],origin)).fetchone()[0]
            job = self.db.execute("SELECT COUNT(*) FROM fetch_attempts WHERE job_id=?", (job_id,)).fetchone()[0]
            if total >= daily or host >= per_origin or job >= per_job:
                raise ValueError("HTTP request budget exhausted; pending work retained")
            ident = self.db.execute("INSERT INTO fetch_attempts(job_id,origin,url,started_at,status) VALUES(?,?,?,?,?)", (job_id,origin,url,stamp,"reserved")).lastrowid
            self.db.commit()
            return ident
        except Exception:
            self.db.rollback()
            raise

    def flag(self, document_id, company, reason):
        company, reason = company.strip(), reason.strip()
        if not company or not reason or len(company)>200 or len(reason)>2000:
            raise ValueError("Company and evidence reason are required and must be bounded")
        if not self.db.execute("SELECT 1 FROM documents WHERE id=?", (document_id,)).fetchone():
            raise ValueError("Unknown evidence document")
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO leads(document_id,company,reason,created_at) VALUES(?,?,?,?)", (document_id,company,reason,now()))
            return self.db.execute("SELECT id FROM leads WHERE document_id=? AND company=?", (document_id,company)).fetchone()[0]

    def begin_qualification(self, lead_id):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT status FROM leads WHERE id=?", (lead_id,)).fetchone()
            if row is None:
                raise ValueError("Unknown lead")
            if row[0] not in ("flagged","qualification_in_progress"):
                raise ValueError("Lead is not eligible for qualification")
            if row[0] == "flagged":
                self.db.execute("UPDATE leads SET status='qualification_in_progress' WHERE id=?", (lead_id,))
                self.db.execute("INSERT INTO transitions(lead_id,previous_status,next_status,created_at) VALUES(?,?,?,?)", (lead_id,"flagged","qualification_in_progress",now()))
            self.db.execute("INSERT OR IGNORE INTO enrichment_queue(lead_id,created_at) VALUES(?,?)", (lead_id,now()))
            self.db.commit()
            return dict(self.db.execute("SELECT * FROM enrichment_queue WHERE lead_id=?", (lead_id,)).fetchone())
        except Exception:
            self.db.rollback()
            raise

    def enrichment_tasks(self):
        # Defense in depth: a task is actionable only during qualification.
        return self.rows("""SELECT q.*,l.company,l.reason,l.document_id FROM enrichment_queue q
          JOIN leads l ON l.id=q.lead_id WHERE l.status='qualification_in_progress'
          AND q.status='pending' ORDER BY q.id""")

    def coverage(self):
        return {"sources":self.rows("SELECT * FROM sources ORDER BY id"),
                "jobs":self.rows("SELECT * FROM jobs ORDER BY id DESC LIMIT 30"),
                "attempts":self.rows("SELECT id,job_id,url,status,detail,started_at FROM fetch_attempts ORDER BY id DESC LIMIT 50"),
                "documents":self.db.execute("SELECT COUNT(*) FROM documents").fetchone()[0],
                "leads":self.rows("SELECT * FROM leads ORDER BY id DESC"),
                "enrichment_tasks":self.enrichment_tasks()}
