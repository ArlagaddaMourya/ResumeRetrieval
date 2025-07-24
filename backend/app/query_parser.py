# app/query_parser.py
from __future__ import annotations
from typing import Any, Dict, List
import logging
import json
import re
from openai import AsyncOpenAI, OpenAIError

from . import config

logger = logging.getLogger(__name__)

# --- Initialize the new AsyncOpenAI client ---
try:
    client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
except Exception as e:
    logger.error(f"Failed to initialize query_parser OpenAI client: {e}")
    # Don't raise, allow regex fallback
    client = None

_SCHEMA = {
    "type": "object",
    "properties": {
        "skills":      {"type": "array",  "items": {"type": "string"}},
        "skills_mode": {"type": "string", "enum": ["any", "all"], "default": "any"},
        "min_years":   {"type": "integer"},
        "max_years":   {"type": "integer"},
        "locations":   {"type": "array",  "items": {"type": "string"}},
        "keywords":    {"type": "array",  "items": {"type": "string"}}
    },
    "required": []
}

# Extended skill list for better matching
COMMON_SKILLS = {
    "python", "java", "javascript", "typescript", "react", "angular", "vue",
    "node", "nodejs", "go", "golang", "c++", "cpp", "c#", "csharp",
    "aws", "azure", "gcp", "google cloud", "docker", "kubernetes", "k8s",
    "sql", "mysql", "postgresql", "mongodb", "nosql", "redis",
    "html", "css", "php", "ruby", "scala", "kotlin", "swift",
    "tensorflow", "pytorch", "machine learning", "ml", "ai",
    "django", "flask", "spring", "express", "fastapi",
    "git", "jenkins", "terraform", "ansible", "helm"
}

# ---  Updated to be an async function ---
async def parse(query: str) -> Dict[str, Any]:
    """Return structured filters dict with improved AND/OR logic."""
    out: Dict[str, Any] = {}

    # ---------- Enhanced regex pass ----------

    # Years experience patterns
    m_ge = re.search(r'(?:more than|over|>\s*|at least|minimum|above)\s*(\d+)\s+years?', query, re.I)
    if m_ge:
        out["min_years"] = int(m_ge.group(1))

    m_le = re.search(r'(?:less than|under|below|<\s*|maximum|upto|up to)\s*(\d+)\s+years?', query, re.I)
    if m_le:
        out["max_years"] = int(m_le.group(1))

    # Exact years match
    m_exact = re.search(r'(?:exactly|with)\s*(\d+)\s+years?', query, re.I)
    if m_exact:
        years = int(m_exact.group(1))
        out["min_years"] = years
        out["max_years"] = years

    # Skills detection with AND/OR logic
    skills_found = []
    for skill in COMMON_SKILLS:
        # More flexible skill matching
        patterns = [
            rf"\b{re.escape(skill)}\b",
            rf"\b{re.escape(skill.replace(' ', ''))}\b",  # Handle "google cloud" -> "googlecloud"
        ]
        for pattern in patterns:
            if re.search(pattern, query, re.I):
                skills_found.append(skill)
                break

    if skills_found:
        out["skills"] = skills_found

        # Determine if it's AND or OR logic based on query patterns
        and_indicators = [
            r'\bwith\s+.*\band\b',      # "with X and Y"
            r'\band\b',                 # any "and"
            r',\s*and\b',               # "X, and Y"
            r'\bwho\s+have\s+.*\band\b', # "who have X and Y"
            r'\bknow\s+.*\band\b',      # "know X and Y"
            r'\bexperience\s+.*\band\b', # "experience with X and Y"
        ]

        or_indicators = [
            r'\bor\b',                  # explicit "or"
            r'\beither\b',              # "either X or Y"
            r'\bany\s+of\b',           # "any of X, Y, Z"
        ]

        # Check for AND indicators
        has_and_logic = any(re.search(pattern, query, re.I) for pattern in and_indicators)
        has_or_logic = any(re.search(pattern, query, re.I) for pattern in or_indicators)

        # Default to AND if we have multiple skills and AND indicators, OR if explicit OR
        if has_or_logic:
            out["skills_mode"] = "any"
        elif has_and_logic or len(skills_found) > 1:
            out["skills_mode"] = "all"
        else:
            out["skills_mode"] = "any"

    # Location detection (basic)
    location_patterns = [
        r'\bin\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',  # "in New York"
        r'\bfrom\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', # "from California"
        r'\bbased\s+in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', # "based in London"
    ]

    locations = []
    for pattern in location_patterns:
        matches = re.findall(pattern, query)
        locations.extend(matches)

    if locations:
        out["locations"] = list(set(locations))  # Remove duplicates

    # If we found something with regex, return it
    if out:
        logger.info(f"Regex parsing found: {out}")
        return out

    # --- MODIFIED: Fallback to OpenAI with new async client ---
    if not client:
        logger.warning("OpenAI client not available for query parsing.")
        return {}

    prompt = (
        "You are an assistant that extracts structured filters from "
        "natural-language hiring queries. Pay special attention to whether "
        "skills should be matched with AND logic (candidate must have ALL skills) "
        "or OR logic (candidate can have ANY of the skills).\n\n"
        
        "Examples:\n"
        "- 'with aws, sql and python' → skills_mode: 'all'\n"
        "- 'python or java developer' → skills_mode: 'any'\n"
        "- 'more than 5 years' → min_years: 5\n"
        "- 'less than 3 years' → max_years: 3\n\n"
        
        f"Query: \"{query}\"\n\n"
        "Return ONLY a JSON object matching this schema:\n"
        f"{json.dumps(_SCHEMA, indent=2)}\n\n"
        "Important: Set skills_mode to 'all' if the query implies the candidate "
        "must have ALL listed skills, 'any' if they can have ANY of them."
    )
    
    try:
        rsp = await client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        result = json.loads(rsp.choices[0].message.content)
        logger.info(f"OpenAI parsing found: {result}")
        return result
    except Exception as e:
        logger.warning(f"OpenAI parse failed → {e}")
        return {}
