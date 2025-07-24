# app/embedder.py
from __future__ import annotations

import uuid
import logging
from typing import List
import tempfile
import os

from fastapi import UploadFile, HTTPException
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from docx import Document
# --- MODIFIED: Use the new OpenAI client ---
from openai import AsyncOpenAI, OpenAIError, RateLimitError

from . import config

# Configure logging
logger = logging.getLogger(__name__)

# --- MODIFIED: Initialize the new AsyncOpenAI client ---
try:
    client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
    logger.info("AsyncOpenAI client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize AsyncOpenAI client: {e}")
    raise RuntimeError(f"AsyncOpenAI client initialization failed: {e}")

_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=200)

# ---------- parsing ----------
def parse_resume(upload: UploadFile) -> str:
    """Extract text from an uploaded PDF or DOC/DOCX with the corrected file handling."""
    fname = upload.filename.lower() if upload.filename else ""
    
    if fname.endswith(".pdf"):
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
                content = upload.file.read()
                tmp_file.write(content)
                tmp_path = tmp_file.name

            loader = PyPDFLoader(tmp_path)
            pages = loader.load()
            text = "\n".join(p.page_content for p in pages)
            
            if not text.strip():
                raise HTTPException(400, "PDF appears to be empty or text could not be extracted")
            
            return text
        except Exception as e:
            logger.error(f"PDF parsing error: {e}")
            raise HTTPException(400, f"Error parsing PDF: {str(e)}")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
            upload.file.seek(0)

    elif fname.endswith((".doc", ".docx")):
        try:
            upload.file.seek(0)
            doc = Document(upload.file)
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            
            if not text.strip():
                raise HTTPException(400, "Document appears to be empty")
            
            return text
        except Exception as e:
            logger.error(f"DOCX parsing error: {e}")
            raise HTTPException(400, f"Error parsing document: {str(e)}")
    else:
        raise HTTPException(400, "Only PDF and DOCX files are supported")


# ---------- helpers ----------
def chunk_text(text: str) -> List[str]:
    """Split text into chunks with validation."""
    if not text or not text.strip():
        return []
    
    try:
        chunks = _splitter.split_text(text)
        chunks = [chunk for chunk in chunks if len(chunk.strip()) > 20]
        return chunks
    except Exception as e:
        logger.error(f"Error chunking text: {e}")
        raise HTTPException(500, f"Error processing text: {str(e)}")

# --- MODIFIED: Updated to use the new async client and syntax ---
async def embed_texts(texts: List[str]) -> List[List[float]]:
    """Return OpenAI ada-002 embeddings for a list of strings with retry logic."""
    if not texts:
        return []
    
    texts = [text.strip() for text in texts if text and text.strip()]
    if not texts:
        return []

    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"Generating embeddings for {len(texts)} texts (attempt {attempt + 1})")

            response = await client.embeddings.create(
                model=config.EMBEDDING_MODEL,
                input=texts
            )
            embeddings = [item.embedding for item in response.data]
            logger.info(f"Successfully generated {len(embeddings)} embeddings")
            return embeddings

        except RateLimitError as e:
            logger.warning(f"Rate limit hit: {e}")
            if attempt < max_retries - 1:
                import time
                time.sleep(2 ** attempt)
                continue
            raise HTTPException(429, "OpenAI rate limit exceeded.")
        
        except OpenAIError as e:
            logger.error(f"OpenAI API error: {e}")
            if attempt < max_retries - 1:
                import time
                time.sleep(1)
                continue
            raise HTTPException(502, f"OpenAI API error: {str(e)}")

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            if attempt < max_retries - 1:
                import time
                time.sleep(1)
                continue
            raise HTTPException(500, f"Error generating embeddings: {str(e)}")
    
    raise HTTPException(500, "Failed to generate embeddings after multiple attempts")


def build_meta(name: str, email: str, skills: List[str], years: int) -> dict:
    """Build metadata dictionary with validation."""
    try:
        name = name.strip() if name else "Unknown"
        email = email.strip() if email else "unknown@example.com"
        skills = [skill.strip() for skill in skills if skill and skill.strip()]
        years = max(0, int(years)) if years is not None else 0
        
        return {
            "resume_id": str(uuid.uuid4()),
            "name": name,
            "email": email,
            "skills": skills,
            "years_experience": years,
        }
    except Exception as e:
        logger.error(f"Error building metadata: {e}")
        raise HTTPException(500, f"Error processing metadata: {str(e)}")

# --- MODIFIED: Updated to use the new async client ---
async def check_openai_connection() -> bool:
    """Check if OpenAI API is accessible."""
    try:
        await client.embeddings.create(
            model=config.EMBEDDING_MODEL,
            input=["test"]
        )
        return True
    except Exception as e:
        logger.error(f"OpenAI connection check failed: {e}")
        return False
