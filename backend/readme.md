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
aiohappyeyeballs==2.6.1
aiohttp==3.12.14
aiosignal==1.4.0
annotated-types==0.7.0
anyio==4.9.0
attrs==25.3.0
certifi==2025.7.14
charset-normalizer==3.4.2
click==8.2.1
colorama==0.4.6
dataclasses-json==0.6.7
distro==1.9.0
dnspython==2.7.0
fastapi==0.116.1
frozenlist==1.7.0
greenlet==3.2.3
grpcio==1.73.1
h11==0.16.0
h2==4.2.0
hpack==4.1.0
httpcore==1.0.9
httptools==0.6.4
httpx==0.28.1
hyperframe==6.1.0
idna==3.10
jiter==0.10.0
jsonpatch==1.33
jsonpointer==3.0.0
langchain==0.1.16
langchain-community==0.0.35
langchain-core==0.1.49
langchain-text-splitters==0.0.2
langsmith==0.1.147
lxml==6.0.0
marshmallow==3.26.1
motor==3.7.1
multidict==6.6.3
mypy_extensions==1.1.0
numpy==1.26.4
openai==1.97.1
orjson==3.11.0
packaging==23.2
portalocker==3.2.0
propcache==0.3.2
protobuf==6.31.1
pydantic==2.11.7
pydantic_core==2.33.2
pymongo==4.13.2
pypdf==5.8.0
python-docx==1.2.0
python-dotenv==1.1.1
python-multipart==0.0.20
PyYAML==6.0.2
qdrant-client==1.15.0
requests==2.32.4
requests-toolbelt==1.0.0
sniffio==1.3.1
SQLAlchemy==2.0.41
starlette==0.47.2
tenacity==8.5.0
tqdm==4.67.1
typing_extensions==4.14.1
typing-inspect==0.9.0
typing-inspection==0.4.1
urllib3==2.5.0
uvicorn==0.35.0
watchfiles==1.1.0
websockets==15.0.1
yarl==1.20.1
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
