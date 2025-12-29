"""Analytics API endpoints for GitStats integration.

Authorization follows the same pattern as the Sources tab:
- Org-level endpoints: enforce_any_source_admin (Super Admin OR admin of any source)
- Codebase-level endpoints: enforce_asset_action with "asset.manage" (admin only)

The list endpoint filters results so Source Admins only see codebases they admin.
Super Admins see all codebases.
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.api.auth import UserToken
from app.api.session import CurrentSession
from app.authorization.fastapi import enforce_any_source_admin, enforce_asset_action
from app.schemas.analytics_schema import (
    ActivityResponse,
    AnalyticsOverview,
    AnalyticsStatus,
    BranchesResponse,
    CodebasesListResponse,
    OrgAnalyticsSummary,
    OwnershipResponse,
)
from app.services.analytics_service import AnalyticsService

router = APIRouter()


# === Organization-Level Endpoints ===
# These use full paths starting with /analytics/


@router.get(
    "/analytics/summary",
    summary="Get organization analytics summary",
    response_model=OrgAnalyticsSummary,
)
def get_analytics_summary(
    session: CurrentSession,
    user: UserToken,
) -> OrgAnalyticsSummary:
    """Get aggregate analytics metrics across all codebases the user can admin."""
    enforce_any_source_admin(db=session, user=user)

    service = AnalyticsService(session, user)
    data = service.get_org_summary()

    if not data:
        return OrgAnalyticsSummary(
            organization_id=str(user.organization_id),
            total_codebases=0,
            codebases_with_analytics=0,
            generated_at=datetime.now(timezone.utc),
        )

    return OrgAnalyticsSummary(**data)


@router.get(
    "/analytics/codebases",
    summary="List codebases with analytics status",
    response_model=CodebasesListResponse,
)
def get_analytics_codebases(
    session: CurrentSession,
    user: UserToken,
) -> CodebasesListResponse:
    """Get list of codebases with analytics status.

    Super Admins see all codebases.
    Source Admins see only codebases they are admin of.
    """
    enforce_any_source_admin(db=session, user=user)

    service = AnalyticsService(session, user)
    data = service.get_codebases_list()  # Filtered by admin access

    if not data:
        return CodebasesListResponse(
            organization_id=str(user.organization_id),
            codebases=[],
            generated_at=datetime.now(timezone.utc),
        )

    return CodebasesListResponse(**data)


# === Codebase-Level Endpoints ===
# These use full paths starting with /codebases/{codebase_id}/analytics/
# This follows the same pattern as source_users.py which uses /sources/{source_id}/users


@router.get(
    "/codebases/{codebase_id}/analytics/overview",
    summary="Get codebase analytics overview",
    response_model=AnalyticsOverview,
)
def get_codebase_overview(
    session: CurrentSession,
    user: UserToken,
    codebase_id: UUID,
) -> AnalyticsOverview:
    """Get overview metrics for a specific codebase (25 fields)."""
    # Uses asset.manage action - only asset_admin role has this permission
    enforce_asset_action(
        db=session, user=user, asset_id=codebase_id, action_key="asset.manage"
    )

    service = AnalyticsService(session, user)
    data = service.get_overview(str(codebase_id))

    if not data:
        raise HTTPException(
            status_code=404, detail="Analytics not found for this codebase"
        )

    return AnalyticsOverview(**data)


@router.get(
    "/codebases/{codebase_id}/analytics/branches",
    summary="Get codebase branch analytics",
    response_model=BranchesResponse,
)
def get_codebase_branches(
    session: CurrentSession,
    user: UserToken,
    codebase_id: UUID,
) -> BranchesResponse:
    """Get branch metrics for a specific codebase (23 fields per branch)."""
    enforce_asset_action(
        db=session, user=user, asset_id=codebase_id, action_key="asset.manage"
    )

    service = AnalyticsService(session, user)
    data = service.get_branches(str(codebase_id))

    if not data:
        raise HTTPException(
            status_code=404, detail="Analytics not found for this codebase"
        )

    return BranchesResponse(**data)


@router.get(
    "/codebases/{codebase_id}/analytics/activity",
    summary="Get codebase daily activity",
    response_model=ActivityResponse,
)
def get_codebase_activity(
    session: CurrentSession,
    user: UserToken,
    codebase_id: UUID,
) -> ActivityResponse:
    """Get daily activity metrics for a specific codebase (12 fields per day)."""
    enforce_asset_action(
        db=session, user=user, asset_id=codebase_id, action_key="asset.manage"
    )

    service = AnalyticsService(session, user)
    data = service.get_activity(str(codebase_id))

    if not data:
        raise HTTPException(
            status_code=404, detail="Analytics not found for this codebase"
        )

    return ActivityResponse(**data)


@router.get(
    "/codebases/{codebase_id}/analytics/ownership",
    summary="Get code ownership data",
    response_model=OwnershipResponse,
)
def get_codebase_ownership(
    session: CurrentSession,
    user: UserToken,
    codebase_id: UUID,
) -> OwnershipResponse:
    """Get code ownership and contributor data for a specific codebase."""
    enforce_asset_action(
        db=session, user=user, asset_id=codebase_id, action_key="asset.manage"
    )

    service = AnalyticsService(session, user)
    data = service.get_ownership(str(codebase_id))

    if not data:
        raise HTTPException(
            status_code=404, detail="Analytics not found for this codebase"
        )

    return OwnershipResponse(**data)


@router.get(
    "/codebases/{codebase_id}/analytics/status",
    summary="Get analytics status",
    response_model=AnalyticsStatus,
)
def get_analytics_status(
    session: CurrentSession,
    user: UserToken,
    codebase_id: UUID,
) -> AnalyticsStatus:
    """Get analytics generation status for a specific codebase."""
    enforce_asset_action(
        db=session, user=user, asset_id=codebase_id, action_key="asset.manage"
    )

    service = AnalyticsService(session, user)
    data = service.get_status(str(codebase_id))

    return AnalyticsStatus(**data)

