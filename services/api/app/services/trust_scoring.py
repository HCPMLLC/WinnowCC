from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.candidate_trust import CandidateTrust
from app.models.resume_document import ResumeDocument
from app.models.trust_audit_log import TrustAuditLog
from app.services.profile_parser import default_profile_json


@dataclass(frozen=True)
class TrustScoreResult:
    score: int
    status: str
    reasons: list[dict]
    user_message: str


TRUST_ALLOWED = "allowed"
TRUST_SOFT = "soft_quarantine"
TRUST_HARD = "hard_quarantine"


def evaluate_trust_for_resume(
    session: Session,
    resume: ResumeDocument,
    profile_json: dict | None,
    action: str,
) -> CandidateTrust:
    profile = profile_json or default_profile_json()
    parse_succeeded = bool(profile_json)
    result = _compute_score(session, resume, profile, parse_succeeded=parse_succeeded)

    trust = session.execute(
        select(CandidateTrust).where(CandidateTrust.resume_document_id == resume.id)
    ).scalar_one_or_none()
    prev_status = trust.status if trust else None
    if trust is None:
        trust = CandidateTrust(
            resume_document_id=resume.id,
            score=result.score,
            status=result.status,
            reasons=result.reasons,
            user_message=result.user_message,
            internal_notes=None,
        )
        session.add(trust)
        session.flush()
    else:
        trust.score = result.score
        trust.status = result.status
        trust.reasons = result.reasons
        trust.user_message = result.user_message

    audit = TrustAuditLog(
        trust_id=trust.id,
        actor_type="system",
        action=action,
        prev_status=prev_status,
        new_status=trust.status,
        details={"score": trust.score, "reasons": trust.reasons},
    )
    session.add(audit)
    session.commit()
    session.refresh(trust)
    return trust


def create_audit_entry(
    session: Session,
    trust: CandidateTrust,
    actor_type: str,
    action: str,
    details: dict | None = None,
    prev_status: str | None = None,
    new_status: str | None = None,
) -> None:
    audit = TrustAuditLog(
        trust_id=trust.id,
        actor_type=actor_type,
        action=action,
        prev_status=prev_status,
        new_status=new_status,
        details=details or {},
    )
    session.add(audit)
    session.commit()


def get_latest_resume(session: Session, user_id: int) -> ResumeDocument | None:
    stmt = (
        select(ResumeDocument)
        .where(ResumeDocument.user_id == user_id)
        .order_by(ResumeDocument.created_at.desc())
        .limit(1)
    )
    return session.execute(stmt).scalars().first()


def get_latest_trust(session: Session, user_id: int) -> CandidateTrust | None:
    resume = get_latest_resume(session, user_id)
    if resume is None:
        return None
    stmt = select(CandidateTrust).where(CandidateTrust.resume_document_id == resume.id)
    return session.execute(stmt).scalar_one_or_none()


def _compute_score(
    session: Session,
    resume: ResumeDocument,
    profile_json: dict,
    parse_succeeded: bool,
) -> TrustScoreResult:
    reasons: list[dict] = []
    score = 0

    bucket_a = 0
    basics = profile_json.get("basics", {}) if isinstance(profile_json, dict) else {}
    experience = profile_json.get("experience", []) if isinstance(profile_json, dict) else []

    name_present = bool(basics.get("name"))
    email_present = bool(basics.get("email"))
    location_present = bool(basics.get("location"))
    work_history_present = bool(experience)

    bucket_a += _add_signal(
        reasons,
        name_present,
        6,
        "identity_name_present",
        "low",
        "Name detected in profile data.",
    )
    bucket_a += _add_signal(
        reasons,
        email_present,
        6,
        "identity_email_present",
        "low",
        "Email detected in profile data.",
    )
    bucket_a += _add_signal(
        reasons,
        location_present,
        6,
        "identity_location_present",
        "low",
        "Location detected in profile data.",
    )
    bucket_a += _add_signal(
        reasons,
        work_history_present,
        7,
        "identity_work_history_present",
        "low",
        "Work history detected in profile data.",
    )
    if (not name_present) or (not work_history_present):
        bucket_a += _add_reason(
            reasons,
            10,
            "identity_missing_core_fields",
            "medium",
            "Missing name or work history in profile data.",
        )
    score += min(bucket_a, 25)

    bucket_b = 0
    bucket_b += _add_signal(
        reasons,
        parse_succeeded,
        5,
        "resume_parse_succeeded",
        "low",
        "Resume parsed successfully.",
    )
    has_job_entries = len(experience) >= 1
    bucket_b += _add_signal(
        reasons,
        has_job_entries,
        5,
        "resume_job_entries_present",
        "low",
        "At least one job entry detected.",
    )
    overlaps = _find_overlaps(experience)
    if not overlaps and has_job_entries:
        bucket_b += _add_reason(
            reasons,
            5,
            "resume_no_overlaps",
            "low",
            "No overlapping employment dates detected.",
        )
    if overlaps:
        overlap_score = 15 if len(overlaps) > 1 else 10
        bucket_b += _add_reason(
            reasons,
            overlap_score,
            "resume_overlapping_dates",
            "high" if overlap_score >= 15 else "medium",
            "Overlapping employment dates detected.",
        )
    keyword_stuffing = _keyword_stuffing_detected(profile_json)
    if not keyword_stuffing and parse_succeeded:
        bucket_b += _add_reason(
            reasons,
            5,
            "resume_no_keyword_stuffing",
            "low",
            "No extreme keyword repetition detected.",
        )
    if keyword_stuffing:
        bucket_b += _add_reason(
            reasons,
            10,
            "resume_keyword_stuffing",
            "medium",
            "Extreme keyword repetition detected.",
        )
    score += min(bucket_b, 20)

    bucket_c = 0
    urls = _extract_urls(basics)
    linkedin_present = _url_present(urls, "linkedin.com")
    github_present = _url_present(urls, "github.com") or bool(basics.get("github"))
    portfolio_present = bool(basics.get("portfolio") or basics.get("website"))
    other_present = github_present or portfolio_present

    bucket_c += _add_signal(
        reasons,
        linkedin_present,
        10,
        "online_linkedin_present",
        "low",
        "LinkedIn URL provided.",
    )
    bucket_c += _add_signal(
        reasons,
        other_present,
        5,
        "online_github_or_portfolio_present",
        "low",
        "GitHub or portfolio URL provided.",
    )
    if linkedin_present and other_present:
        bucket_c += _add_reason(
            reasons,
            10,
            "online_multiple_profiles_present",
            "low",
            "Multiple professional profiles provided.",
        )

    malformed_count = _count_malformed_urls(urls)
    if malformed_count:
        bucket_c += _add_reason(
            reasons,
            min(10, malformed_count * 5),
            "online_malformed_urls",
            "medium",
            "One or more URLs appear malformed.",
        )
    score += min(bucket_c, 25)

    bucket_d = 0
    if resume.sha256:
        duplicate_count = session.execute(
            select(func.count(ResumeDocument.id)).where(
                ResumeDocument.sha256 == resume.sha256
            )
        ).scalar_one()
        if duplicate_count and duplicate_count > 1:
            dup_score = 20 if duplicate_count == 2 else 25 if duplicate_count == 3 else 30
            bucket_d += _add_reason(
                reasons,
                dup_score,
                "abuse_duplicate_resume_hash",
                "high",
                f"Resume hash appears on {duplicate_count} documents.",
            )

    if _frequent_uploads(session, resume.user_id):
        bucket_d += _add_reason(
            reasons,
            10,
            "abuse_frequent_uploads",
            "medium",
            "Unusually frequent resume uploads detected.",
        )
    score += min(bucket_d, 30)

    status = _status_from_score(score)
    user_message = (
        "Verification required before matching."
        if status != TRUST_ALLOWED
        else "Profile ready for matching."
    )

    return TrustScoreResult(
        score=score,
        status=status,
        reasons=reasons,
        user_message=user_message,
    )


