"""Integration tests for analytics API endpoints.

Authorization follows the Sources tab pattern:
- Org-level: enforce_any_source_admin (Super Admin OR asset_admin on any codebase)
- Codebase-level: enforce_asset_action with asset.manage (asset_admin role)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from database.models import OrgMembership
from database.models_enums import OrgRole, PrimaryAssetRole, PrincipalKind
from fastapi.testclient import TestClient
from sqlmodel import Session, select

if TYPE_CHECKING:
    from app.auth.models import User

from app.test_factories import (
    Auth0UserFactory,
    PrimaryAssetFactory,
    PrimaryAssetRoleGrantFactory,
)


def create_mock_user(organization_id: str, user_id: str = "test-user-id") -> User:
    """Create a mock User object for testing."""
    from app.auth.models import User

    return User(
        org_id=organization_id,
        org_name="Test Organization",
        sub=user_id,
        iss="https://test.auth0.com/",
        aud=["test-audience"],
        iat=1234567890,
        exp=9999999999,
        scope="",
        azp="",
        permissions=[],
        user_email="test@example.com",
        user_full_name="Test User",
    )


@pytest.mark.integration
class TestAnalyticsOrgLevelAuthorization:
    """Tests for organization-level endpoint authorization."""

    @pytest.fixture
    def mock_analytics_service(self):
        """Mock the AnalyticsService for integration tests."""
        with patch("app.api.routes.v1.analytics.AnalyticsService") as mock:
            mock_instance = MagicMock()
            mock_instance.get_org_summary.return_value = {
                "organization_id": "test-org",
                "total_codebases": 1,
                "codebases_with_analytics": 1,
                "generated_at": "2024-06-15T10:00:00Z",
            }
            mock_instance.get_codebases_list.return_value = {
                "organization_id": "test-org",
                "codebases": [],
                "generated_at": "2024-06-15T10:00:00Z",
            }
            mock.return_value = mock_instance
            yield mock

    @pytest.mark.integration
    def test_super_admin_can_access_summary(
        self,
        integration_db_session: Session,
        mock_analytics_service,
    ):
        """Test that super admins can access org summary."""
        org_id = "test-org-id"

        # Create a super admin user
        super_admin = Auth0UserFactory.create(
            integration_db_session, organization_id=org_id
        )

        # Update org membership to make them super admin
        org_membership = integration_db_session.exec(
            select(OrgMembership).where(
                OrgMembership.user_id == super_admin.id,
                OrgMembership.org_id == org_id,
            )
        ).first()
        if org_membership:
            org_membership.role = OrgRole.org_super_admin
            integration_db_session.add(org_membership)
            integration_db_session.commit()

        # Create mock JWT user
        mock_user = create_mock_user(org_id, super_admin.id)

        # Mock the UserToken dependency and session
        with patch("app.api.auth.get_current_user", return_value=mock_user), patch(
            "app.api.session.get_session",
            return_value=integration_db_session,
        ):
            from app.api.routes.v1.analytics import get_analytics_summary

            # Call the endpoint
            result = get_analytics_summary(
                session=integration_db_session, user=mock_user
            )

            # Super admin should be able to access
            assert result.total_codebases == 1

    @pytest.mark.integration
    def test_source_admin_can_access_summary(
        self,
        integration_db_session: Session,
        mock_analytics_service,
    ):
        """Test that source admins (asset_admin on any codebase) can access org summary."""
        org_id = "test-org-id"

        # Create user with org_member role
        source_admin = Auth0UserFactory.create(
            integration_db_session, organization_id=org_id
        )

        # Create a codebase and grant asset_admin role
        codebase = PrimaryAssetFactory.create(
            integration_db_session, organization_id=org_id
        )
        PrimaryAssetRoleGrantFactory.create(
            integration_db_session,
            primary_asset_id=codebase.id,
            principal_kind=PrincipalKind.user,
            user_id=source_admin.id,
            role=PrimaryAssetRole.asset_admin,
            organization_id=org_id,
        )

        mock_user = create_mock_user(org_id, source_admin.id)

        with patch("app.api.auth.get_current_user", return_value=mock_user), patch(
            "app.api.session.get_session",
            return_value=integration_db_session,
        ):
            from app.api.routes.v1.analytics import get_analytics_summary

            result = get_analytics_summary(
                session=integration_db_session, user=mock_user
            )

            # Source admin should be able to access
            assert result.total_codebases == 1

    @pytest.mark.integration
    def test_regular_member_cannot_access_summary(
        self,
        integration_db_session: Session,
        mock_analytics_service,
    ):
        """Test that org members without admin roles cannot access org summary."""
        from fastapi import HTTPException

        org_id = "test-org-id"

        # Create user with only org_member role (no asset_admin grants)
        regular_member = Auth0UserFactory.create(
            integration_db_session, organization_id=org_id
        )

        mock_user = create_mock_user(org_id, regular_member.id)

        with patch("app.api.auth.get_current_user", return_value=mock_user), patch(
            "app.api.session.get_session",
            return_value=integration_db_session,
        ):
            from app.api.routes.v1.analytics import get_analytics_summary

            # Regular member should get 403
            with pytest.raises(HTTPException) as exc_info:
                get_analytics_summary(session=integration_db_session, user=mock_user)

            assert exc_info.value.status_code == 403


@pytest.mark.integration
class TestAnalyticsCodebaseLevelAuthorization:
    """Tests for codebase-level endpoint authorization."""

    @pytest.fixture
    def mock_analytics_service(self):
        """Mock the AnalyticsService for integration tests."""
        with patch("app.api.routes.v1.analytics.AnalyticsService") as mock:
            mock_instance = MagicMock()
            mock_instance.get_overview.return_value = {
                "codebase_id": "test-id",
                "display_name": "test-repo",
                "repository_name": "test-repo",
                "full_name": "owner/test-repo",
                "owner": "owner",
                "total_commits": 100,
                "total_contributors": 5,
                "total_branches": 3,
                "total_lines": 5000,
                "total_additions_lines": 8000,
                "total_deletions_lines": 3000,
                "total_sloc": 5000,
                "net_sloc": 2500,
                "current_sloc": 2500,
                "total_addition_bytes": 400000,
                "total_deletion_bytes": 150000,
                "avg_bytes_per_line": 50.0,
                "total_files": 42,
                "default_branch": "main",
                "primary_language": "Python",
                "first_commit_date": "2024-01-01T00:00:00Z",
                "last_commit_date": "2024-06-01T00:00:00Z",
                "collected_at": "2024-06-01T12:00:00Z",
                "last_updated_at": "2024-06-01T12:00:00Z",
            }
            mock.return_value = mock_instance
            yield mock

    @pytest.mark.integration
    def test_asset_admin_can_view_codebase_analytics(
        self,
        integration_db_session: Session,
        mock_analytics_service,
    ):
        """Test that asset_admin can view analytics for their codebase."""
        org_id = "test-org-id"

        # Create user
        asset_admin = Auth0UserFactory.create(
            integration_db_session, organization_id=org_id
        )

        # Create codebase with asset_admin grant
        codebase = PrimaryAssetFactory.create(
            integration_db_session, organization_id=org_id
        )
        PrimaryAssetRoleGrantFactory.create(
            integration_db_session,
            primary_asset_id=codebase.id,
            principal_kind=PrincipalKind.user,
            user_id=asset_admin.id,
            role=PrimaryAssetRole.asset_admin,
            organization_id=org_id,
        )

        mock_user = create_mock_user(org_id, asset_admin.id)

        with patch("app.api.auth.get_current_user", return_value=mock_user), patch(
            "app.api.session.get_session",
            return_value=integration_db_session,
        ):
            from app.api.routes.v1.analytics import get_codebase_overview

            result = get_codebase_overview(
                session=integration_db_session, user=mock_user, codebase_id=codebase.id
            )

            # Asset admin should be able to view analytics
            assert result.total_commits == 100

    @pytest.mark.integration
    def test_asset_member_cannot_view_codebase_analytics(
        self,
        integration_db_session: Session,
        mock_analytics_service,
    ):
        """Test that asset_member cannot view analytics (asset.manage required)."""
        from fastapi import HTTPException

        org_id = "test-org-id"

        # Create user
        asset_member = Auth0UserFactory.create(
            integration_db_session, organization_id=org_id
        )

        # Create codebase with asset_member grant (not asset_admin)
        codebase = PrimaryAssetFactory.create(
            integration_db_session, organization_id=org_id
        )
        PrimaryAssetRoleGrantFactory.create(
            integration_db_session,
            primary_asset_id=codebase.id,
            principal_kind=PrincipalKind.user,
            user_id=asset_member.id,
            role=PrimaryAssetRole.asset_member,  # Not admin!
            organization_id=org_id,
        )

        mock_user = create_mock_user(org_id, asset_member.id)

        with patch("app.api.auth.get_current_user", return_value=mock_user), patch(
            "app.api.session.get_session",
            return_value=integration_db_session,
        ):
            from app.api.routes.v1.analytics import get_codebase_overview

            # Asset member should get 403 (needs asset.manage permission)
            with pytest.raises(HTTPException) as exc_info:
                get_codebase_overview(
                    session=integration_db_session,
                    user=mock_user,
                    codebase_id=codebase.id,
                )

            assert exc_info.value.status_code == 403

    @pytest.mark.integration
    def test_user_without_codebase_access_denied(
        self,
        integration_db_session: Session,
        mock_analytics_service,
    ):
        """Test that users without any role on codebase are denied."""
        from fastapi import HTTPException

        org_id = "test-org-id"

        # Create user with no grants
        user_without_access = Auth0UserFactory.create(
            integration_db_session, organization_id=org_id
        )

        # Create codebase (no grant for this user)
        codebase = PrimaryAssetFactory.create(
            integration_db_session, organization_id=org_id
        )

        mock_user = create_mock_user(org_id, user_without_access.id)

        with patch("app.api.auth.get_current_user", return_value=mock_user), patch(
            "app.api.session.get_session",
            return_value=integration_db_session,
        ):
            from app.api.routes.v1.analytics import get_codebase_overview

            # User without access should get 403
            with pytest.raises(HTTPException) as exc_info:
                get_codebase_overview(
                    session=integration_db_session,
                    user=mock_user,
                    codebase_id=codebase.id,
                )

            assert exc_info.value.status_code == 403


@pytest.mark.integration
class TestAnalytics404Handling:
    """Tests for 404 handling when analytics data is not found."""

    @pytest.fixture
    def mock_analytics_service_not_found(self):
        """Mock the AnalyticsService to return None (not found)."""
        with patch("app.api.routes.v1.analytics.AnalyticsService") as mock:
            mock_instance = MagicMock()
            mock_instance.get_overview.return_value = None
            mock_instance.get_branches.return_value = None
            mock_instance.get_activity.return_value = None
            mock_instance.get_ownership.return_value = None
            mock.return_value = mock_instance
            yield mock

    @pytest.mark.integration
    def test_codebase_overview_returns_404_when_not_found(
        self,
        integration_db_session: Session,
        mock_analytics_service_not_found,
    ):
        """Test that codebase overview returns 404 when analytics not found."""
        from fastapi import HTTPException

        org_id = "test-org-id"

        # Create super admin (can access any codebase)
        super_admin = Auth0UserFactory.create(
            integration_db_session, organization_id=org_id
        )
        org_membership = integration_db_session.exec(
            select(OrgMembership).where(
                OrgMembership.user_id == super_admin.id,
                OrgMembership.org_id == org_id,
            )
        ).first()
        if org_membership:
            org_membership.role = OrgRole.org_super_admin
            integration_db_session.add(org_membership)
            integration_db_session.commit()

        # Create codebase
        codebase = PrimaryAssetFactory.create(
            integration_db_session, organization_id=org_id
        )

        mock_user = create_mock_user(org_id, super_admin.id)

        with patch("app.api.auth.get_current_user", return_value=mock_user), patch(
            "app.api.session.get_session",
            return_value=integration_db_session,
        ):
            from app.api.routes.v1.analytics import get_codebase_overview

            # Should return 404 when analytics not found
            with pytest.raises(HTTPException) as exc_info:
                get_codebase_overview(
                    session=integration_db_session,
                    user=mock_user,
                    codebase_id=codebase.id,
                )

            assert exc_info.value.status_code == 404
            assert "Analytics not found" in exc_info.value.detail

