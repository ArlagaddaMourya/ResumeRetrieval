from typing import List, Optional, Dict, Any
from fastapi.middleware.cors import CORSMiddleware
import logging
import json
import zipfile
import tempfile
import pathlib
from contextlib import asynccontextmanager
import shutil
from fastapi import FastAPI, File, UploadFile, Form, Query, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from . import qdrant_db
# Use the new MongoDB data access layer
from . import embedder, utils, query_parser
from . import db_mongo as db 

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UPLOADS_DIR = pathlib.Path(__file__).resolve().parent.parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)


# --- MODIFIED LIFESPAN MANAGER ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage MongoDB connection on startup and shutdown."""
    logger.info("▶️  Starting Resume Search API")
    await db.connect_to_mongo()
    await qdrant_db.setup_collection()
    if not await embedder.check_openai_connection():
        logger.warning("OpenAI check failed – embeddings may not work")
    yield
    logger.info("⏹️  Shutting down API")
    await db.close_mongo_connection()
    

app = FastAPI(title="Resume Search API v2 (MongoDB)", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # THIS IS THE CRITICAL LINE YOU NEED TO ADD
    expose_headers=["Content-Disposition"],
)

# ---------- HEALTH CHECK ----------

@app.get("/health")
async def health_check():
    """Health check endpoint for MongoDB, Qdrant, and OpenAI."""
    db_ok = False
    total_resumes = 0
    try:
        await db.client.admin.command('ping')
        db_ok = True
        total_resumes = await db.get_total_resumes()
    except Exception as e:
        logger.error(f"MongoDB health check failed: {e}")
        db_ok = False

    qdrant_ok = True
    # MODIFIED: Await the async check
    openai_ok = await embedder.check_openai_connection()
    
    status = "healthy" if db_ok and openai_ok and qdrant_ok else "degraded"

    return {
        "status": status,
        "database_mongo": "ok" if db_ok else "error",
        "database_qdrant": "ok" if qdrant_ok else "error",
        "openai_api": "ok" if openai_ok else "error",
        "total_resumes_in_db": total_resumes,
    }


# ---------- ENHANCED ROUTES ----------

@app.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    name:  Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    skills: Optional[str] = Form(None),
    years_experience: Optional[int] = Form(None, ge=0, le=50),
):
    try:
        if not file.filename:
            raise HTTPException(400, "No file selected")
        if pathlib.Path(file.filename).suffix.lower() not in {".pdf", ".docx", ".doc"}:
            raise HTTPException(400, "Only PDF/DOCX files are accepted")

        # --- MODIFIED: Read the file content into a bytes object first ---
        file_content = await file.read()
        
        # Reset file pointer for parsing
        await file.seek(0) 

        text = embedder.parse_resume(file)
        if email is None: email = utils.extract_email(text) or "unknown@example.com"
        if skills is None: parsed_skills = utils.extract_skills(text)
        else:
            try: parsed_skills = json.loads(skills)
            except Exception: parsed_skills = [s.strip().lower() for s in skills.split(",") if s.strip()]
        if years_experience is None: years_experience = utils.estimate_years_experience(text)
        if name is None: name = utils.guess_name(file.filename, email)

        chunks = embedder.chunk_text(text)
        if not chunks:
            raise HTTPException(400, "Resume contains no usable text")

        embeds = await embedder.embed_texts(chunks)
        meta = embedder.build_meta(name=name, email=email, skills=parsed_skills, years=years_experience)

        # --- MODIFIED: Pass the `file_content` bytes, not the `file` object ---
        await db.insert_resume(meta, text, file.filename, file_content)
        
        await qdrant_db.upsert_resume_vectors(meta['resume_id'], chunks, embeds)
        
        logger.info(f"✅ Stored resume {meta['resume_id']} in Mongo and GridFS.")
        return {"resume_id": meta["resume_id"], "name": meta["name"], "chunks": len(chunks)}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Upload failed")
        raise HTTPException(500, f"Internal error: {e}")

