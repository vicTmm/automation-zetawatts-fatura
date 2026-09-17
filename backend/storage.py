"""Persistência local SQLite ou PostgreSQL/Supabase, com revisão otimista."""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = """
CREATE TABLE IF NOT EXISTS zeta_documents (
    kind TEXT NOT NULL, id TEXT NOT NULL, version INTEGER NOT NULL,
    payload TEXT NOT NULL, PRIMARY KEY (kind, id)
);
CREATE TABLE IF NOT EXISTS zeta_revisions (
    kind TEXT NOT NULL, id TEXT NOT NULL, version INTEGER NOT NULL,
    payload TEXT NOT NULL, changed_at TEXT NOT NULL,
    PRIMARY KEY (kind, id, version)
);
"""


class ConflictError(ValueError):
    pass


class Store:
    def __init__(self, path=None, url=None):
        self.url = url if url is not None else os.getenv("DATABASE_URL", "")
        self.path = str(path or os.getenv("SQLITE_PATH", ROOT / "data" / "zeta.db"))

    @contextmanager
    def connect(self):
        if self.url:
            import psycopg
            from psycopg.rows import dict_row
            connection = psycopg.connect(self.url, row_factory=dict_row, prepare_threshold=None, connect_timeout=10)
        else:
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.path, timeout=15)
            connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def execute(self, connection, sql, params=()):
        return connection.execute(sql.replace("?", "%s") if self.url else sql, params)

    def initialize(self):
        with self.connect() as connection:
            for statement in SCHEMA.split(";"):
                if statement.strip():
                    connection.execute(statement)
            if self.url:
                connection.execute("ALTER TABLE zeta_documents ENABLE ROW LEVEL SECURITY")
                connection.execute("ALTER TABLE zeta_revisions ENABLE ROW LEVEL SECURITY")
                connection.execute("REVOKE ALL ON zeta_documents, zeta_revisions FROM anon, authenticated")

    @staticmethod
    def decode(row):
        return {**json.loads(row["payload"]), "version": row["version"]} if row else None

    def get(self, kind, key):
        with self.connect() as connection:
            row = self.execute(connection, "SELECT payload, version FROM zeta_documents WHERE kind=? AND id=?", (kind, key)).fetchone()
            return self.decode(row)

    def list(self, kind):
        with self.connect() as connection:
            rows = self.execute(connection, "SELECT payload, version FROM zeta_documents WHERE kind=? ORDER BY id", (kind,)).fetchall()
            return [self.decode(row) for row in rows]

    def put(self, kind, key, payload, expected_version):
        payload = {k: v for k, v in payload.items() if k != "version"}
        version = expected_version + 1
        serialized = json.dumps(payload, ensure_ascii=False)
        with self.connect() as connection:
            if expected_version == 0:
                result = self.execute(connection, "INSERT INTO zeta_documents(kind,id,version,payload) VALUES (?,?,?,?) ON CONFLICT(kind,id) DO NOTHING", (kind, key, version, serialized))
            else:
                result = self.execute(connection, "UPDATE zeta_documents SET payload=?,version=? WHERE kind=? AND id=? AND version=?", (serialized, version, kind, key, expected_version))
            if result.rowcount != 1:
                raise ConflictError("Este registro mudou em outra sessão. Recarregue antes de salvar para não sobrescrever dados.")
            self.execute(connection, "INSERT INTO zeta_revisions(kind,id,version,payload,changed_at) VALUES (?,?,?,?,?)", (kind, key, version, serialized, datetime.now(timezone.utc).isoformat()))
        return {**payload, "version": version}

    def import_documents(self, documents):
        added, skipped = 0, 0
        with self.connect() as connection:
            for kind, key, payload in documents:
                serialized = json.dumps(payload, ensure_ascii=False)
                result = self.execute(connection, "INSERT INTO zeta_documents(kind,id,version,payload) VALUES (?,?,1,?) ON CONFLICT(kind,id) DO NOTHING", (kind, key, serialized))
                if result.rowcount:
                    added += 1
                    self.execute(connection, "INSERT INTO zeta_revisions(kind,id,version,payload,changed_at) VALUES (?,?,1,?,?)", (kind, key, serialized, datetime.now(timezone.utc).isoformat()))
                else:
                    skipped += 1
        return {"added": added, "skipped": skipped}

