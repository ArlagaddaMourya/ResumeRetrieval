"""
Enhanced utility helpers with improved skill extraction
"""
from __future__ import annotations
import re
from pathlib import Path
from datetime import datetime


__all__ = [
    "l2_normalize",
    "extract_email",
    "extract_skills",
    "estimate_years_experience",
    "guess_name",
]

# ---------- résumé heuristics ----------
EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

# Comprehensive skills list with aliases
SKILL_ALIASES = {
    "python": ["python", "py"],
    "java": ["java"],
    "javascript": ["javascript", "js", "node.js", "nodejs"],
    "typescript": ["typescript", "ts"],
    "react": ["react", "reactjs", "react.js"],
    "angular": ["angular", "angularjs"],
    "vue": ["vue", "vuejs", "vue.js"],
    "node": ["node", "nodejs", "node.js"],
    "go": ["go", "golang"],
    "c++": ["c++", "cpp", "cplusplus"],
    "c#": ["c#", "csharp", "c-sharp"],
    "aws": ["aws", "amazon web services"],
    "azure": ["azure", "microsoft azure"],
    "gcp": ["gcp", "google cloud", "google cloud platform"],
    "docker": ["docker", "containerization"],
    "kubernetes": ["kubernetes", "k8s"],
    "sql": ["sql", "mysql", "postgresql", "postgres", "sqlite"],
    "nosql": ["nosql", "mongodb", "mongo", "cassandra", "dynamodb"],
    "redis": ["redis"],
    "html": ["html", "html5"],
    "css": ["css", "css3", "scss", "sass"],
    "php": ["php"],
    "ruby": ["ruby", "ruby on rails", "rails"],
    "scala": ["scala"],
    "kotlin": ["kotlin"],
    "swift": ["swift"],
    "tensorflow": ["tensorflow", "tf"],
    "pytorch": ["pytorch", "torch"],
    "machine learning": ["machine learning", "ml", "artificial intelligence", "ai"],
    "django": ["django"],
    "flask": ["flask"],
    "spring": ["spring", "spring boot"],
    "express": ["express", "expressjs", "express.js"],
    "fastapi": ["fastapi"],
    "git": ["git", "github", "gitlab", "bitbucket"],
    "jenkins": ["jenkins", "ci/cd"],
    "terraform": ["terraform"],
    "ansible": ["ansible"],
    "helm": ["helm"],
    "spark": ["spark", "apache spark"],
    "kafka": ["kafka", "apache kafka"],
    "elasticsearch": ["elasticsearch", "elastic search"],
    "grafana": ["grafana"],
    "prometheus": ["prometheus"],
    "rest": ["rest", "restful", "rest api", "api"],
    "graphql": ["graphql"],
    "microservices": ["microservices", "microservice"],
    "devops": ["devops", "dev ops"],
    "agile": ["agile", "scrum", "kanban"],
    "jira": ["jira"],
}

# Flatten for quick lookup
COMMON_SKILLS = set()
for canonical, aliases in SKILL_ALIASES.items():
    COMMON_SKILLS.add(canonical)
    COMMON_SKILLS.update(aliases)

def extract_email(text: str) -> str | None:
    m = EMAIL_RE.search(text)
    return m.group(0) if m else None

def extract_skills(text: str) -> list[str]:
    """Extract skills with better matching using aliases."""
    found_skills = set()
    text_lower = text.lower()
    
    # Check each canonical skill and its aliases
    for canonical_skill, aliases in SKILL_ALIASES.items():
        for alias in aliases:
            # Create word boundary pattern for better matching
            pattern = rf"\b{re.escape(alias)}\b"
            if re.search(pattern, text_lower):
                found_skills.add(canonical_skill)
                break  # Found this skill, no need to check other aliases
    
    return sorted(found_skills)

def estimate_years_experience(text: str) -> int:
    """Improved years of experience estimation."""
    # Pattern 1: Explicit "X years of experience"
    patterns = [
        r"(\d{1,2})\s*\+?\s*(?:yrs?|years?)\s+of\s+(?:experience|exp)",
        r"(\d{1,2})\s*\+?\s*(?:yrs?|years?)\s+(?:experience|exp)",
        r"(\d{1,2})\s*\+?\s*(?:year|yr)\s+(?:experience|exp)",
        r"experience\s*:?\s*(\d{1,2})\s*\+?\s*(?:yrs?|years?)",
        r"(\d{1,2})\s*\+\s*(?:yrs?|years?)",  # "5+ years"
    ]
    
    for pattern in patterns:
        hits = re.findall(pattern, text, re.I)
        if hits:
            return max(int(x) for x in hits)
    
    # Pattern 2: Date ranges (employment history)
    # Look for patterns like "2018-2023", "2018 - present", etc.
    current_year = datetime.now().year
    
    # Find all 4-digit years
    years = []
    year_matches = re.findall(r"\b(19|20)\d{2}\b", text)
    for match in year_matches:
        year = int(match + re.search(rf"{match}\d{{2}}", text).group()[-2:])
        if 1990 <= year <= current_year:
            years.append(year)
    
    if len(years) >= 2:
        # Calculate experience based on year range
        min_year = min(years)
        max_year = max(years)
        if max_year == current_year:
            # If latest year is current year, calculate from earliest
            return max(1, current_year - min_year)
        else:
            # Calculate span of years mentioned
            return max(1, max_year - min_year)
    
    # Pattern 3: Look for "since YYYY" patterns
    since_matches = re.findall(r"since\s+(19|20)\d{2}", text, re.I)
    if since_matches:
        since_year = int(since_matches[0] + re.search(rf"{since_matches[0]}\d{{2}}", text).group()[-2:])
        return max(1, current_year - since_year)
    
    return 0

def guess_name(filename: str, email: str | None) -> str:
    """Improved name guessing from filename or email."""
    if email:
        # Extract name from email prefix
        name_part = email.split("@")[0]
        # Handle common patterns like firstname.lastname, firstname_lastname
        name_part = name_part.replace(".", " ").replace("_", " ").replace("-", " ")
        # Remove numbers and special characters
        name_part = re.sub(r'[^a-zA-Z\s]', '', name_part)
        return name_part.title().strip()
    
    if filename:
        # Extract name from filename
        name_part = Path(filename).stem
        name_part = name_part.replace("_", " ").replace("-", " ")
        # Remove common resume-related words
        name_part = re.sub(r'\b(?:resume|cv|curriculum|vitae)\b', '', name_part, flags=re.I)
        # Remove numbers and special characters
        name_part = re.sub(r'[^a-zA-Z\s]', '', name_part)
        return name_part.title().strip()
    
    return "Unknown"