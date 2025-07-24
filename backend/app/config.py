from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv() 
# DATA_DIR = Path(__file__).resolve().parent.parent / "data"
# DATA_DIR.mkdir(exist_ok=True)
# INDEX_PATH = DATA_DIR / "index.faiss"
# DB_PATH = DATA_DIR / "resumes.db"

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://cvuser:1!&rR1t4N22%C2%A3@88.222.242.195:27017/hr_cv_search_dev")
MONGO_DATABASE = "hr_cv_search_dev"
MONGO_COLLECTION = "resumes"

# --- Qdrant Config ---
QDRANT_URL = "https://d6057bf7-4166-4182-9bb2-b8b25d990ce8.eu-central-1-0.aws.cloud.qdrant.io"
QDRANT_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.jIAnmBn3_I_OHyXLNFuzB22qC9c0NK7UoULsjZ-ju-U"
QDRANT_COLLECTION_NAME = "resumes_prod"

EMBEDDING_MODEL = "text-embedding-ada-002"
VECTOR_DIM = 1536  # ada-002 size
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("Set OPENAI_API_KEY in env variables")