@app.post("/batch_upload")
async def batch_upload(zip_file: UploadFile = File(...)):
    """Batch upload resumes from a ZIP file with improved error handling."""
    if not zip_file.filename or not zip_file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "Upload a .zip file containing PDFs/DOCXs.")

    processed = 0
    errors = []
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = pathlib.Path(tmpdir)
            
            try:
                with zipfile.ZipFile(zip_file.file) as z:
                    z.extractall(tmp_path)
            except zipfile.BadZipFile:
                raise HTTPException(400, "Invalid ZIP file")
            
            for p in tmp_path.rglob("*"):
                if p.suffix.lower() in (".pdf", ".docx", ".doc"):
                    try:
                        with open(p, "rb") as f:
                            fake_file = UploadFile(filename=p.name, file=f)
                            
                            await upload_resume(
                                fake_file,
                                name=p.stem,
                                email=f"{p.stem}@example.com",
                                skills="[]",
                                years_experience=0,
                            )
                        processed += 1
                        logger.info(f"Processed file: {p.name}")
                        
                    except Exception as e:
                        error_msg = f"Error processing {p.name}: {str(e)}"
                        errors.append(error_msg)
                        logger.error(error_msg)
                        continue
        
        result = {
            "processed": processed,
            "total_files": len([p for p in tmp_path.rglob("*") if p.suffix.lower() in (".pdf", ".docx", ".doc")]),
        }
        
        if errors:
            result["errors"] = errors[:10]
            result["error_count"] = len(errors)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch upload error: {e}")
        raise HTTPException(500, f"Batch upload failed: {str(e)}")

@app.post("/upsert")
async def upsert_resume(
    resume_id: str = Form(...),
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    skills: Optional[str] = Form(None),
    years_experience: Optional[int] = Form(None, ge=0),
):
    """Update an existing resume by replacing it."""
    try:
        existing_meta = await db.fetch_meta(resume_id)
        if not existing_meta:
            raise HTTPException(404, f"Resume with ID {resume_id} not found")
        
        text = embedder.parse_resume(file)
        chunks = embedder.chunk_text(text)
        if not chunks:
            raise HTTPException(400, "No text extracted from the updated file.")
        
        # MODIFIED: Await the async embed_texts call
        embeddings = await embedder.embed_texts(chunks)
        
        if skills:
            try:
                parsed_skills = json.loads(skills)
            except json.JSONDecodeError:
                parsed_skills = [s.strip().lower() for s in skills.split(",") if s.strip()]
        else:
            parsed_skills = existing_meta.get("skills", [])
        
        meta = embedder.build_meta(
            name=(name or existing_meta.get("name", "Unknown")),
            email=(email or existing_meta.get("email", "unknown@example.com")),
            skills=parsed_skills,
            years=(years_experience if years_experience is not None else existing_meta.get("years_experience", 0)),
        )
        meta['resume_id'] = resume_id

        await db.delete_resume(resume_id)
        await qdrant_db.delete_vectors_for_resume(resume_id)
        
        await db.insert_resume(meta, text, file.filename, file_content)
        await qdrant_db.upsert_resume_vectors(meta['resume_id'], chunks, embeddings)
        
        logger.info(f"Updated resume {resume_id} in both stores")
        return {"message": f"Resume {resume_id} updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating resume {resume_id}: {e}")
        raise HTTPException(500, f"Failed to update resume: {str(e)}")


@app.delete("/resume/{resume_id}")
async def delete_resume(resume_id: str):
    """Delete a resume from MongoDB, Qdrant, and GridFS."""
    try:
        # The modified db.delete_resume now handles GridFS deletion
        deleted_count = await db.delete_resume(resume_id) 
        if deleted_count == 0:
            raise HTTPException(404, f"Resume with ID {resume_id} not found")
        
        await qdrant_db.delete_vectors_for_resume(resume_id)
        
        # --- REMOVED: No longer deleting from local filesystem ---
        # for ext in ['.pdf', '.docx', '.doc']:
        #     file_path = UPLOADS_DIR / f"{resume_id}{ext}"
        #     if file_path.exists():
        #         file_path.unlink()
        #         break
                
        logger.info(f"Deleted resume {resume_id} from all stores.")
        return {"message": f"Resume {resume_id} deleted successfully"}
        
    except Exception as e:
        logger.error(f"Error deleting resume {resume_id}: {e}")
        raise HTTPException(500, f"Failed to delete resume: {str(e)}")
