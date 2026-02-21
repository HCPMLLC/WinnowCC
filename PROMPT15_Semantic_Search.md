# PROMPT15_Semantic_Search.md

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, and the existing openapi JSON files before making changes.

## Purpose

Add semantic search and embedding-based matching to Winnow using pgvector. This goes beyond keyword overlap — embeddings capture the *meaning* of a candidate's experience and a job's requirements, enabling matches that keyword matching misses (e.g., "built CI/CD pipelines" matching a job asking for "DevOps automation experience" even though the exact words differ).

This is the intelligence layer that makes Winnow's matching feel magical to users.

---

## Triggers — When to Use This Prompt

- Adding vector similarity search to job matching.
- Enabling pgvector in the Postgres database.
- Generating embeddings for job postings and candidate profiles.
- Implementing "find similar jobs" or "semantic match" features.
- Product asks for "smarter matching," "semantic search," or "AI-powered matching."

---

## What Already Exists (DO NOT recreate)

1. **Postgres 16** running via Docker Compose at `infra/docker-compose.yml`. Currently uses the standard `postgres:16` image (pgvector extension NOT yet enabled).
2. **Job model:** `services/api/app/models/job.py` — stores job postings. SPEC §7 specifies an `embedding vector` column but it may not exist yet in the actual model.
3. **Candidate profile:** `services/api/app/models/candidate_profile.py` — `profile_json` (JSONB) with structured experience, skills, preferences.
4. **Matching service:** `services/api/app/services/matching.py` — deterministic skill-overlap scoring (match_score, resume_score, interview_probability). This is the file where semantic similarity will be blended in.
5. **Queue/worker:** `services/api/app/services/queue.py` + `services/api/app/worker.py` — RQ-based background job processing.
6. **Ingestion pipeline:** Fetches jobs from sources and stores them in the `jobs` table. Embeddings should be generated as part of this pipeline.
7. **Anthropic SDK:** Already in `requirements.txt` (from PROMPT11 tailored resume). The Anthropic Voyager embedding model is available.

---

## Architecture Overview

```
                                          ┌──────────────────┐
  Job Ingestion ──→ Store Job ──→ RQ ──→  │ Embed Job Text   │ ──→ jobs.embedding
                                          └──────────────────┘
                                          
  Resume Parse ──→ Store Profile ──→ RQ ──→ ┌────────────────────┐
                                            │ Embed Profile Text │ ──→ candidate_profiles.embedding
                                            └────────────────────┘

  Match Refresh ──→ SELECT jobs WHERE cosine_sim(profile.embedding, job.embedding) > threshold
                    ──→ Blend with deterministic match_score ──→ Final composite score
```

Three components:
1. **Infrastructure:** pgvector extension enabled in Postgres, vector columns added.
2. **Embedding service:** Generates embeddings via API (Anthropic Voyage or OpenAI), stores them.
3. **Semantic matching:** Uses cosine similarity in SQL to find and rank jobs, blended with existing deterministic scoring.

---

## What to Build

### Part 1: Infrastructure — Enable pgvector

#### 1.1 Update Docker Compose image

**File to modify:** `infra/docker-compose.yml`

Change the Postgres image from `postgres:16` to `pgvector/pgvector:pg16` which is the official pgvector-enabled Postgres 16 image.

Find the Postgres service definition and change:

```yaml
# BEFORE
services:
  postgres:
    image: postgres:16
    # ...

# AFTER
services:
  postgres:
    image: pgvector/pgvector:pg16
    # ... (keep everything else the same)
```

#### 1.2 Alembic migration — enable extension + add vector columns

**File to create:** New Alembic migration

```powershell
cd services/api
.\.venv\Scripts\Activate.ps1
alembic revision -m "enable pgvector and add embedding columns"
```

In the generated migration file, write:

