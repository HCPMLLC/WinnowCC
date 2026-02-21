"""Embedding generation service for semantic search.

Supports multiple providers:
- sentence_transformers (default, free, local)
- voyage (production quality, requires VOYAGE_API_KEY)
- openai (alternative, requires OPENAI_API_KEY)
"""

import logging
import os

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
EMBEDDING_PROVIDER = os.environ.get("EMBEDDING_PROVIDER", "sentence_transformers")
EMBEDDING_DIMENSION = int(os.environ.get("EMBEDDING_DIMENSION", "384"))


# ---------------------------------------------------------------------------
# Provider implementations (lazy imports to avoid startup cost)
# ---------------------------------------------------------------------------
def _embed_voyage(texts: list[str]) -> list[list[float]]:
    """Generate embeddings using Voyage AI API."""
    import voyageai

    client = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])
    result = client.embed(texts, model="voyage-3", input_type="document")
    return result.embeddings


def _embed_openai(texts: list[str]) -> list[list[float]]:
    """Generate embeddings using OpenAI API."""
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.embeddings.create(input=texts, model="text-embedding-3-small")
    return [item.embedding for item in response.data]


_st_model = None


def _get_st_model():
    global _st_model
    if _st_model is None:
        from sentence_transformers import SentenceTransformer

        model_name = os.environ.get("ST_MODEL_NAME", "all-MiniLM-L6-v2")
        _st_model = SentenceTransformer(model_name)
        logger.info("Loaded Sentence Transformer model: %s", model_name)
    return _st_model


def _embed_sentence_transformers(texts: list[str]) -> list[list[float]]:
    """Generate embeddings using local Sentence Transformers model."""
    model = _get_st_model()
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    return [emb.tolist() for emb in embeddings]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
PROVIDERS = {
    "voyage": _embed_voyage,
    "openai": _embed_openai,
    "sentence_transformers": _embed_sentence_transformers,
}


def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a list of texts using the configured provider.

    Args:
        texts: List of text strings to embed.

    Returns:
        List of embedding vectors (list of floats), one per input text.
    """
    provider = EMBEDDING_PROVIDER
    if provider not in PROVIDERS:
        raise ValueError(
            f"Unknown embedding provider: {provider}. Use: {list(PROVIDERS.keys())}"
        )

    embed_fn = PROVIDERS[provider]
    batch_size = 32 if provider in ("voyage", "openai") else 128

    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        batch_embeddings = embed_fn(batch)
        all_embeddings.extend(batch_embeddings)

    return all_embeddings


def generate_embedding(text: str) -> list[float]:
    """Generate embedding for a single text string."""
    return generate_embeddings([text])[0]


# ---------------------------------------------------------------------------
# Text preparation helpers
# ---------------------------------------------------------------------------
def prepare_job_text(job) -> str:
    """Build the text that represents a job posting for embedding.

    Combines title, company, description, and location into a single string.
    """
    parts: list[str] = []
    if job.title:
        parts.append(f"Job Title: {job.title}")
    if job.company:
        parts.append(f"Company: {job.company}")
    if job.description_text:
        parts.append(f"Description: {job.description_text[:2000]}")
    if job.location:
        parts.append(f"Location: {job.location}")
    return "\n".join(parts)


def prepare_profile_text(profile_json: dict) -> str:
    """Build the text that represents a candidate profile for embedding.

    Combines summary, experience, skills, and preferences.
    """
    parts: list[str] = []

    # Professional summary
    summary = profile_json.get("professional_summary") or ""
    if summary:
        parts.append(f"Summary: {summary}")

    # Experience (most recent 3 roles)
    experience = profile_json.get("experience") or []
    for exp in experience[:3]:
        if not isinstance(exp, dict):
            continue
        title = exp.get("title", "")
        company = exp.get("company", "")
        if title or company:
            parts.append(f"Role: {title} at {company}")
        # Use accomplishments first, then duties, then bullets
        bullets = (
            exp.get("accomplishments") or exp.get("duties") or exp.get("bullets") or []
        )
        for bullet in bullets[:5]:
            text = bullet if isinstance(bullet, str) else str(bullet)
            parts.append(f"- {text}")

    # Skills (flat list)
    skills = profile_json.get("skills") or []
    if isinstance(skills, list):
        skill_names = [s for s in skills if isinstance(s, str)]
    else:
        skill_names = []
    if skill_names:
        parts.append(f"Skills: {', '.join(skill_names[:30])}")

    # Target roles from preferences
    prefs = profile_json.get("preferences") or {}
    target_titles = prefs.get("target_titles") or []
    if target_titles:
        parts.append(f"Target roles: {', '.join(target_titles)}")

    return "\n".join(parts)
