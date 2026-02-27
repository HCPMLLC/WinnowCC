"""API schemas."""

from app.schemas.jobs import JobResponse
from app.schemas.matches import MatchesRefreshResponse, MatchResponse
from app.schemas.profile import (
    CandidateProfilePayload,
    CandidateProfileResponse,
    CandidateProfileUpdateRequest,
    ParseJobResponse,
)
from app.schemas.resume import ResumeDocumentResponse, ResumeUploadResponse
from app.schemas.tailor import TailorRequestResponse, TailorStatusResponse
from app.schemas.trust import (
    AdminTrustRecordResponse,
    AdminTrustUpdateRequest,
    AdminTrustUpdateResponse,
    TrustReviewRequestResponse,
    TrustStatusResponse,
)

__all__ = [
    "CandidateProfilePayload",
    "CandidateProfileResponse",
    "CandidateProfileUpdateRequest",
    "AuthRequest",
    "AuthMeResponse",
    "AuthLogoutResponse",
    "CandidateUpsertRequest",
    "CandidateResponse",
    "ParseJobResponse",
    "JobResponse",
    "MatchResponse",
    "MatchesRefreshResponse",
    "ResumeDocumentResponse",
    "ResumeUploadResponse",
    "TailorRequestResponse",
    "TailorStatusResponse",
    "TrustStatusResponse",
    "TrustReviewRequestResponse",
    "AdminTrustRecordResponse",
    "AdminTrustUpdateRequest",
    "AdminTrustUpdateResponse",
]
from app.schemas.auth import AuthLogoutResponse, AuthMeResponse, AuthRequest
from app.schemas.onboarding import CandidateResponse, CandidateUpsertRequest