```python
from alembic import op
import sqlalchemy as sa

def upgrade():
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    
    # Add embedding column to jobs table
    # Using 1024 dimensions (Voyage-3 default) or 1536 (OpenAI default)
    # Adjust dimension based on chosen model
    op.add_column("jobs", sa.Column("embedding", sa.LargeBinary(), nullable=True))
    
    # Add embedding column to candidate_profiles table
    op.add_column("candidate_profiles", sa.Column("embedding", sa.LargeBinary(), nullable=True))

def downgrade():
    op.drop_column("candidate_profiles", "embedding")
    op.drop_column("jobs", "embedding")
    op.execute("DROP EXTENSION IF EXISTS vector")
```

**Important:** The `pgvector` Python package handles the vector type natively with SQLAlchemy. See Part 1.3 for the proper SQLAlchemy column type.

#### 1.3 Install pgvector Python package

**File to modify:** `services/api/requirements.txt`

Add:
```
pgvector>=0.3.0
```

Then install:
```powershell
cd services/api
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

#### 1.4 SQLAlchemy vector column type

Use `pgvector`'s SQLAlchemy integration. In the migration and models, use:

```python
from pgvector.sqlalchemy import Vector

# In the Alembic migration (correct approach):
def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column("jobs", sa.Column("embedding", Vector(1024), nullable=True))
    op.add_column("candidate_profiles", sa.Column("embedding", Vector(1024), nullable=True))
```

#### 1.5 Update the SQLAlchemy models

**File to modify:** `services/api/app/models/job.py`

Add the embedding column:
```python
from pgvector.sqlalchemy import Vector

class Job(Base):
    # ... existing columns ...
    embedding = Column(Vector(1024), nullable=True)  # Voyage-3: 1024 dims
```

**File to modify:** `services/api/app/models/candidate_profile.py`

Add the embedding column:
```python
from pgvector.sqlalchemy import Vector

class CandidateProfile(Base):
    # ... existing columns ...
    embedding = Column(Vector(1024), nullable=True)  # Voyage-3: 1024 dims
```

#### 1.6 Create the pgvector index

After adding data, create an index for fast similarity search. Add to the migration or as a separate migration:

```python
def upgrade():
    # ... (after adding columns) ...
    # Create IVFFlat index on jobs.embedding for approximate nearest neighbor search
    # Use ivfflat for datasets < 1M rows; switch to HNSW for larger datasets
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_jobs_embedding 
        ON jobs 
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_profiles_embedding 
        ON candidate_profiles 
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)
```

**Note:** IVFFlat index requires that some rows already exist before creation (it needs to build lists). If the tables are empty, create the index AFTER the first batch of embeddings is generated. Alternatively, use HNSW which doesn't have this limitation:

```sql
CREATE INDEX IF NOT EXISTS idx_jobs_embedding 
ON jobs 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

HNSW is recommended for production. IVFFlat is faster to build but HNSW has better query performance.

#### 1.7 Restart infrastructure

After modifying docker-compose.yml:

```powershell
cd infra
docker compose down
docker compose up -d
```

Then run the migration:
```powershell
cd services/api
.\.venv\Scripts\Activate.ps1
alembic upgrade head
```

---

### Part 2: Embedding Service

**File to create:** `services/api/app/services/embedding.py` (NEW)

This service generates embeddings for text using an external API and handles batching.

#### 2.1 Choose an embedding model

