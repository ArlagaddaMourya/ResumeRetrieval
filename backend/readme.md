"""
Prototype: **Local‑only Resume Search Assistant**
==============================================

This is a **proof‑of‑concept** that runs 100 % on your laptop – no Docker, no external DBs.

---
### 📂 Recommended Folder Structure
```
resume-search-prototype/
├── app/
│   └── resume_search_local.py   # ← the FastAPI server (this file)
├── data/                        # FAISS index & SQLite DB created here at runtime
├── requirements.txt             # Python deps listed below
├── README.md                    # Quick‑start guide (optional)
└── sample_resumes/              # Put a few PDFs/DOCXs here for testing (optional)
```
*Run from the project root with:*  
`uvicorn app.resume_search_local:app --reload`

---
### 🪄 What It Does
* **Ingest** single resumes via `/upload` or a ZIP via `/batch_upload`.
* **Embeds** chunks with OpenAI `text-embedding-ada-002`.
* **Stores** vectors in a local **FAISS** index (`data/index.faiss`) and metadata in **SQLite** (`data/resumes.db`).
* **Searches** in real‑time through `/search` with optional filters (`skill_filter`, `min_years`).
* **Upserts** existing resumes through `/upsert` (deletes old vectors, inserts new).  

---
### 🛠️ requirements.txt  
```
fastapi
uvicorn[standard]
openai==1.23.0
langchain==0.2.0
langchain-community==0.0.34
pdfminer.six==20221105
python-docx==1.1.0
python-multipart
faiss-cpu==1.7.4
python-dotenv
```

---
### 🚀 Quick Start  
```bash
# 1 – clone & cd into the repo
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="sk-..."
uvicorn app.resume_search_local:app --reload
# POST /upload or /batch_upload to http://127.0.0.1:8000
```

Data lives entirely in `./data/`, so deleting that folder resets the prototype.
"""
