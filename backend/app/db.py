"""
SQLite metadata + FAISS vector storage (singleton style).
---------------------------------------------------------
• Uses IndexIDMap + IndexFlatIP  ➜  allows add_with_ids()
• Stores vectors as L2-normalised float32
• Guarantees unique vector_ids even after deletions
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Tuple

import faiss
import numpy as np

from . import config  # expects .VECTOR_DIM, .INDEX_PATH, .DB_PATH

# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _l2_normalize(vectors: List[List[float]]) -> np.ndarray:
    """Return L2-normalised float32 ndarray (n_samples, dim)."""
    arr = np.asarray(vectors, dtype="float32")
    norms = np.linalg.norm(arr, axis=1, keepdims=True) + 1e-10
    return arr / norms

def _init_index() -> faiss.IndexIDMap:
    """Load existing FAISS index or create a new one (IDMap + FlatIP)."""
    if config.INDEX_PATH.exists():
        idx = faiss.read_index(str(config.INDEX_PATH))
        # Older on-disk indexes might be bare IndexFlatIP; wrap if needed
        if not isinstance(idx, faiss.IndexIDMap):
            idx = faiss.IndexIDMap(idx)
        return idx
    return faiss.IndexIDMap(faiss.IndexFlatIP(config.VECTOR_DIM))

def _next_free_vector_id(sql_conn: sqlite3.Connection) -> int:
    """Find the first unused integer vector_id."""
    row = sql_conn.execute("SELECT COALESCE(MAX(vector_id), -1) FROM chunks").fetchone()
    return int(row[0]) + 1


# ------------------------------------------------------------------ #
# Initialise FAISS + SQLite
# ------------------------------------------------------------------ #

index: faiss.IndexIDMap = _init_index()

conn = sqlite3.connect(config.DB_PATH)
conn.execute(
    """CREATE TABLE IF NOT EXISTS resumes (
         resume_id        TEXT PRIMARY KEY,
         name             TEXT,
         email            TEXT,
         skills           TEXT,
         years_experience INTEGER,
         version          INTEGER DEFAULT 1
       )"""
)
conn.execute(
    """CREATE TABLE IF NOT EXISTS chunks (
         vector_id INTEGER PRIMARY KEY,
         resume_id TEXT,
         text      TEXT
       )"""
)
conn.commit()

_next_id: int = _next_free_vector_id(conn)  # guaranteed unique

# ------------------------------------------------------------------ #
# Core API
# ------------------------------------------------------------------ #

def save_index() -> None:
    faiss.write_index(index, str(config.INDEX_PATH))


def insert_resume(
    meta: Dict[str, Any],
    chunks: List[str],
    embeddings: List[List[float]],
) -> None:
    """Insert *or* replace a resume and its vector chunks atomically."""
    global _next_id

    if len(chunks) != len(embeddings):
        raise ValueError("chunks and embeddings must have identical length")

    # --- upsert resume metadata ---
    conn.execute(
        """
        INSERT INTO resumes (resume_id, name, email, skills, years_experience, version)
        VALUES (?,?,?,?,?,
                COALESCE((SELECT version FROM resumes WHERE resume_id = ?)+1, 1)
        )
        ON CONFLICT(resume_id) DO UPDATE SET
            name             = excluded.name,
            email            = excluded.email,
            skills           = excluded.skills,
            years_experience = excluded.years_experience,
            version          = resumes.version + 1
        """,
        (
            meta["resume_id"],
            meta["name"],
            meta["email"],
            json.dumps(meta["skills"]),
            meta["years_experience"],
            meta["resume_id"],
        ),
    )

    # --- vectors ---
    vec_ids = np.arange(_next_id, _next_id + len(chunks), dtype="int64")
    index.add_with_ids(_l2_normalize(embeddings), vec_ids)

    conn.executemany(
        "INSERT INTO chunks (vector_id, resume_id, text) VALUES (?,?,?)",
        [(int(v_id), meta["resume_id"], txt) for v_id, txt in zip(vec_ids, chunks)],
    )

    _next_id += len(chunks)
    conn.commit()
    save_index()


def delete_resume(resume_id: str) -> None:
    """Remove a resume & its vectors; vacuum IDs from the FAISS index."""
    vec_ids = [
        r[0]
        for r in conn.execute(
            "SELECT vector_id FROM chunks WHERE resume_id = ?", (resume_id,)
        )
    ]
    if vec_ids:
        index.remove_ids(np.asarray(vec_ids, dtype="int64"))

    conn.execute("DELETE FROM chunks  WHERE resume_id = ?", (resume_id,))
    conn.execute("DELETE FROM resumes WHERE resume_id = ?", (resume_id,))
    conn.commit()
    save_index()


def fetch_meta(resume_id: str) -> Dict[str, Any] | None:
    row = conn.execute(
        "SELECT name, skills, years_experience FROM resumes WHERE resume_id = ?",
        (resume_id,),
    ).fetchone()
    if not row:
        return None
    name, skills_json, years_exp = row
    return {
        "name": name,
        "skills": json.loads(skills_json),
        "years_experience": years_exp,
    }


def search_vectors(query_vec, top_k: int = 10):
    """
    Accept list, list-of-lists **or** np.ndarray and return
    [(score, vector_id), …].
    """
    if isinstance(query_vec, np.ndarray):
        q = _l2_normalize(query_vec if query_vec.ndim == 2 else [query_vec])
    elif isinstance(query_vec, list) and query_vec:
        q = _l2_normalize(query_vec if isinstance(query_vec[0], list) else [query_vec])
    else:
        raise ValueError("query_vec must be a 1-D/2-D ndarray or a non-empty list")

    if index.ntotal == 0:
        return []

    try:
        distances, ids = index.search(q, k=min(top_k, index.ntotal))
        return [
            (float(distances[0][i]), int(ids[0][i]))
            for i in range(len(ids[0])) if ids[0][i] != -1
        ]
    except Exception as e:
        print(f"Error in search_vectors: {e}")
        return []

def vector_to_resume(vector_id: int) -> str:
    """Map FAISS vector_id → resume_id (fast path)."""
    row = conn.execute("SELECT resume_id FROM chunks WHERE vector_id=?", (vector_id,)).fetchone()
    return row[0] if row else ""


def index_size() -> int:
    """Return the number of vectors in the index."""
    return index.ntotal


def get_all_resume_ids() -> List[str]:
    """Get all resume IDs in the database."""
    rows = conn.execute("SELECT resume_id FROM resumes").fetchall()
    return [row[0] for row in rows]


def get_chunks_for_resume(resume_id: str) -> List[Tuple[int, str]]:
    """Get all chunks (vector_id, text) for a given resume."""
    rows = conn.execute(
        "SELECT vector_id, text FROM chunks WHERE resume_id = ? ORDER BY vector_id", 
        (resume_id,)
    ).fetchall()
    return [(row[0], row[1]) for row in rows]


def search_by_metadata(
    skills: List[str] = None,
    min_years: int = None,
    max_years: int = None,
    name_pattern: str = None
) -> List[str]:
    """Search resumes by metadata filters only (no vector search)."""
    clauses = []
    params = []
    
    if skills:
        skill_conditions = []
        for skill in skills:
            skill_conditions.append("skills LIKE ?")
            params.append(f"%{skill.lower()}%")
        clauses.append(f"({' OR '.join(skill_conditions)})")
    
    if min_years is not None:
        clauses.append("years_experience >= ?")
        params.append(min_years)
    
    if max_years is not None:
        clauses.append("years_experience <= ?")
        params.append(max_years)
    
    if name_pattern:
        clauses.append("name LIKE ?")
        params.append(f"%{name_pattern}%")
    
    where_clause = " AND ".join(clauses) if clauses else "1=1"
    query = f"SELECT resume_id FROM resumes WHERE {where_clause}"
    
    rows = conn.execute(query, params).fetchall()
    return [row[0] for row in rows]