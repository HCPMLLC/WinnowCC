"""
Sieve application flow orchestration.

Manages the conversational application experience, integrating
resume parsing, profile completion, custom questions, and cross-job
matching.
"""

import json
import logging
import os
import secrets
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.career_page import CareerPage
from app.models.career_page_application import (
    ApplicationStatus,
    CareerPageApplication,
)
from app.models.job import Job
from app.models.job_custom_question import (
    CandidateQuestionResponse,
    JobCustomQuestion,
)
from app.services.cross_job_matcher import (
    generate_cross_job_recommendations,
)
from app.services.profile_completeness import (
    calculate_completeness_score,
    generate_completeness_prompt,
    get_job_specific_requirements,
    get_missing_fields,
    get_profile_data_from_parsed_resume,
)

logger = logging.getLogger(__name__)


def _get_anthropic_client():
    """Get Anthropic client for LLM calls."""
    import anthropic

    return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), max_retries=3)


def start_application(
    db: Session,
    career_page_id: UUID,
    job_id: int,
    email: str | None = None,
    source_url: str | None = None,
    utm_params: dict | None = None,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> CareerPageApplication:
    """Start a new application session."""
    session_token = secrets.token_urlsafe(32)

    # Check for existing application with same email
    if email:
        existing = db.execute(
            select(CareerPageApplication).where(
                and_(
                    CareerPageApplication.career_page_id == career_page_id,
                    CareerPageApplication.job_id == job_id,
                    CareerPageApplication.email == email,
                    CareerPageApplication.status != ApplicationStatus.ABANDONED,
                )
            )
        )
        existing_app = existing.scalar_one_or_none()
        if existing_app:
            return existing_app

    # Get job details for context
    result = db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise ValueError("Job not found")

    # Get job-specific requirements
    job_requirements = get_job_specific_requirements(job)

    # Initialize missing fields
    initial_missing = get_missing_fields({})
    initial_missing.extend(job_requirements)

    application = CareerPageApplication(
        career_page_id=career_page_id,
        job_id=job_id,
        session_token=session_token,
        email=email,
        status=ApplicationStatus.STARTED,
        completeness_score=0,
        missing_fields=initial_missing,
        conversation_history=[],
        source_url=source_url,
        utm_params=utm_params,
        user_agent=user_agent,
        ip_address=ip_address,
    )

    db.add(application)
    db.commit()
    db.refresh(application)

    logger.info(
        "Started application %s for job %s",
        application.id,
        job_id,
    )
    return application


def generate_welcome_message(
    db: Session,
    application: CareerPageApplication,
    sieve_config: dict[str, Any],
) -> str:
    """Generate Sieve's welcome message for the application."""
    result = db.execute(select(Job).where(Job.id == application.job_id))
    job = result.scalar_one()

    cp_result = db.execute(
        select(CareerPage).where(CareerPage.id == application.career_page_id)
    )
    career_page = cp_result.scalar_one()

    sieve_name = sieve_config.get("name", "Sieve")
    tone = sieve_config.get("tone", "professional")
    custom_welcome = sieve_config.get("welcome_message", "")

    prompt = f"""Generate a brief, warm welcome message for a job applicant.

Context:
- Assistant name: {sieve_name}
- Tone: {tone}
- Job title: {job.title}
- Company: {career_page.name}
- Custom welcome (incorporate if provided): {custom_welcome}

Requirements:
- Keep it to 2-3 sentences
- Be welcoming and professional
- Mention you'll help them apply for the {job.title} role
- Invite them to upload their resume or tell you about themselves
- Don't ask multiple questions

Output only the message, no quotes or formatting."""

    try:
        client = _get_anthropic_client()
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        welcome = response.content[0].text.strip()
    except Exception as e:
        logger.error("Error generating welcome: %s", e)
        welcome = (
            f"Hi! I'm {sieve_name}, and I'm here to help you "
            f"apply for the {job.title} position. You can upload "
            f"your resume or just tell me about your background "
            f"to get started."
        )

    # Add to conversation history
    application.conversation_history = [
        {
            "role": "assistant",
            "content": welcome,
            "timestamp": datetime.utcnow().isoformat(),
        }
    ]

    db.commit()
    return welcome


def process_resume_upload(
    db: Session,
    application: CareerPageApplication,
    parsed_resume_data: dict[str, Any],
    resume_file_url: str,
) -> tuple[str, int, list[dict]]:
    """
    Process uploaded resume and generate Sieve response.

    Returns (sieve_response, completeness_score, missing_fields).
    """
    profile_data = get_profile_data_from_parsed_resume(parsed_resume_data)

    completeness = calculate_completeness_score(profile_data)
    missing = get_missing_fields(profile_data)

    # Add job-specific requirements
    result = db.execute(select(Job).where(Job.id == application.job_id))
    job = result.scalar_one()
    job_requirements = get_job_specific_requirements(job)

    for req in job_requirements:
        if req["field"] not in profile_data:
            missing.append(req)

    # Update application
    application.resume_file_url = resume_file_url
    application.resume_parsed_data = parsed_resume_data
    application.completeness_score = completeness
    application.missing_fields = missing
    application.status = ApplicationStatus.RESUME_UPLOADED
    application.last_activity_at = datetime.utcnow()

    # Generate Sieve response
    sieve_response = _generate_resume_response(
        profile_data, completeness, missing, job.title
    )

    # Add to conversation
    history = list(application.conversation_history or [])
    history.append(
        {
            "role": "user",
            "content": "[Uploaded resume]",
            "timestamp": datetime.utcnow().isoformat(),
            "type": "resume_upload",
        }
    )
    history.append(
        {
            "role": "assistant",
            "content": sieve_response,
            "timestamp": datetime.utcnow().isoformat(),
        }
    )
    application.conversation_history = history

    db.commit()

    return sieve_response, completeness, missing


def _generate_resume_response(
    profile_data: dict,
    completeness: int,
    missing: list,
    job_title: str,
) -> str:
    """Generate Sieve's response to resume upload."""
    name = profile_data.get("full_name", "")
    current_title = profile_data.get("current_title", "")
    required_missing = [f for f in missing if f["importance"] == "required"]

    prompt = f"""Generate a brief, encouraging response to a resume upload.

Context:
- Candidate name: {name or "the candidate"}
- Current/recent title: {current_title or "not specified"}
- Profile completeness: {completeness}%
- Job applying for: {job_title}
- Required fields still needed: {[f["label"] for f in required_missing[:3]]}

Requirements:
- Acknowledge you received their resume
- If name is available, use it once
- Comment briefly on their background (1 sentence)
- If completeness < 80%, naturally ask about ONE missing required field
- Keep total response to 3-4 sentences
- Be warm and encouraging

Output only the message."""

    try:
        client = _get_anthropic_client()
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=250,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.error("Error generating resume response: %s", e)

        if completeness >= 80:
            return (
                f"Thanks for sharing your resume! Your background "
                f"looks great for the {job_title} role. Just a "
                f"couple more quick questions and we'll have your "
                f"application ready."
            )
        first_missing = (
            required_missing[0]["label"] if required_missing else "work history"
        )
        return (
            f"Thanks for sharing your resume! I can see you have "
            f"relevant experience. To complete your application, "
            f"could you tell me more about your "
            f"{first_missing.lower()}?"
        )


def process_chat_message(
    db: Session,
    application: CareerPageApplication,
    user_message: str,
) -> tuple[str, int, list[str], list[str], bool]:
    """
    Process a chat message from the candidate.

    Returns (sieve_response, completeness_score, fields_updated,
    questions_answered, suggest_submit).
    """
    profile_data = dict(application.resume_parsed_data or {})
    missing_fields = list(application.missing_fields or [])

    custom_questions = _get_unanswered_questions(db, application)

    context = generate_completeness_prompt(
        missing_fields, custom_questions, profile_data
    )

    result = db.execute(select(Job).where(Job.id == application.job_id))
    job = result.scalar_one()

    recent_history = (
        application.conversation_history[-6:]
        if application.conversation_history
        else []
    )

    sieve_response, extracted_data = _generate_chat_response(
        user_message,
        recent_history,
        context,
        job.title,
        missing_fields,
        custom_questions,
    )

    fields_updated: list[str] = []
    questions_answered: list[str] = []

    # Update profile fields
    if extracted_data.get("profile_updates"):
        for field, value in extracted_data["profile_updates"].items():
            profile_data[field] = value
            fields_updated.append(field)

            for mf in missing_fields:
                if mf["field"] == field:
                    mf["answered"] = True

    # Update custom question responses
    if extracted_data.get("question_responses"):
        q_responses = dict(application.question_responses or {})
        for q_id, response in extracted_data["question_responses"].items():
            q_responses[q_id] = response
            questions_answered.append(q_id)
        application.question_responses = q_responses

    new_completeness = calculate_completeness_score(profile_data)

    application.resume_parsed_data = profile_data
    application.completeness_score = new_completeness
    application.missing_fields = missing_fields
    application.status = ApplicationStatus.PROFILE_BUILDING
    application.last_activity_at = datetime.utcnow()

    # Add to conversation history
    history = list(application.conversation_history or [])
    history.append(
        {
            "role": "user",
            "content": user_message,
            "timestamp": datetime.utcnow().isoformat(),
        }
    )
    history.append(
        {
            "role": "assistant",
            "content": sieve_response,
            "timestamp": datetime.utcnow().isoformat(),
        }
    )
    application.conversation_history = history

    db.commit()

    can_submit = application.can_submit
    suggest_submit = new_completeness >= 85 and can_submit

    return (
        sieve_response,
        new_completeness,
        fields_updated,
        questions_answered,
        suggest_submit,
    )


def _get_unanswered_questions(
    db: Session,
    application: CareerPageApplication,
) -> list[dict]:
    """Get custom questions not yet answered."""
    result = db.execute(
        select(JobCustomQuestion)
        .where(
            and_(
                JobCustomQuestion.job_id == application.job_id,
                JobCustomQuestion.active == True,  # noqa: E712
            )
        )
        .order_by(JobCustomQuestion.order_index)
    )
    questions = list(result.scalars().all())

    answered_ids = set((application.question_responses or {}).keys())

    return [
        {
            "question_id": str(q.id),
            "question_text": q.question_text,
            "question_type": q.question_type,
            "options": q.options,
            "required": q.required,
            "sieve_prompt_hint": q.sieve_prompt_hint,
            "answered": str(q.id) in answered_ids,
        }
        for q in questions
        if str(q.id) not in answered_ids
    ]


def _generate_chat_response(
    user_message: str,
    conversation_history: list,
    context: str,
    job_title: str,
    missing_fields: list,
    custom_questions: list,
) -> tuple[str, dict]:
    """Generate Sieve response and extract profile data."""
    history_str = "\n".join(
        [f"{msg['role'].title()}: {msg['content']}" for msg in conversation_history]
    )

    fields_to_extract = [f["field"] for f in missing_fields if not f.get("answered")]
    questions_to_extract = [q["question_id"] for q in custom_questions]

    prompt = f"""You are Sieve, a friendly AI assistant helping \
someone apply for a {job_title} position.

CONVERSATION SO FAR:
{history_str}

USER'S LATEST MESSAGE:
{user_message}

CONTEXT (what we still need):
{context}

INSTRUCTIONS:
1. Extract any profile information the user provided
2. Check if they answered any custom screening questions
3. Generate a natural, brief response (2-3 sentences max)
4. If profile is nearly complete, encourage them
5. If missing critical info, ask ONE follow-up question
6. Be warm, professional, and efficient

OUTPUT FORMAT (JSON):
{{
    "response": "Your conversational response here",
    "profile_updates": {{
        "field_name": "extracted_value"
    }},
    "question_responses": {{
        "question_id": {{"response": "extracted answer", \
"confidence": 90}}
    }}
}}

Fields to look for: {fields_to_extract}
Question IDs to match: {questions_to_extract}

Output ONLY the JSON, no other text."""

    try:
        client = _get_anthropic_client()
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = response.content[0].text.strip()

        # Clean up JSON if wrapped in markdown
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]

        data = json.loads(response_text)

        return data.get("response", ""), {
            "profile_updates": data.get("profile_updates", {}),
            "question_responses": data.get("question_responses", {}),
        }

    except Exception as e:
        logger.error("Error generating chat response: %s", e)
        return (
            "Thanks for sharing that! Let me note that down. "
            "Is there anything else you'd like to add about "
            "your background?",
            {},
        )


