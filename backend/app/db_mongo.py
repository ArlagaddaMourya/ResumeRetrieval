"""
MongoDB data access layer using motor for async operations.
Replaces the previous SQLite and FAISS implementation.
"""
from __future__ import annotations
from typing import Any, Dict, List, Tuple
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
# --- ADDED: Import GridFS components ---
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
import io
from gridfs.errors import NoFile
import logging
from . import config
import re
logger = logging.getLogger(__name__)

# --- MongoDB Client Setup ---
client: AsyncIOMotorClient | None = None
db: AsyncIOMotorDatabase | None = None
# --- GridFS bucket instance ---
fs: AsyncIOMotorGridFSBucket | None = None

def get_db():
    """Returns the database instance's resume collection."""
    if db is None:
        raise RuntimeError("Database not initialized. Call connect_to_mongo first.")
    return db.get_collection(config.MONGO_COLLECTION)

async def connect_to_mongo():
    """Connect to MongoDB and initialize GridFS."""
    global client, db, fs # --- Added fs to globals
    logger.info("Connecting to MongoDB...")
    client = AsyncIOMotorClient(config.MONGO_URI)
    db = client[config.MONGO_DATABASE]
    # --- Initialize the GridFS bucket ---
    fs = AsyncIOMotorGridFSBucket(db, bucket_name="resume_files")
    
    try:
        await client.admin.command('ping')
        logger.info("✅ MongoDB and GridFS connection successful.")
    except Exception as e:
        logger.error(f"❌ MongoDB connection failed: {e}")
        raise

async def close_mongo_connection():
    """Close MongoDB connection."""
    global client
    if client:
        client.close()
        logger.info("MongoDB connection closed.")


# --- Core API ---

# --- The function now accepts file content to store in GridFS ---
async def insert_resume(meta: Dict[str, Any], full_text: str, filename: str, file_content: bytes) -> None:
    """
    Insert a new resume document and its file content into GridFS.
    """
    resume_id = meta["resume_id"]
    
    # --- Create a memory-based stream from the file content ---
    source_stream = io.BytesIO(file_content)

    # 1. Store the file in GridFS using the memory-based stream
    await fs.upload_from_stream_with_id(
        resume_id,
        filename,
        source_stream # <-- Pass the BytesIO stream here
    )
    logger.info(f"Stored file for resume {resume_id} in GridFS.")

    # 2. Store the metadata in the resumes collection
    resume_doc = {
        "_id": resume_id,
        "name": meta["name"],
        "email": meta["email"],
        "skills": meta["skills"],
        "years_experience": meta["years_experience"],
        "original_filename": filename,
        "full_text": full_text
    }
    
    collection = get_db()
    await collection.insert_one(resume_doc)
    logger.info(f"Inserted metadata for resume {resume_id} into MongoDB.")

async def delete_resume(resume_id: str) -> int:
    """Delete a resume's metadata and its file from GridFS."""
    collection = get_db()
    
    # --- ADDED: Delete the file from GridFS first ---
    await fs.delete(resume_id)
    logger.info(f"Deleted file for resume {resume_id} from GridFS.")

    # Delete the metadata document
    result = await collection.delete_one({"_id": resume_id})
    return result.deleted_count

# --- ADDED: A new function to retrieve a file stream from GridFS ---
async def get_resume_file_stream(resume_id: str):
    """Opens a download stream for a file stored in GridFS."""
    try:
        grid_out = await fs.open_download_stream(resume_id)
        return grid_out
    except NoFile:
        return None

async def fetch_meta(resume_id: str) -> Dict[str, Any] | None:
    """Fetch resume metadata (excluding large text fields)."""
    collection = get_db()
    projection = {"full_text": 0} 
    doc = await collection.find_one({"_id": resume_id}, projection)
    return doc

async def get_total_resumes() -> int:
    """Get the total count of resumes in the database."""
    collection = get_db()
    return await collection.count_documents({})

async def fetch_resumes_by_ids(resume_ids: List[str]) -> List[Dict[str, Any]]:
    """Fetch multiple resumes by their _id, excluding large fields for brevity."""
    if not resume_ids:
        return []
    collection = get_db()
    projection = {"full_text": 0}
    cursor = collection.find({"_id": {"$in": resume_ids}}, projection)
    return await cursor.to_list(length=len(resume_ids))