"""
Match quality validation script.
Loads test profiles, runs matching against seeded jobs, and produces a quality report.

Usage: python scripts/validate_matching.py [--profiles all|01|02|03|04|05]
                                            [--min-matches 10]
                                            [--output-dir reports/]
"""

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select

from app.db.session import get_session_factory
from app.models.candidate import Candidate
from app.models.candidate_profile import CandidateProfile
from app.models.job import Job
from app.models.user import User
from app.services.matching import compute_matches

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROFILE_DIR = Path(__file__).parent / "test_profiles"


def load_profiles(profile_filter: str) -> list[tuple[str, dict]]:
    """Load test profile JSON files."""
    profiles = []
    for path in sorted(PROFILE_DIR.glob("*.json")):
        profile_id = path.stem[:2]
        if profile_filter != "all" and profile_id not in profile_filter.split(","):
            continue
        with open(path) as f:
            profiles.append((path.stem, json.load(f)))
    return profiles


def evaluate_matches(
    profile_name: str, profile_json: dict, matches: list, session
) -> dict:
    """Evaluate match quality for a single profile."""
    candidate_skills = {s.lower() for s in profile_json.get("skills", [])}
    prefs = profile_json.get("preferences", {})
    desired_titles = [t.lower() for t in prefs.get("desired_titles", [])]
    remote_pref = prefs.get("remote_preference", "")

    scores = [m.match_score for m in matches]
    top_10 = matches[:10]
    top_20 = matches[:20]
    top_20_scores = [m.match_score for m in top_20]

    # Title relevance: check if job title relates to desired titles
    title_relevant = 0
    for m in top_10:
        job = session.execute(
            select(Job).where(Job.id == m.job_id)
        ).scalar_one_or_none()
        if not job:
            continue
        job_title_lower = (job.title or "").lower()
        if any(dt in job_title_lower or job_title_lower in dt for dt in desired_titles):
            title_relevant += 1
        elif any(
            word in job_title_lower
            for dt in desired_titles
            for word in dt.split()
            if len(word) > 3
        ):
            title_relevant += 1

    title_relevance_pct = (title_relevant / max(len(top_10), 1)) * 100

    # Skill overlap
    skill_overlaps = []
    for m in top_10:
        reasons = m.reasons or {}
        matched = reasons.get("matched_skills", [])
        skill_overlaps.append(len(matched))
    avg_skill_overlap = sum(skill_overlaps) / max(len(skill_overlaps), 1)

    # Hallucination check
    hallucinated = 0
    for m in top_10:
        reasons = m.reasons or {}
        matched = reasons.get("matched_skills", [])
        for skill in matched:
            if skill.lower() not in candidate_skills:
                hallucinated += 1

    # Location compliance
    location_ok = 0
    for m in top_10:
        job = session.execute(
            select(Job).where(Job.id == m.job_id)
        ).scalar_one_or_none()
        if not job:
            continue
        if remote_pref == "remote_only":
            if job.remote_flag:
                location_ok += 1
        else:
            location_ok += 1
    location_compliance_pct = (location_ok / max(len(top_10), 1)) * 100

    # Fraud and staleness
    fraudulent_matches = 0
    stale_matches = 0
    for m in matches:
        job = session.execute(
            select(Job).where(Job.id == m.job_id)
        ).scalar_one_or_none()
        if job and not job.is_active:
            stale_matches += 1

    # Embedding coverage
    embedded_count = 0
    for m in top_20:
        job = session.execute(
            select(Job).where(Job.id == m.job_id)
        ).scalar_one_or_none()
        if job and job.embedding is not None:
            embedded_count += 1
    embedding_coverage_pct = (embedded_count / max(len(top_20), 1)) * 100

    # Score distribution
    import statistics

    score_std_dev = statistics.stdev(top_20_scores) if len(top_20_scores) > 1 else 0

    matches_above_40 = len([s for s in scores if s >= 40])
    top_match_score = max(scores) if scores else 0
    avg_top_10 = sum(s.match_score for s in top_10) / max(len(top_10), 1)

    # Build top 5 details
    top_5_details = []
    for m in matches[:5]:
        job = session.execute(
            select(Job).where(Job.id == m.job_id)
        ).scalar_one_or_none()
        reasons = m.reasons or {}
        top_5_details.append(
            {
                "job_title": job.title if job else "Unknown",
                "company": job.company if job else "Unknown",
                "match_score": m.match_score,
                "matched_skills": reasons.get("matched_skills", []),
                "missing_skills": reasons.get("missing_skills", []),
            }
        )

    # Pass/fail
    issues = []
    if matches_above_40 < 10:
        issues.append(f"Only {matches_above_40} matches above 40 (target: >=10)")
    if title_relevance_pct < 70:
        issues.append(f"Title relevance {title_relevance_pct:.0f}% (target: >=70%)")
    if avg_skill_overlap < 3:
        issues.append(f"Avg skill overlap {avg_skill_overlap:.1f} (target: >=3)")
    if hallucinated > 0:
        issues.append(f"{hallucinated} hallucinated skills")
    if score_std_dev < 5:
        issues.append(f"Score std dev {score_std_dev:.1f} (target: >5)")
    if top_match_score < 60:
        issues.append(f"Top match score {top_match_score} (target: >=60)")

    return {
        "profile": profile_name,
        "profile_name": profile_json.get("name", profile_name),
        "total_matches": len(matches),
        "matches_above_40": matches_above_40,
        "top_match_score": top_match_score,
        "avg_top_10_score": round(avg_top_10, 1),
        "score_std_dev": round(score_std_dev, 1),
        "title_relevance_pct": round(title_relevance_pct, 1),
        "avg_skill_overlap": round(avg_skill_overlap, 1),
        "hallucinated_skills": hallucinated,
        "location_compliance_pct": round(location_compliance_pct, 1),
        "fraudulent_matches": fraudulent_matches,
        "stale_matches": stale_matches,
        "embedding_coverage_pct": round(embedding_coverage_pct, 1),
        "pass": len(issues) == 0,
        "issues": issues,
        "top_5_matches": top_5_details,
    }