def generate_cross_job_pitch(
    db: Session,
    application: CareerPageApplication,
) -> tuple[str, list[dict]]:
    """Generate cross-job recommendations and Sieve's pitch."""
    cp_result = db.execute(
        select(CareerPage).where(CareerPage.id == application.career_page_id)
    )
    career_page = cp_result.scalar_one()

    recommendations = generate_cross_job_recommendations(
        db,
        application.candidate_id,
        application.job_id,
        career_page.tenant_id,
        career_page.tenant_type,
        limit=3,
    )

    if not recommendations:
        return "", []

    rec_list = [
        {
            "job_id": rec.recommended_job_id,
            "ips_score": rec.ips_score,
            "explanation": rec.explanation,
        }
        for rec in recommendations
    ]

    # Get job titles
    job_ids = [rec.recommended_job_id for rec in recommendations]
    jobs_result = db.execute(select(Job).where(Job.id.in_(job_ids)))
    jobs_map = {j.id: j for j in jobs_result.scalars().all()}

    for rec in rec_list:
        job_obj = jobs_map.get(rec["job_id"])
        if job_obj:
            rec["title"] = job_obj.title
            rec["location"] = job_obj.location

    # Get applied job title
    job_result = db.execute(select(Job).where(Job.id == application.job_id))
    job = job_result.scalar_one()

    pitch = _generate_pitch_message(job.title, rec_list)

    application.cross_job_recommendations = rec_list
    db.commit()

    return pitch, rec_list


