"""Widget API key management."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.user import User
from app.schemas.widget import (
    WidgetApiKeyCreate,
    WidgetApiKeyCreatedResponse,
    WidgetApiKeyListResponse,
    WidgetApiKeyResponse,
)
from app.services.auth import get_current_user
from app.services.widget_auth import (
    create_api_key,
    delete_api_key,
    list_api_keys,
    revoke_api_key,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/widget-keys", tags=["widget-keys"])


def _get_tenant_info(user: User) -> tuple[int, str]:
    if user.employer_profile:
        return user.employer_profile.id, "employer"
    elif user.recruiter_profile:
        return user.recruiter_profile.id, "recruiter"
    raise HTTPException(
        status_code=403, detail="Requires employer or recruiter account"
    )


@router.get("", response_model=WidgetApiKeyListResponse)
async def list_keys(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    tenant_id, tenant_type = _get_tenant_info(user)
    keys = await list_api_keys(db, tenant_id, tenant_type)
    return WidgetApiKeyListResponse(
        keys=[WidgetApiKeyResponse.model_validate(k) for k in keys],
        total=len(keys),
    )


@router.post(
    "", response_model=WidgetApiKeyCreatedResponse, status_code=201
)
async def create_key(
    data: WidgetApiKeyCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    tenant_id, tenant_type = _get_tenant_info(user)
    key_record, full_key = await create_api_key(
        db,
        tenant_id,
        tenant_type,
        name=data.name,
        allowed_domains=data.allowed_domains,
        environment=data.environment,
    )
    response = WidgetApiKeyCreatedResponse.model_validate(key_record)
    response.api_key = full_key
    return response


@router.post("/{key_id}/revoke", status_code=204)
async def revoke_key_endpoint(
    key_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    tenant_id, tenant_type = _get_tenant_info(user)
    await revoke_api_key(db, key_id, tenant_id, tenant_type)


@router.delete("/{key_id}", status_code=204)
async def delete_key_endpoint(
    key_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    tenant_id, tenant_type = _get_tenant_info(user)
    await delete_api_key(db, key_id, tenant_id, tenant_type)
