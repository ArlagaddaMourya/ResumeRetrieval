# qdrant_db.py

import logging
from typing import List, Dict, Any
import uuid

from qdrant_client import QdrantClient, AsyncQdrantClient, models
from qdrant_client.http.models import UpdateStatus

from . import config

logger = logging.getLogger(__name__)

# --- Qdrant Client Setup ---
client = None

def get_qdrant_client():
    """Initializes and returns the Qdrant client."""
    global client
    if client is None:
        logger.info(f"Initializing Qdrant client for host: {config.QDRANT_URL}")
        client = AsyncQdrantClient(
            url=config.QDRANT_URL,
            api_key=config.QDRANT_API_KEY,
            )
    return client

async def setup_collection():
    """Ensures the Qdrant collection exists and is configured correctly."""
    qdrant = get_qdrant_client()
    try:
        await qdrant.get_collection(collection_name=config.QDRANT_COLLECTION_NAME)
        logger.info(f"Qdrant collection '{config.QDRANT_COLLECTION_NAME}' already exists.")
    except Exception:
        logger.info(f"Creating Qdrant collection '{config.QDRANT_COLLECTION_NAME}'")
        await qdrant.recreate_collection(
            collection_name=config.QDRANT_COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=config.VECTOR_DIM,
                distance=models.Distance.COSINE
            ),
        )
        await qdrant.create_payload_index(
            collection_name=config.QDRANT_COLLECTION_NAME,
            field_name="resume_id",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )


async def upsert_resume_vectors(resume_id: str, chunks: List[str], embeddings: List[List[float]]):
    """Upserts resume chunk vectors into Qdrant."""
    if not embeddings:
        return
    qdrant = get_qdrant_client()
    points = [
        models.PointStruct(
            id=str(uuid.uuid4()),  
            vector=embedding,
            payload={
                "resume_id": resume_id,
                "text_chunk": chunk[:200] + "..." if len(chunk) > 200 else chunk 
            }
        )
        for chunk, embedding in zip(chunks, embeddings)
    ]

    operation_info = await qdrant.upsert(
        collection_name=config.QDRANT_COLLECTION_NAME,
        wait=True,
        points=points
    )
    if operation_info.status != UpdateStatus.COMPLETED:
        logger.error(f"Qdrant upsert failed for resume {resume_id}")
    else:
        logger.info(f"Upserted {len(points)} vectors for resume {resume_id} to Qdrant.")


async def delete_vectors_for_resume(resume_id: str):
    """Deletes all vectors associated with a specific resume_id."""
    logger.info(f"Deleting vectors from Qdrant for resume_id: {resume_id}")
    qdrant = get_qdrant_client()
    await qdrant.delete(
        collection_name=config.QDRANT_COLLECTION_NAME,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="resume_id",
                        match=models.MatchValue(value=resume_id),
                    )
                ]
            )
        ),
    )

async def search_vectors(query_embedding: List[float], filters: Dict[str, Any], top_k: int) -> List[Dict[str, Any]]:
    """Performs a vector search in Qdrant and returns unique resume IDs with scores."""
    qdrant = get_qdrant_client()

    # Note: Qdrant filtering is done via its own filter model.
    # We will perform metadata filtering after retrieving from MongoDB for simplicity here,
    # but for production, you would map your filters to Qdrant's filter language.

    search_result = await qdrant.search(
        collection_name=config.QDRANT_COLLECTION_NAME,
        query_vector=query_embedding,
        limit=top_k,
        with_payload=True,
    )

    # Process results to get unique resume IDs and their highest score
    resume_scores = {}
    for scored_point in search_result:
        r_id = scored_point.payload['resume_id']
        if r_id not in resume_scores or scored_point.score > resume_scores[r_id]:
            resume_scores[r_id] = scored_point.score

    # Sort unique resumes by score
    sorted_resumes = sorted(resume_scores.items(), key=lambda item: item[1], reverse=True)

    return [{"resume_id": r_id, "score": score} for r_id, score in sorted_resumes]

async def get_collection_stats() -> Dict[str, Any]:
    """Retrieves statistics for the collection."""
    qdrant = get_qdrant_client()
    collection_info = await qdrant.get_collection(collection_name=config.QDRANT_COLLECTION_NAME)
    return {
        "total_chunks": collection_info.vectors_count
    }