def _generate_pitch_message(
    applied_job_title: str,
    recommendations: list[dict],
) -> str:
    """Generate Sieve's cross-job pitch message."""
    if not recommendations:
        return ""

    top_rec = recommendations[0]

    prompt = f"""Generate a brief, excited message suggesting \
another job to a candidate.

Context:
- They just applied for: {applied_job_title}
- We're suggesting: {top_rec.get("title", "another role")}
- Match score: {top_rec["ips_score"]}%
- Why it's a fit: {top_rec.get("explanation", "")}
- Additional recommendations: {len(recommendations) - 1}

Requirements:
- 2-3 sentences max
- Sound genuinely excited about the match
- Mention the specific role and score
- If there are more recommendations, hint at them
- Don't be pushy

Output only the message."""

    try:
        client = _get_anthropic_client()
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.error("Error generating pitch: %s", e)
        return (
            f"Great news! Based on your profile, you'd be an "
            f"excellent fit for our "
            f"{top_rec.get('title', 'other open')} role too — "
            f"I'm seeing a {top_rec['ips_score']}% match!"
        )


def submit_application(
    db: Session,
    application: CareerPageApplication,
    additional_job_ids: list[int] | None = None,
) -> dict[str, Any]:
    """
    Submit the completed application.

    Marks application as completed and optionally records
    additional job interest.
    """
    if not application.can_submit:
        raise ValueError("Application not ready for submission")

    # Mark as completed
    application.status = ApplicationStatus.COMPLETED
    application.completed_at = datetime.utcnow()

    # Save custom question responses
    _save_question_responses(db, application)

    # Apply to additional jobs if requested
    additional: list[int] = []
    if additional_job_ids:
        for job_id in additional_job_ids:
            additional.append(job_id)
        application.additional_applications = additional_job_ids

    # Update career page application count
    cp_result = db.execute(
        select(CareerPage).where(CareerPage.id == application.career_page_id)
    )
    career_page = cp_result.scalar_one()
    career_page.application_count = (
        (career_page.application_count or 0) + 1 + len(additional)
    )

    db.commit()

    return {
        "application_id": str(application.id),
        "additional_applications": additional,
    }


def _save_question_responses(
    db: Session,
    application: CareerPageApplication,
) -> None:
    """Save custom question responses to database."""
    if not application.question_responses:
        return

    for question_id_str, response_data in application.question_responses.items():
        try:
            question_id = UUID(question_id_str)
        except (ValueError, TypeError):
            continue

        response = CandidateQuestionResponse(
            candidate_id=application.candidate_id,
            job_id=application.job_id,
            question_id=question_id,
            response_text=response_data.get("response"),
            confidence_score=response_data.get("confidence"),
            answered_via="sieve",
        )
        db.add(response)

    db.commit()