def run_validation(profile_filter: str, output_dir: str) -> None:
    profiles = load_profiles(profile_filter)
    if not profiles:
        logger.error("No profiles found matching filter: %s", profile_filter)
        return

    session = get_session_factory()()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    total_active_jobs = (
        session.execute(
            select(func.count(Job.id)).where(Job.is_active.is_(True))
        ).scalar()
        or 0
    )

    results = []

    try:
        for profile_name, profile_json in profiles:
            logger.info("Testing profile: %s", profile_name)

            # Create temporary user + candidate + profile
            test_email = profile_json["basics"]["email"]
            user = User(email=test_email, password_hash="test-validation-only")
            session.add(user)
            session.flush()

            candidate = Candidate(
                user_id=user.id,
                first_name=profile_json["basics"]["name"].split()[0],
                last_name=profile_json["basics"]["name"].split()[-1],
                desired_job_types=",".join(
                    profile_json.get("preferences", {}).get("desired_titles", [])
                ),
                desired_locations=",".join(
                    profile_json.get("preferences", {}).get("desired_locations", [])
                ),
                remote_preference=profile_json.get("preferences", {}).get(
                    "remote_preference", "any"
                ),
                desired_salary_min=profile_json.get("preferences", {}).get(
                    "desired_salary_min"
                ),
                desired_salary_max=profile_json.get("preferences", {}).get(
                    "desired_salary_max"
                ),
            )
            session.add(candidate)
            session.flush()

            cp = CandidateProfile(
                user_id=user.id,
                version=1,
                profile_json=profile_json,
            )
            session.add(cp)
            session.flush()

            # Run matching
            try:
                matches = compute_matches(session, user.id, cp.version)
                matches_sorted = sorted(
                    matches, key=lambda m: m.match_score, reverse=True
                )
                result = evaluate_matches(
                    profile_name, profile_json, matches_sorted, session
                )
                results.append(result)
                logger.info(
                    "  %s: %d matches, top=%d, pass=%s",
                    profile_name,
                    result["total_matches"],
                    result["top_match_score"],
                    result["pass"],
                )
            except Exception as exc:
                logger.error("  %s: matching failed — %s", profile_name, exc)
                results.append(
                    {
                        "profile": profile_name,
                        "profile_name": profile_json.get("name", profile_name),
                        "error": str(exc),
                        "pass": False,
                    }
                )

            # Rollback the temp data
            session.rollback()

    finally:
        session.close()

    # Summary
    passed = sum(1 for r in results if r.get("pass"))
    failed = len(results) - passed
    avg_score = sum(
        r.get("avg_top_10_score", 0) for r in results if "error" not in r
    ) / max(len([r for r in results if "error" not in r]), 1)

    report = {
        "timestamp": datetime.now(UTC).isoformat(),
        "total_active_jobs": total_active_jobs,
        "profiles_tested": len(results),
        "results": results,
        "summary": {
            "profiles_passed": passed,
            "profiles_failed": failed,
            "avg_match_score": round(avg_score, 1),
            "overall_pass": failed == 0,
        },
    }

    # Write JSON report
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    json_path = output_path / f"match_quality_report_{ts}.json"
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    logger.info("JSON report written to: %s", json_path)

    # Write Markdown report
    md_path = output_path / f"match_quality_report_{ts}.md"
    with open(md_path, "w") as f:
        f.write("# Winnow Match Quality Report\n\n")
        f.write(f"Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M')} UTC\n\n")
        f.write(
            f"## Overall: {'PASS' if failed == 0 else 'FAIL'} "
            f"({passed}/{len(results)} profiles passed)\n\n"
        )
        hdr = "| Profile | >=40 | Top | Avg10 | Title% | Skills | Loc% | Pass |\n"
        sep = "|---------|------|-----|------|--------|--------|------|------|\n"
        f.write(hdr)
        f.write(sep)
        for r in results:
            if "error" in r:
                f.write(f"| {r['profile_name']} | ERROR | - | - | - | - | - | FAIL |\n")
            else:
                name = r["profile_name"]
                pf = "PASS" if r["pass"] else "FAIL"
                f.write(
                    f"| {name}"
                    f" | {r['matches_above_40']}"
                    f" | {r['top_match_score']}"
                    f" | {r['avg_top_10_score']}"
                    f" | {r['title_relevance_pct']}%"
                    f" | {r['avg_skill_overlap']}"
                    f" | {r['location_compliance_pct']}%"
                    f" | {pf} |\n"
                )

        # Issues
        all_issues = [issue for r in results for issue in r.get("issues", [])]
        f.write("\n## Issues Found\n\n")
        if all_issues:
            for issue in all_issues:
                f.write(f"- {issue}\n")
        else:
            f.write("None\n")

    logger.info("Markdown report written to: %s", md_path)


def main():
    parser = argparse.ArgumentParser(description="Match quality validation")
    parser.add_argument(
        "--profiles",
        default="all",
        help="Profile filter: 'all' or comma-separated IDs (01,02,03)",
    )
    parser.add_argument("--output-dir", default="reports/", help="Report output dir")
    args = parser.parse_args()

    run_validation(args.profiles, args.output_dir)


if __name__ == "__main__":
    main()