Two recommended options (pick ONE based on what's available):

**Option A: Anthropic Voyage (recommended if already using Anthropic)**
- Model: `voyage-3` (1024 dimensions, excellent for job/resume text)
- Requires: `VOYAGE_API_KEY` in `.env` (separate from Anthropic API key — Voyage is a separate service at https://www.voyageai.com)
- Install: `pip install voyageai`

**Option B: OpenAI Embeddings (alternative)**
- Model: `text-embedding-3-small` (1536 dimensions) or `text-embedding-3-large` (3072, can truncate to 1024)
- Requires: `OPENAI_API_KEY` in `.env`
- Install: `pip install openai`

**Option C: Sentence Transformers (free, local, no API key)**
- Model: `all-MiniLM-L6-v2` (384 dimensions) or `all-mpnet-base-v2` (768 dimensions)
- Requires: No API key — runs locally
- Install: `pip install sentence-transformers`
- Tradeoff: Lower quality than Voyage/OpenAI but free and fast

The implementation below uses **Option A (Voyage)** as primary with **Option C (Sentence Transformers)** as the free fallback. Adjust the vector dimension in your migration accordingly (1024 for Voyage, 384 for MiniLM).

#### 2.2 Embedding service implementation

```python
"""
Embedding generation service.
Supports Voyage AI (production) and Sentence Transformers (free/local fallback).
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Configuration
EMBEDDING_PROVIDER = os.environ.get("EMBEDDING_PROVIDER", "sentence_transformers")  # "voyage" | "openai" | "sentence_transformers"
EMBEDDING_DIMENSION = int(os.environ.get("EMBEDDING_DIMENSION", "384"))  # Match your model

# ── Voyage AI ──────────────────────────────────
def _embed_voyage(texts: list[str]) -> list[list[float]]:
    """Generate embeddings using Voyage AI API."""
    import voyageai
    client = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])
    result = client.embed(texts, model="voyage-3", input_type="document")
    return result.embeddings

# ── OpenAI ─────────────────────────────────────
def _embed_openai(texts: list[str]) -> list[list[float]]:
    """Generate embeddings using OpenAI API."""
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.embeddings.create(input=texts, model="text-embedding-3-small")
    return [item.embedding for item in response.data]

# ── Sentence Transformers (free local) ─────────
_st_model = None
def _get_st_model():
    global _st_model
    if _st_model is None:
        from sentence_transformers import SentenceTransformer
        model_name = os.environ.get("ST_MODEL_NAME", "all-MiniLM-L6-v2")
        _st_model = SentenceTransformer(model_name)
        logger.info(f"Loaded Sentence Transformer model: {model_name}")
    return _st_model

def _embed_sentence_transformers(texts: list[str]) -> list[list[float]]:
    """Generate embeddings using local Sentence Transformers model."""
    model = _get_st_model()
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    return [emb.tolist() for emb in embeddings]

# ── Public API ─────────────────────────────────
PROVIDERS = {
    "voyage": _embed_voyage,
    "openai": _embed_openai,
    "sentence_transformers": _embed_sentence_transformers,
}

def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for a list of texts using the configured provider.
    
    Args:
        texts: List of text strings to embed. Max recommended batch: 32 for API, 128 for local.
    
    Returns:
        List of embedding vectors (list of floats), one per input text.
    """
    provider = EMBEDDING_PROVIDER
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown embedding provider: {provider}. Use: {list(PROVIDERS.keys())}")
    
    embed_fn = PROVIDERS[provider]
    
    # Batch if needed (API providers have limits)
    batch_size = 32 if provider in ("voyage", "openai") else 128
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        batch_embeddings = embed_fn(batch)
        all_embeddings.extend(batch_embeddings)
    
    return all_embeddings

def generate_embedding(text: str) -> list[float]:
    """Generate embedding for a single text string."""
    return generate_embeddings([text])[0]
```

#### 2.3 Text preparation helpers

```python
def prepare_job_text(job) -> str:
    """
    Build the text that represents a job posting for embedding.
    Combine title, company, description, and requirements into a single string.
    """
    parts = []
    if job.title:
        parts.append(f"Job Title: {job.title}")
    if job.company:
        parts.append(f"Company: {job.company}")
    if job.description:
        parts.append(f"Description: {job.description[:2000]}")  # Truncate very long descriptions
    if job.requirements:
        parts.append(f"Requirements: {job.requirements[:1000]}")
    if job.location:
        parts.append(f"Location: {job.location}")
    return "\n".join(parts)

def prepare_profile_text(profile_json: dict) -> str:
    """
    Build the text that represents a candidate profile for embedding.
    Combine summary, experience, skills, and preferences.
    """
    parts = []
    
    # Professional summary
    summary = profile_json.get("professional_summary") or ""
    if summary:
        parts.append(f"Summary: {summary}")
    
    # Experience (most recent 3 roles)
    experience = profile_json.get("work_experience") or profile_json.get("experience") or []
    for exp in experience[:3]:
        title = exp.get("job_title") or exp.get("title", "")
        company = exp.get("company_name") or exp.get("company", "")
        bullets = exp.get("accomplishments") or exp.get("duties") or exp.get("bullets") or []
        if title or company:
            parts.append(f"Role: {title} at {company}")
        for bullet in bullets[:5]:
            text = bullet if isinstance(bullet, str) else bullet.get("text", str(bullet))
            parts.append(f"- {text}")
    
    # Skills
    skills = profile_json.get("skills", {})
    if isinstance(skills, list):
        skill_names = skills  # Flat list (v1 format)
    elif isinstance(skills, dict):
        tech = skills.get("technical_skills", [])
        skill_names = [s["name"] if isinstance(s, dict) else s for s in tech]
        skill_names += skills.get("methodologies", [])
    else:
        skill_names = []
    if skill_names:
        parts.append(f"Skills: {', '.join(skill_names[:30])}")
    
    # Preferences
    prefs = profile_json.get("preferences", {})
    target_titles = prefs.get("target_titles", [])
    if target_titles:
        parts.append(f"Target roles: {', '.join(target_titles)}")
    
    return "\n".join(parts)
```

---

### Part 3: Embedding Generation Workers

**File to modify:** `services/api/app/services/queue.py` (or worker module)

Add two RQ background jobs:

#### 3.1 Embed a single job

```python
def embed_job(job_id: int):
    """
    Generate and store embedding for a single job.
    Called after job ingestion or reparse.
    """
    from app.services.embedding import generate_embedding, prepare_job_text
    # Load job from DB
    # text = prepare_job_text(job)
    # embedding = generate_embedding(text)
    # job.embedding = embedding
    # db.commit()
```

#### 3.2 Embed a candidate profile

```python
def embed_profile(user_id: int, profile_version: int):
    """
    Generate and store embedding for a candidate profile.
    Called after resume parsing or profile update.
    """
    from app.services.embedding import generate_embedding, prepare_profile_text
    # Load latest profile from DB
    # text = prepare_profile_text(profile.profile_json)
    # embedding = generate_embedding(text)
    # profile.embedding = embedding
    # db.commit()
```

#### 3.3 Batch embed all jobs (backfill)

```python
def embed_all_jobs():
    """
    Backfill embeddings for all jobs that don't have one.
    Enqueue as an admin background job.
    """
    from app.services.embedding import generate_embeddings, prepare_job_text
    # Load all jobs where embedding IS NULL
    # Batch process in groups of 32
    # For each batch: prepare texts → generate_embeddings → update DB
    # Log progress: "Embedded 32/1500 jobs..."
```

#### 3.4 Wire into existing pipelines

**After job ingestion:** In the ingestion pipeline (where new jobs are stored), add:
```python
# After: db.add(job); db.commit()
queue.enqueue(embed_job, job.id)
```

**After resume parsing:** In the resume parse worker, add:
```python
# After: profile saved with new profile_json
queue.enqueue(embed_profile, user_id, profile.version)
```

**After profile update:** In `services/api/app/routers/profile.py` — after `PUT /api/profile`:
```python
# After: profile_json updated, version bumped
queue.enqueue(embed_profile, user_id, profile.version)
```

---

### Part 4: Semantic Matching — SQL Queries

**File to modify:** `services/api/app/services/matching.py`

#### 4.1 Cosine similarity search

pgvector provides the `<=>` operator for cosine distance (lower = more similar). To convert to a 0–100 similarity score:

```python
from sqlalchemy import text

def find_semantically_similar_jobs(
    profile_embedding: list[float],
    limit: int = 50,
    min_similarity: float = 0.5,
    db_session = None,
) -> list[tuple[int, float]]:
    """
    Find jobs most similar to a candidate profile using cosine similarity.
    
    Returns: List of (job_id, similarity_score) tuples, sorted by similarity desc.
    similarity_score is 0.0–1.0 (1.0 = identical).
    """
    # pgvector cosine distance: 0 = identical, 2 = opposite
    # Convert to similarity: 1 - (distance / 2) for 0-1 range, or 1 - distance for standard cosine sim
    query = text("""
        SELECT 
            id,
            1 - (embedding <=> :profile_embedding) AS similarity
        FROM jobs
        WHERE embedding IS NOT NULL
          AND (is_active = true OR is_active IS NULL)
        ORDER BY embedding <=> :profile_embedding ASC
        LIMIT :limit
    """)
    
    result = db_session.execute(query, {
        "profile_embedding": str(profile_embedding),  # pgvector accepts string representation
        "limit": limit,
    })
    
    return [(row.id, row.similarity) for row in result if row.similarity >= min_similarity]
```

#### 4.2 "Find similar jobs" query

Given a job_id, find other similar jobs:

```python
def find_similar_jobs(
    job_id: int,
    limit: int = 10,
    db_session = None,
) -> list[tuple[int, float]]:
    """Find jobs similar to a given job using embedding similarity."""
    query = text("""
        SELECT 
            j2.id,
            1 - (j1.embedding <=> j2.embedding) AS similarity
        FROM jobs j1, jobs j2
        WHERE j1.id = :job_id
          AND j2.id != :job_id
          AND j1.embedding IS NOT NULL
          AND j2.embedding IS NOT NULL
          AND (j2.is_active = true OR j2.is_active IS NULL)
        ORDER BY j1.embedding <=> j2.embedding ASC
        LIMIT :limit
    """)
    
    result = db_session.execute(query, {"job_id": job_id, "limit": limit})
    return [(row.id, row.similarity) for row in result]
```

---

### Part 5: Blend Semantic Similarity with Deterministic Scoring

**File to modify:** `services/api/app/services/matching.py`

The semantic similarity score should *supplement* the existing deterministic match_score, not replace it. Keyword/skill-level matching is precise and explainable; semantic matching catches conceptual overlap that keywords miss.

#### 5.1 Blended match score

```python
# Weights for blending
W_DETERMINISTIC = 0.65  # Existing keyword/skill matching (precise, explainable)
W_SEMANTIC = 0.35       # Embedding similarity (catches conceptual overlap)

def compute_blended_match_score(
    deterministic_score: int,
    semantic_similarity: float | None,
) -> int:
    """
    Blend the deterministic match score with semantic similarity.
    
    Args:
        deterministic_score: 0-100 from existing matching logic
        semantic_similarity: 0.0-1.0 from cosine similarity (None if no embedding)
    
    Returns:
        Blended score 0-100
    """
    if semantic_similarity is None:
        return deterministic_score  # No embedding available — use deterministic only
    
    semantic_score = int(round(semantic_similarity * 100))  # Convert 0-1 to 0-100
    blended = W_DETERMINISTIC * deterministic_score + W_SEMANTIC * semantic_score
    return max(0, min(100, int(round(blended))))
```

#### 5.2 Wire into match computation

In the existing match computation pipeline (where `match_score` is set), add:

```python
# After computing deterministic match_score:
semantic_sim = None
if profile.embedding is not None and job.embedding is not None:
    # Compute cosine similarity between profile and job embeddings
    from pgvector.sqlalchemy import Vector
    # Use numpy or direct computation
    import numpy as np
    profile_vec = np.array(profile.embedding)
    job_vec = np.array(job.embedding)
    cosine_sim = np.dot(profile_vec, job_vec) / (np.linalg.norm(profile_vec) * np.linalg.norm(job_vec))
    semantic_sim = float(cosine_sim)

match.match_score = compute_blended_match_score(deterministic_score, semantic_sim)
```

#### 5.3 Add semantic_similarity to match response

**File to modify:** `services/api/app/schemas/matches.py`

Add to `MatchResponse`:
```python
semantic_similarity: float | None = None  # 0.0–1.0 cosine similarity
```

**File to modify:** `services/api/app/models/match.py`

Add column (requires migration):
```python
semantic_similarity = Column(Float, nullable=True)
```

---

### Part 6: Semantic Search API Endpoint

**File to modify:** `services/api/app/routers/matches.py` (or create new router)

#### 6.1 Semantic search endpoint

Add an endpoint that allows the user to search for jobs by free-text query (not just profile-based matching):

```python
@router.get("/api/matches/search")
async def semantic_search(
    q: str,
    limit: int = 20,
    user = Depends(get_current_user),
    db = Depends(get_db),
):
    """
    Search for jobs using a free-text query with semantic similarity.
    
    Example: "remote python backend developer with AWS experience"
    """
    from app.services.embedding import generate_embedding
    
    query_embedding = generate_embedding(q)
    
    results = find_semantically_similar_jobs(
        profile_embedding=query_embedding,
        limit=limit,
        min_similarity=0.3,
        db_session=db,
    )
    
    # Load full job objects for matched IDs
    # Return with similarity scores
```

#### 6.2 "Similar jobs" endpoint

```python
@router.get("/api/jobs/{job_id}/similar")
async def similar_jobs(
    job_id: int,
    limit: int = 5,
    user = Depends(get_current_user),
    db = Depends(get_db),
):
    """Find jobs similar to a given job."""
    results = find_similar_jobs(job_id=job_id, limit=limit, db_session=db)
    # Load and return similar job details
```

---

### Part 7: Admin — Backfill & Status Endpoints

**File to modify:** `services/api/app/routers/admin_jobs.py` (or create if doesn't exist)

```python
@router.post("/api/admin/embeddings/backfill-jobs")
async def backfill_job_embeddings(admin_token: str, db = Depends(get_db)):
    """Enqueue a background job to embed all jobs without embeddings."""
    # Verify admin_token
    # Enqueue embed_all_jobs()
    # Return: {"status": "queued", "jobs_without_embeddings": count}

@router.get("/api/admin/embeddings/status")
async def embedding_status(admin_token: str, db = Depends(get_db)):
    """Return counts of embedded vs. non-embedded jobs and profiles."""
    # Count jobs with/without embeddings
    # Count profiles with/without embeddings
    # Return: {"jobs_embedded": X, "jobs_total": Y, "profiles_embedded": A, "profiles_total": B}
```

---

### Part 8: Frontend — Semantic Search UI

**File to modify:** `apps/web/app/matches/page.tsx`

#### 8.1 Search bar

Add a text search input at the top of the matches page:

```
┌────────────────────────────────────────────────────────────────┐
│ 🔍 Search jobs: "remote devops engineer with kubernetes"  [Search] │
└────────────────────────────────────────────────────────────────┘
```

When the user types a query and clicks Search (or presses Enter):
1. Call `GET /api/matches/search?q=...`
2. Display results below the search bar, ranked by semantic similarity
3. Show the similarity score as a percentage badge (e.g., "94% match")

This is **in addition to** the existing profile-based matches. The search bar provides a way to explore beyond auto-matched jobs.

#### 8.2 "Similar Jobs" section

On each match card (or in a job detail view), add a "See similar jobs" link that calls `GET /api/jobs/{job_id}/similar` and shows 3–5 similar jobs in a sidebar or expandable section.

---

## Environment Variables

Add to `services/api/.env` and `services/api/.env.example`:

```
# Embedding provider: "voyage" | "openai" | "sentence_transformers"
EMBEDDING_PROVIDER=sentence_transformers

# Dimension (must match your model)
EMBEDDING_DIMENSION=384

# If using Voyage AI:
# VOYAGE_API_KEY=pa-...

# If using OpenAI:
# OPENAI_API_KEY=sk-...

# If using Sentence Transformers (local):
ST_MODEL_NAME=all-MiniLM-L6-v2
```

For local development, start with `sentence_transformers` (free, no API key needed). Switch to `voyage` for production quality.

---

## Dependencies to Add

**File to modify:** `services/api/requirements.txt`

Add:
```
pgvector>=0.3.0
sentence-transformers>=3.0.0
numpy>=1.26.0
```

Optionally (if using Voyage or OpenAI):
```
voyageai>=0.3.0
openai>=1.0.0
```

Install:
```powershell
cd services/api
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Note:** `sentence-transformers` will download the model on first use (~90MB for MiniLM). This happens once and is cached locally. The first embedding call may take a few seconds.

---

## File and Component Reference

| What | Where | Action |
|------|-------|--------|
| Docker Compose (pgvector image) | `infra/docker-compose.yml` | MODIFY — change Postgres image |
| Alembic migration (pgvector + columns) | `services/api/alembic/versions/` | CREATE — enable extension, add vector columns + index |
| Job model (embedding column) | `services/api/app/models/job.py` | MODIFY — add `embedding` Vector column |
| Profile model (embedding column) | `services/api/app/models/candidate_profile.py` | MODIFY — add `embedding` Vector column |
| Match model (semantic_similarity) | `services/api/app/models/match.py` | MODIFY — add `semantic_similarity` Float column |
| Embedding service | `services/api/app/services/embedding.py` | CREATE — embedding generation + text preparation |
| Matching service (blend) | `services/api/app/services/matching.py` | MODIFY — add semantic similarity blending |
| Queue / worker (embed jobs) | `services/api/app/services/queue.py` | MODIFY — add embed_job, embed_profile, embed_all_jobs |
| Ingestion pipeline | `services/api/app/services/ingestion.py` (or equivalent) | MODIFY — enqueue embed_job after storing |
| Profile router | `services/api/app/routers/profile.py` | MODIFY — enqueue embed_profile after PUT |
| Matches router (search) | `services/api/app/routers/matches.py` | MODIFY — add /search and /similar endpoints |
| Admin router (backfill) | `services/api/app/routers/admin_jobs.py` | MODIFY — add /embeddings/backfill-jobs and /status |
| Match schemas | `services/api/app/schemas/matches.py` | MODIFY — add semantic_similarity field |
| Requirements | `services/api/requirements.txt` | MODIFY — add pgvector, sentence-transformers, numpy |
| Environment | `services/api/.env` | MODIFY — add EMBEDDING_PROVIDER, EMBEDDING_DIMENSION |
| Frontend matches page | `apps/web/app/matches/page.tsx` | MODIFY — add search bar, similar jobs |

---

## Implementation Order (for a beginner following in Cursor)

### Phase 1: Infrastructure (Steps 1–5)

1. **Step 1:** Modify `infra/docker-compose.yml` — change Postgres image to `pgvector/pgvector:pg16`.
2. **Step 2:** Rebuild infrastructure:
   ```powershell
   cd infra
   docker compose down -v    # WARNING: -v removes data volumes. Skip -v if you want to keep data.
   docker compose up -d
   ```
   **Note:** If you want to keep existing data, omit `-v` and instead manually run `CREATE EXTENSION IF NOT EXISTS vector;` in psql after restarting.
3. **Step 3:** Add `pgvector`, `sentence-transformers`, `numpy` to `services/api/requirements.txt`. Install them.
4. **Step 4:** Create the Alembic migration:
   ```powershell
   cd services/api
   .\.venv\Scripts\Activate.ps1
   alembic revision -m "enable pgvector and add embedding columns"
   ```
   Edit the migration file to enable the extension and add vector columns to `jobs` and `candidate_profiles`.
5. **Step 5:** Run the migration:
   ```powershell
   alembic upgrade head
   ```
   Verify: connect to Postgres and run `SELECT extversion FROM pg_extension WHERE extname = 'vector';` — should return a version number.

### Phase 2: Embedding Service (Steps 6–8)

6. **Step 6:** Add `EMBEDDING_PROVIDER`, `EMBEDDING_DIMENSION`, `ST_MODEL_NAME` to `services/api/.env`.
7. **Step 7:** Create `services/api/app/services/embedding.py` with all provider functions and text preparation helpers.
8. **Step 8:** Update `services/api/app/models/job.py` and `services/api/app/models/candidate_profile.py` to add the `embedding` column using `Vector(384)` (or your chosen dimension).

### Phase 3: Workers (Steps 9–11)

9. **Step 9:** Add `embed_job`, `embed_profile`, `embed_all_jobs` worker functions.
10. **Step 10:** Wire `embed_job` into the ingestion pipeline (after job is stored).
11. **Step 11:** Wire `embed_profile` into the resume parse worker and the `PUT /api/profile` handler.

### Phase 4: Matching Enhancement (Steps 12–14)

12. **Step 12:** Add `semantic_similarity` column to Match model. Create Alembic migration. Run it.
13. **Step 13:** Add `compute_blended_match_score` and cosine similarity computation to `matching.py`.
14. **Step 14:** Wire blended scoring into the match computation pipeline.

### Phase 5: API Endpoints (Steps 15–17)

15. **Step 15:** Add `GET /api/matches/search?q=...` endpoint.
16. **Step 16:** Add `GET /api/jobs/{job_id}/similar` endpoint.
17. **Step 17:** Add admin backfill and status endpoints.

### Phase 6: Backfill + Test (Steps 18–19)

18. **Step 18:** Start all services. Use the admin endpoint to trigger `POST /api/admin/embeddings/backfill-jobs` to embed all existing jobs.
19. **Step 19:** Test:
    - [ ] Jobs have embeddings (check admin status endpoint)
    - [ ] Upload a resume → parse → profile gets embedding
    - [ ] Run match refresh → matches include `semantic_similarity` value
    - [ ] `GET /api/matches/search?q=python backend developer` returns relevant jobs
    - [ ] `GET /api/jobs/{id}/similar` returns similar jobs
    - [ ] Match scores are blended (65% deterministic + 35% semantic)

### Phase 7: Frontend (Step 20)

20. **Step 20:** Add search bar and similar jobs section to `apps/web/app/matches/page.tsx`.

### Phase 8: Lint (Step 21)

21. **Step 21:** Lint and format:
    ```powershell
    cd services/api
    python -m ruff check .
    python -m ruff format .
    cd apps/web
    npm run lint
    ```

---

## Performance & Cost Notes

- **Batch compute embeddings, not per request** (per ARCHITECTURE §5). Embeddings are generated on write (ingestion/parsing), not on read (match query).
- **Sentence Transformers (local):** Free, ~100ms per embedding, ~90MB model download once. Great for dev and small-scale production.
- **Voyage AI:** ~$0.0001 per 1K tokens. For 10,000 jobs at ~500 tokens each = ~$0.50 total. Very affordable.
- **Index choice:** HNSW is recommended for production (better query speed). IVFFlat is fine for < 10K rows.
- **Cache profile embeddings:** Only regenerate when profile_json changes (version bump).

---

## Non-Goals (Do NOT implement in this prompt)

- Fine-tuning a custom embedding model
- Real-time embedding generation on every page load
- Full-text search with PostgreSQL `tsvector` (separate feature, not needed with semantic search)
- Multi-language embedding support (future)
- Embedding visualization/debugging UI (admin-only future feature)

---

## Summary Checklist

- [ ] Infrastructure: Postgres image changed to `pgvector/pgvector:pg16`
- [ ] Infrastructure: pgvector extension enabled, vector columns + index created
- [ ] Dependencies: `pgvector`, `sentence-transformers`, `numpy` installed
- [ ] Environment: `EMBEDDING_PROVIDER`, `EMBEDDING_DIMENSION` configured
- [ ] Embedding service: `embedding.py` created with multi-provider support + text preparation
- [ ] Job model: `embedding` Vector column added
- [ ] Profile model: `embedding` Vector column added
- [ ] Match model: `semantic_similarity` Float column added
- [ ] Workers: `embed_job`, `embed_profile`, `embed_all_jobs` implemented
- [ ] Pipelines: embedding generated on job ingestion + resume parsing + profile update
- [ ] Matching: blended score (65% deterministic + 35% semantic) computed and stored
- [ ] API: `/api/matches/search?q=...` semantic search endpoint
- [ ] API: `/api/jobs/{job_id}/similar` similar jobs endpoint
- [ ] API: Admin backfill and status endpoints
- [ ] Frontend: Search bar on matches page
- [ ] Frontend: "Similar jobs" section on match cards
- [ ] Existing jobs backfilled with embeddings
- [ ] Linted and formatted

Return code changes only.