@app.get("/resume/{resume_id}/file")
async def get_resume_file(resume_id: str):
    """Serves the original resume file from GridFS for preview or download."""
    meta = await db.fetch_meta(resume_id)
    if not meta or not meta.get("original_filename"):
         raise HTTPException(status_code=404, detail="File metadata not found for this resume.")
    
    # --- MODIFIED: Fetch stream from GridFS instead of local path ---
    grid_fs_stream = await db.get_resume_file_stream(resume_id)
    if not grid_fs_stream:
        logger.error(f"File not found in GridFS for resume {resume_id}")
        raise HTTPException(status_code=404, detail="Original resume file not found in storage.")
    
    original_filename = meta["original_filename"]
    file_extension = pathlib.Path(original_filename).suffix.lower()

    media_types = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
    }
    media_type = media_types.get(file_extension, "application/octet-stream")

    # --- MODIFIED: Use StreamingResponse to efficiently send the file ---
    return StreamingResponse(
        grid_fs_stream,
        media_type=media_type,
        headers={
            "Content-Disposition": f"inline; filename=\"{original_filename}\""
        }
    )
@app.get("/stats")
async def get_stats():
    """Get system statistics from MongoDB."""
    try:
        collection = db.get_db()
        
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_resumes": {"$sum": 1},
                    "avg_years": {"$avg": "$years_experience"},
                    "min_years": {"$min": "$years_experience"},
                    "max_years": {"$max": "$years_experience"}
                }
            }
        ]
        stats_result = await collection.aggregate(pipeline).to_list(length=1)

        if not stats_result:
            return { "message": "No resumes found in the database." }

        stats = stats_result[0]

        qdrant_client = qdrant_db.get_qdrant_client()
        collection_info = qdrant_client.get_collection(collection_name=config.QDRANT_COLLECTION_NAME)
        total_chunks = collection_info.vectors_count

        return {
            "total_resumes": stats.get("total_resumes", 0),
            "total_chunks_indexed": total_chunks,
            "avg_years_experience": round(stats.get("avg_years", 0), 1),
            "min_years_experience": stats.get("min_years", 0),
            "max_years_experience": stats.get("max_years", 0),
        }
        
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(500, f"Failed to get stats: {str(e)}")

@app.get("/nl_search")
async def natural_language_search(
    query: str = Query(..., min_length=1, description="Natural language query for candidates"),
    top_k: int = Query(10, ge=1, le=50, description="Number of results to return"),
):
    """
    Performs a hybrid search using Qdrant for vectors and MongoDB for metadata.
    """
    try:
        logger.info(f"NL search: {query!r} with top_k={top_k}")

        # --- MODIFIED: Await the async functions ---
        filters = await query_parser.parse(query) or {}
        logger.info(f"Parsed filters: {filters}")

        q_embedding = (await embedder.embed_texts([query]))[0]
        
        qdrant_results = await qdrant_db.search_vectors(q_embedding, filters, top_k * 2)
        if not qdrant_results:
            return JSONResponse(content=[])

        ordered_resume_ids = [res['resume_id'] for res in qdrant_results]
        scores_map = {res['resume_id']: res['score'] for res in qdrant_results}

        mongo_docs = await db.fetch_resumes_by_ids(ordered_resume_ids)

        final_results = []
        for doc in mongo_docs:
            if (min_y := filters.get("min_years")) and doc.get("years_experience", 0) < min_y:
                continue
            if (max_y := filters.get("max_years")) and doc.get("years_experience", 0) > max_y:
                continue
            if (req_skills := filters.get("skills")):
                mode = filters.get("skills_mode", "any")
                doc_skills = set(doc.get("skills", []))
                if mode == "all" and not set(req_skills).issubset(doc_skills):
                    continue
                if mode == "any" and not set(req_skills).intersection(doc_skills):
                    continue

            doc['search_score'] = scores_map.get(doc['_id'], 0.0)
            final_results.append(doc)

        final_results.sort(key=lambda x: x.get('search_score', 0.0), reverse=True)
        
        logger.info(f"NL search returned {len(final_results[:top_k])} results")
        return JSONResponse(content=final_results[:top_k])
        
    except Exception as e:
        logger.exception(f"Natural language search error")
        raise HTTPException(500, f"Natural language search failed: {str(e)}")

    
