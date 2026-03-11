"""Cross-job matching service."""

import logging
from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cross_job_recommendation import CrossJobRecommendation
from app.models.job import Job

logger = logging.getLogger(__name__)


async def generate_cross_job_recommendations(
    db: AsyncSession,
    candidate_id: int,
    applied_job_id: int,
    tenant_id: int,
    tenant_type: str,
    limit: int = 5,
) -> list[CrossJobRecommendation]:
    """Generate cross-job recommendations when candidate applies."""

    # Find other open jobs from this tenant
    filters = [
        Job.id != applied_job_id,
        Job.is_active == True,  # noqa: E712
    ]
    if tenant_type == "employer":
        filters.append(Job.employer_job_id.isnot(None))

    result = await db.execute(select(Job).where(and_(*filters)).limit(20))
    other_jobs = list(result.scalars().all())

    if not other_jobs:
        return []

    recommendations = []

    for job in other_jobs:
        # Check cache
        existing = await db.execute(
            select(CrossJobRecommendation).where(
                and_(
                    CrossJobRecommendation.candidate_id == candidate_id,
                    CrossJobRecommendation.source_job_id == applied_job_id,
                    CrossJobRecommendation.recommended_job_id == job.id,
                    CrossJobRecommendation.expires_at > datetime.utcnow(),
                )
            )
        )
        cached = existing.scalar_one_or_none()

        if cached:
            recommendations.append(cached)
            continue

        # Calculate IPS (simplified - integrate with matching service)
        ips_score = 75  # TODO: Call actual matching service

        if ips_score >= 60:
            explanation = await _generate_match_explanation(job, ips_score)

            cross_rec = CrossJobRecommendation(
                candidate_id=candidate_id,
                source_job_id=applied_job_id,
                recommended_job_id=job.id,
                ips_score=ips_score,
                explanation=explanation,
                expires_at=CrossJobRecommendation.default_expiry(),
            )
            db.add(cross_rec)
            recommendations.append(cross_rec)

    await db.commit()

    # Sort and limit
    recommendations.sort(key=lambda x: x.ips_score, reverse=True)
    return recommendations[:limit]


async def get_cross_job_recommendations(
    db: AsyncSession,
    candidate_id: int,
    source_job_id: int = None,
) -> list[CrossJobRecommendation]:
    """Get cached recommendations for a candidate."""
    query = select(CrossJobRecommendation).where(
        and_(
            CrossJobRecommendation.candidate_id == candidate_id,
            CrossJobRecommendation.expires_at > datetime.utcnow(),
        )
    )

    if source_job_id:
        query = query.where(
            CrossJobRecommendation.source_job_id == source_job_id
        )

    result = await db.execute(
        query.order_by(CrossJobRecommendation.ips_score.desc())
    )
    return list(result.scalars().all())


async def _generate_match_explanation(job: Job, ips_score: int) -> str:
    """Generate explanation using Claude Haiku (~$0.001)."""
    # TODO: Integrate with Anthropic API
    if ips_score >= 85:
        return "Strong match based on your experience and skills"
    elif ips_score >= 70:
        return "Good alignment with the role requirements"
    else:
        return "Potential fit worth exploring"
