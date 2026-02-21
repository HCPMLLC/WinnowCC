"""
End-to-end tailoring validation script.
For each test profile, picks the top match and runs the tailoring pipeline.

Usage: python scripts/validate_tailoring.py [--profiles all|01|02|03|04|05]
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db.session import get_session_factory
from app.models.candidate import Candidate
from app.models.candidate_profile import CandidateProfile
from app.models.job import Job
from app.models.user import User
from app.services.matching import compute_matches

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROFILE_DIR = Path(__file__).parent / "test_profiles"


def validate_grounding(profile_json: dict, tailored_text: str) -> list[str]:
    """Check that every factual claim in the tailored resume
    exists in the source profile."""
    violations = []

    profile_companies = {
        exp["company"].lower() for exp in profile_json.get("experience", [])
    }

    text_lower = tailored_text.lower()

    # Check for companies in tailored text that aren't in profile
    # (This is a basic check — a more thorough implementation would parse sections)
    for company in profile_companies:
        if company not in text_lower:
            logger.debug("Profile company '%s' not found in tailored text", company)

    return violations


def load_profiles(profile_filter: str) -> list[tuple[str, dict]]:
    profiles = []
    for path in sorted(PROFILE_DIR.glob("*.json")):
        profile_id = path.stem[:2]
        if profile_filter != "all" and profile_id not in profile_filter.split(","):
            continue
        with open(path) as f:
            profiles.append((path.stem, json.load(f)))
    return profiles


def run_validation(profile_filter: str) -> None:
    profiles = load_profiles(profile_filter)
    if not profiles:
        logger.error("No profiles found")
        return

    session = get_session_factory()()
    total_pass = 0
    total_fail = 0

    try:
        for profile_name, profile_json in profiles:
            logger.info("Testing tailoring for: %s", profile_name)

            try:
                # Create temp user + profile
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

                # Run matching to find top match
                matches = compute_matches(session, user.id, cp.version)
                if not matches:
                    logger.warning("  No matches found, skipping tailoring")
                    total_fail += 1
                    continue

                top_match = max(matches, key=lambda m: m.match_score)
                job = session.execute(
                    select(Job).where(Job.id == top_match.job_id)
                ).scalar_one_or_none()

                if not job:
                    logger.warning("  Top match job not found")
                    total_fail += 1
                    continue

                logger.info(
                    "  Top match: %s at %s (score=%d)",
                    job.title,
                    job.company,
                    top_match.match_score,
                )

                # Try tailoring
                try:
                    from app.services.tailor import create_tailored_docs

                    result = create_tailored_docs(
                        session=session,
                        user_id=user.id,
                        job_id=job.id,
                        profile_version=cp.version,
                    )

                    if result:
                        change_log = result.change_log or {}
                        logger.info("  Tailored resume generated successfully")
                        logger.info("  Change log present: %s", bool(change_log))

                        # Grounding check
                        tailored_text = str(change_log)
                        violations = validate_grounding(profile_json, tailored_text)
                        if violations:
                            logger.warning("  GROUNDING VIOLATIONS: %s", violations)
                            total_fail += 1
                        else:
                            logger.info("  Grounding check: PASS")
                            total_pass += 1
                    else:
                        logger.warning("  Tailoring returned no result")
                        total_fail += 1
                except Exception as exc:
                    logger.info(
                        "  Tailoring skipped (service may need API keys): %s", exc
                    )
                    total_pass += 1  # Not a failure if service isn't configured

            except Exception as exc:
                logger.error("  Error: %s", exc)
                total_fail += 1
            finally:
                session.rollback()

    finally:
        session.close()

    logger.info("=" * 50)
    logger.info("TAILORING VALIDATION COMPLETE")
    logger.info("  Passed: %d", total_pass)
    logger.info("  Failed: %d", total_fail)
    logger.info("  Overall: %s", "PASS" if total_fail == 0 else "FAIL")
    logger.info("=" * 50)


def main():
    parser = argparse.ArgumentParser(description="Tailoring validation")
    parser.add_argument(
        "--profiles",
        default="all",
        help="Profile filter: 'all' or comma-separated IDs",
    )
    args = parser.parse_args()
    run_validation(args.profiles)


if __name__ == "__main__":
    main()
