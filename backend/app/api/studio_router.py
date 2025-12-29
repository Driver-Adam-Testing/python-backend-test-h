from fastapi import APIRouter

from app.api.routes.legacy.schema import graphql_router, sandbox_router
from app.api.routes.v1 import (
    admin_sources,
    analytics,
    codebase,
    content,
    git_provider,
    organization,
    organization_settings,
    source_teams,
    source_users,
    tags,
    teams,
    upload,
    usage,
    user,
    user_profile,
    user_sources,
    user_teams,
)

# ruff: noqa: F401
from app.api.routes.v2 import (
    about_you_survey,
    autodocs,
    chat,
    codebase_card,
    contents,
    convenience_endpoints,
    document_sources,
    onboarding_checklist,
    primary_asset_tags,
    primary_assets,
    versions,
)
from app.api.routes.v2 import (
    api_key as v2_api_key,
)
from app.api.routes.v2 import (
    router as v2_router,
)
from app.api.routes.v2 import (
    tags as v2_tags,
)
from app.core.config import settings

studio_router = APIRouter()

studio_router.include_router(graphql_router, prefix="/graphql", tags=["legacy-graphql"])
studio_router.include_router(v2_api_key.router, prefix="/api_key", tags=["api_key"])
studio_router.include_router(
    git_provider.router, prefix="/git-provider", tags=["git-provider"]
)
studio_router.include_router(content.router, prefix="/content", tags=["content"])
studio_router.include_router(codebase.router, prefix="/codebases", tags=["codebase"])
studio_router.include_router(tags.router, prefix="/tags", tags=["tags"])
studio_router.include_router(teams.router, prefix="/teams", tags=["teams"])
studio_router.include_router(
    source_users.router, tags=["source-users"]
)  # Source users routes (no prefix, uses /sources/{id}/users)
studio_router.include_router(
    source_teams.router, tags=["source-teams"]
)  # Source teams routes (no prefix, uses /sources/{id}/teams)
studio_router.include_router(
    analytics.router, tags=["analytics"]
)  # Analytics routes (no prefix, uses /analytics/* and /codebases/{id}/analytics/*)
studio_router.include_router(upload.router, prefix="/upload", tags=["upload"])
studio_router.include_router(usage.router, prefix="/usage", tags=["usage"])
studio_router.include_router(user.router, prefix="/user", tags=["user"])
studio_router.include_router(user_profile.router, prefix="/me", tags=["user-profile"])
studio_router.include_router(
    user_teams.router, prefix="/admin/users", tags=["admin-users"]
)
studio_router.include_router(
    user_sources.router, prefix="/admin/users", tags=["admin-users"]
)
studio_router.include_router(
    admin_sources.router, prefix="/admin/sources", tags=["admin-sources"]
)
studio_router.include_router(about_you_survey.router, tags=["about_you_survey"])
studio_router.include_router(onboarding_checklist.router, tags=["onboarding_checklist"])
studio_router.include_router(
    organization.router, prefix="/organization", tags=["organization"]
)
studio_router.include_router(
    organization_settings.router,
    prefix="/organization/settings",
    tags=["organization-settings"],
)
studio_router.include_router(v2_router.router, prefix="/node", tags=["node"])

if settings.ENVIRONMENT != "production":
    studio_router.include_router(
        sandbox_router, prefix="/sandbox", tags=["legacy-sandbox"]
    )

studio_router.include_router(chat.router, prefix="/chat", tags=["chat"])
studio_router.include_router(autodocs.router, prefix="/autodocs", tags=["autodocs"])
studio_router.include_router(
    codebase_card.router, prefix="/codebase_card", tags=["codebase_card"]
)