def _status_from_score(score: int) -> str:
    if score < 30:
        return TRUST_ALLOWED
    if score < 60:
        return TRUST_SOFT
    return TRUST_HARD


def _add_signal(
    reasons: list[dict],
    condition: bool,
    points: int,
    code: str,
    severity: str,
    message: str,
) -> int:
    if not condition:
        return 0
    return _add_reason(reasons, points, code, severity, message)


def _add_reason(
    reasons: list[dict],
    points: int,
    code: str,
    severity: str,
    message: str,
) -> int:
    reasons.append(
        {
            "code": code,
            "severity": severity,
            "message": message,
            "points": points,
        }
    )
    return points


def _extract_urls(basics: dict) -> list[str]:
    urls = []
    for key in ("linkedin", "github", "portfolio", "website", "url"):
        value = basics.get(key)
        if isinstance(value, str) and value.strip():
            urls.append(value.strip())
    return urls


def _url_present(urls: list[str], domain: str) -> bool:
    for value in urls:
        if domain in value.lower():
            return True
    return False


def _count_malformed_urls(urls: list[str]) -> int:
    count = 0
    for value in urls:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            count += 1
    return count


def _frequent_uploads(session: Session, user_id: int | None) -> bool:
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    if user_id is None:
        user_filter = ResumeDocument.user_id.is_(None)
    else:
        user_filter = ResumeDocument.user_id == user_id
    stmt = select(func.count(ResumeDocument.id)).where(
        user_filter, ResumeDocument.created_at >= since
    )
    count = session.execute(stmt).scalar_one()
    return bool(count and count >= 5)


def _find_overlaps(experience: list[dict]) -> list[tuple[int, int]]:
    ranges = []
    for item in experience:
        start = _parse_date(item.get("start_date"))
        end = _parse_date(item.get("end_date"), default_end=True)
        if start is None or end is None:
            continue
        if end < start:
            start, end = end, start
        ranges.append((start, end))

    overlaps = []
    ranges.sort()
    for idx, (start, end) in enumerate(ranges):
        for next_start, next_end in ranges[idx + 1 :]:
            if next_start <= end:
                overlaps.append((start, next_end))
            else:
                break
    return overlaps


def _parse_date(value: str | None, default_end: bool = False) -> int | None:
    if not value:
        return None
    cleaned = value.strip().lower()
    if cleaned in {"present", "current", "now"}:
        return 999912 if default_end else None
    parts = cleaned.replace(".", "").split()
    if len(parts) == 1 and parts[0].isdigit():
        return int(parts[0]) * 100
    if len(parts) >= 2 and parts[1].isdigit():
        year = int(parts[1])
        month = _month_number(parts[0])
        if month:
            return year * 100 + month
    return None


def _month_number(value: str) -> int | None:
    months = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "sept": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }
    return months.get(value[:4])


def _keyword_stuffing_detected(profile_json: dict) -> bool:
    tokens = []

    def _collect(value: object) -> None:
        if isinstance(value, str):
            tokens.extend(value.split())
        elif isinstance(value, dict):
            for inner in value.values():
                _collect(inner)
        elif isinstance(value, list):
            for inner in value:
                _collect(inner)

    _collect(profile_json)
    counts: dict[str, int] = {}
    for token in tokens:
        word = "".join(char for char in token.lower() if char.isalnum())
        if len(word) < 4:
            continue
        counts[word] = counts.get(word, 0) + 1
    return any(count >= 20 for count in counts.values())
