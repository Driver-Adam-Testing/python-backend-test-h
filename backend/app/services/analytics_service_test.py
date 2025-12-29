"""Unit tests for AnalyticsService."""

import json
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from botocore.exceptions import ClientError


class TestAnalyticsService:
    """Unit tests for AnalyticsService with mocked S3."""

    @pytest.fixture
    def mock_s3_client(self):
        """Create a mock S3 client."""
        with patch("app.services.analytics_service.boto3.client") as mock:
            yield mock.return_value

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return MagicMock()

    @pytest.fixture
    def mock_super_admin_user(self):
        """Create a mock super admin user."""
        user = MagicMock()
        user.user_id = str(uuid4())
        user.organization_id = str(uuid4())
        return user

    @pytest.fixture
    def mock_source_admin_user(self):
        """Create a mock source admin user."""
        user = MagicMock()
        user.user_id = str(uuid4())
        user.organization_id = str(uuid4())
        return user

    @pytest.fixture
    def service_super_admin(self, mock_s3_client, mock_session, mock_super_admin_user):
        """Create AnalyticsService for super admin with mocked S3."""
        from app.services.analytics_service import AnalyticsService

        with patch(
            "app.services.analytics_service.is_super_admin", return_value=True
        ):
            return AnalyticsService(mock_session, mock_super_admin_user)

    @pytest.fixture
    def service_source_admin(
        self, mock_s3_client, mock_session, mock_source_admin_user
    ):
        """Create AnalyticsService for source admin with mocked S3."""
        from app.services.analytics_service import AnalyticsService

        with patch(
            "app.services.analytics_service.is_super_admin", return_value=False
        ):
            return AnalyticsService(mock_session, mock_source_admin_user)

    # Alias for backward compatibility in tests
    @pytest.fixture
    def service(self, service_super_admin):
        """Default service fixture (super admin)."""
        return service_super_admin

    @pytest.mark.unit
    def test_get_overview_success(self, service, mock_s3_client):
        """Test successful overview retrieval with full schema."""
        expected_data = {
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
        mock_s3_client.get_object.return_value = {
            "Body": MagicMock(read=lambda: json.dumps(expected_data).encode())
        }

        result = service.get_overview("test-id")

        assert result == expected_data
        mock_s3_client.get_object.assert_called_once()

    @pytest.mark.unit
    def test_get_overview_not_found(self, service, mock_s3_client):
        """Test overview retrieval when file doesn't exist."""
        error_response = {"Error": {"Code": "NoSuchKey"}}
        mock_s3_client.get_object.side_effect = ClientError(
            error_response, "GetObject"
        )

        result = service.get_overview("missing-id")

        assert result is None

    @pytest.mark.unit
    def test_get_status_success(self, service, mock_s3_client):
        """Test successful status retrieval."""
        expected_data = {
            "codebase_id": "test-id",
            "generated_at": "2024-06-15T10:00:00Z",
            "status": "complete",
            "generation_seconds": 1.5,
        }
        mock_s3_client.get_object.return_value = {
            "Body": MagicMock(read=lambda: json.dumps(expected_data).encode())
        }

        result = service.get_status("test-id")

        assert result["status"] == "complete"
        assert result["codebase_id"] == "test-id"

    @pytest.mark.unit
    def test_get_status_returns_none_status_when_not_found(
        self, service, mock_s3_client
    ):
        """Test that get_status returns 'none' status when metadata not found."""
        error_response = {"Error": {"Code": "NoSuchKey"}}
        mock_s3_client.get_object.side_effect = ClientError(
            error_response, "GetObject"
        )

        result = service.get_status("missing-id")

        assert result["status"] == "none"
        assert result["codebase_id"] == "missing-id"
        assert result["generated_at"] is None

    @pytest.mark.unit
    def test_get_org_summary_super_admin_gets_precomputed(
        self, service, mock_s3_client
    ):
        """Test that super admin gets pre-computed org summary."""
        expected_data = {
            "organization_id": "test-org",
            "total_codebases": 5,
            "codebases_with_analytics": 3,
            "total_commits": 500,
            "total_contributors": 25,
            "total_sloc": 50000,
            "generated_at": "2024-06-15T10:00:00Z",
        }
        mock_s3_client.get_object.return_value = {
            "Body": MagicMock(read=lambda: json.dumps(expected_data).encode())
        }

        result = service.get_org_summary()

        assert result == expected_data
        # Super admin reads org_summary.json directly
        mock_s3_client.get_object.assert_called_once()

    @pytest.mark.unit
    def test_get_codebases_list_success(self, service, mock_s3_client):
        """Test successful codebases list retrieval."""
        expected_data = {
            "organization_id": "test-org",
            "codebases": [
                {
                    "codebase_id": "id-1",
                    "display_name": "repo-1",
                    "total_commits": 100,
                    "current_sloc": 5000,
                    "last_commit_date": "2024-06-01T00:00:00Z",
                    "analytics_status": "complete",
                },
                {
                    "codebase_id": "id-2",
                    "display_name": "repo-2",
                    "total_commits": 50,
                    "current_sloc": 2500,
                    "last_commit_date": "2024-05-15T00:00:00Z",
                    "analytics_status": "complete",
                },
            ],
            "generated_at": "2024-06-15T10:00:00Z",
        }
        mock_s3_client.get_object.return_value = {
            "Body": MagicMock(read=lambda: json.dumps(expected_data).encode())
        }

        result = service.get_codebases_list()

        assert result == expected_data
        assert len(result["codebases"]) == 2

    @pytest.mark.unit
    def test_get_branches_success(self, service, mock_s3_client):
        """Test successful branches retrieval with full schema."""
        expected_data = {
            "codebase_id": "test-id",
            "branches": [
                {
                    "name": "main",
                    "is_default": True,
                    "commits": 80,
                    "last_commit_date": "2024-06-01T00:00:00Z",
                    "last_analyzed_at": "2024-06-01T12:00:00Z",
                    "status": "active",
                    "head_commit_sha": "abc123",
                    "current_sloc": 5000,
                    "churn_sloc": 8000,
                    "unique_contributors": 5,
                    "total_files": 42,
                },
            ],
        }
        mock_s3_client.get_object.return_value = {
            "Body": MagicMock(read=lambda: json.dumps(expected_data).encode())
        }

        result = service.get_branches("test-id")

        assert result == expected_data
        assert len(result["branches"]) == 1
        assert result["branches"][0]["churn_sloc"] == 8000

    @pytest.mark.unit
    def test_get_activity_success(self, service, mock_s3_client):
        """Test successful activity retrieval with byte-based metrics."""
        expected_data = {
            "codebase_id": "test-id",
            "daily_activity": [
                {
                    "date": "2024-01-15",
                    "commits": 5,
                    "additions": 100,
                    "deletions": 20,
                    "active_contributors": 2,
                    "files_changed": 8,
                    "cumulative_lines": 1000,
                    "addition_bytes": 5000,
                    "deletion_bytes": 1000,
                    "net_bytes": 4000,
                    "patch_bytes": 6000,
                    "cumulative_sloc": 120,
                },
            ],
        }
        mock_s3_client.get_object.return_value = {
            "Body": MagicMock(read=lambda: json.dumps(expected_data).encode())
        }

        result = service.get_activity("test-id")

        assert result == expected_data
        assert result["daily_activity"][0]["addition_bytes"] == 5000

    @pytest.mark.unit
    def test_get_ownership_success(self, service, mock_s3_client):
        """Test successful ownership retrieval."""
        expected_data = {
            "codebase_id": "test-id",
            "directories": [
                {
                    "directory_path": "src",
                    "total_commits": 50,
                    "total_sloc": 3000,
                    "unique_contributors": 3,
                    "primary_owner_email": "dev@example.com",
                    "primary_owner_name": "Developer",
                    "primary_owner_percentage": 60.0,
                    "contributors": [
                        {
                            "contributor_email": "dev@example.com",
                            "contributor_name": "Developer",
                            "total_commits": 30,
                            "total_sloc": 1800,
                            "ownership_percentage": 60.0,
                            "first_commit_at": "2024-01-01T00:00:00Z",
                            "last_commit_at": "2024-06-01T00:00:00Z",
                            "active_days": 45,
                        }
                    ],
                }
            ],
        }
        mock_s3_client.get_object.return_value = {
            "Body": MagicMock(read=lambda: json.dumps(expected_data).encode())
        }

        result = service.get_ownership("test-id")

        assert result == expected_data
        assert result["directories"][0]["primary_owner_email"] == "dev@example.com"

    @pytest.mark.unit
    def test_invalid_json_returns_none(self, service, mock_s3_client):
        """Test that invalid JSON returns None."""
        mock_s3_client.get_object.return_value = {
            "Body": MagicMock(read=lambda: b"not valid json")
        }

        result = service.get_overview("test-id")

        assert result is None

    @pytest.mark.unit
    def test_s3_error_propagates(self, service, mock_s3_client):
        """Test that non-404 S3 errors propagate."""
        error_response = {"Error": {"Code": "AccessDenied"}}
        mock_s3_client.get_object.side_effect = ClientError(
            error_response, "GetObject"
        )

        with pytest.raises(ClientError):
            service.get_overview("test-id")


class TestAnalyticsFiltering:
    """Tests for org summary and codebases list filtering based on admin access."""

    @pytest.fixture
    def mock_s3_client(self):
        """Create a mock S3 client."""
        with patch("app.services.analytics_service.boto3.client") as mock:
            yield mock.return_value

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return MagicMock()

    @pytest.fixture
    def mock_super_admin_user(self):
        """Create a mock super admin user."""
        user = MagicMock()
        user.user_id = str(uuid4())
        user.organization_id = str(uuid4())
        return user

    @pytest.fixture
    def mock_source_admin_user(self):
        """Create a mock source admin user."""
        user = MagicMock()
        user.user_id = str(uuid4())
        user.organization_id = str(uuid4())
        return user

    @pytest.fixture
    def administered_codebase_ids(self):
        """IDs of codebases the source admin can manage."""
        return {UUID("11111111-1111-1111-1111-111111111111")}

    @pytest.fixture
    def all_codebases_data(self):
        """Full list of codebases in the org."""
        return {
            "organization_id": "test-org",
            "codebases": [
                {
                    "codebase_id": "11111111-1111-1111-1111-111111111111",
                    "display_name": "repo-1",
                    "total_commits": 100,
                    "total_contributors": 5,
                    "current_sloc": 5000,
                    "analytics_status": "complete",
                },
                {
                    "codebase_id": "22222222-2222-2222-2222-222222222222",
                    "display_name": "repo-2",
                    "total_commits": 50,
                    "total_contributors": 3,
                    "current_sloc": 2500,
                    "analytics_status": "complete",
                },
            ],
            "generated_at": "2024-06-15T10:00:00Z",
        }

    @pytest.mark.unit
    def test_super_admin_sees_all_codebases(
        self, mock_s3_client, mock_session, mock_super_admin_user, all_codebases_data
    ):
        """Super admin should see all codebases without filtering."""
        from app.services.analytics_service import AnalyticsService

        mock_s3_client.get_object.return_value = {
            "Body": MagicMock(read=lambda: json.dumps(all_codebases_data).encode())
        }

        with patch(
            "app.services.analytics_service.is_super_admin", return_value=True
        ):
            service = AnalyticsService(mock_session, mock_super_admin_user)
            result = service.get_codebases_list()

        assert len(result["codebases"]) == 2

    @pytest.mark.unit
    def test_source_admin_sees_only_administered_codebases(
        self,
        mock_s3_client,
        mock_session,
        mock_source_admin_user,
        all_codebases_data,
        administered_codebase_ids,
    ):
        """Source admin should only see codebases they administer."""
        from app.services.analytics_service import AnalyticsService

        mock_s3_client.get_object.return_value = {
            "Body": MagicMock(read=lambda: json.dumps(all_codebases_data).encode())
        }

        with patch(
            "app.services.analytics_service.is_super_admin", return_value=False
        ), patch.object(
            AnalyticsService,
            "_get_administered_codebase_ids",
            return_value=administered_codebase_ids,
        ):
            service = AnalyticsService(mock_session, mock_source_admin_user)
            result = service.get_codebases_list()

        assert len(result["codebases"]) == 1
        assert (
            result["codebases"][0]["codebase_id"]
            == "11111111-1111-1111-1111-111111111111"
        )

    @pytest.mark.unit
    def test_source_admin_org_summary_is_computed_from_filtered_codebases(
        self,
        mock_s3_client,
        mock_session,
        mock_source_admin_user,
        all_codebases_data,
        administered_codebase_ids,
    ):
        """Source admin org summary should be computed from only their administered codebases."""
        from app.services.analytics_service import AnalyticsService

        mock_s3_client.get_object.return_value = {
            "Body": MagicMock(read=lambda: json.dumps(all_codebases_data).encode())
        }

        with patch(
            "app.services.analytics_service.is_super_admin", return_value=False
        ), patch.object(
            AnalyticsService,
            "_get_administered_codebase_ids",
            return_value=administered_codebase_ids,
        ):
            service = AnalyticsService(mock_session, mock_source_admin_user)
            result = service.get_org_summary()

        # Should only include stats from the one administered codebase
        assert result["total_codebases"] == 1
        assert result["codebases_with_analytics"] == 1
        assert result["total_commits"] == 100  # Only repo-1's commits
        assert result["total_contributors"] == 5  # Only repo-1's contributors
        assert result["total_sloc"] == 5000  # Only repo-1's SLOC

    @pytest.mark.unit
    def test_super_admin_org_summary_reads_precomputed_file(
        self, mock_s3_client, mock_session, mock_super_admin_user
    ):
        """Super admin org summary should read from pre-computed org_summary.json."""
        from app.services.analytics_service import AnalyticsService

        precomputed_summary = {
            "organization_id": "test-org",
            "total_codebases": 100,
            "codebases_with_analytics": 95,
            "total_commits": 50000,
            "total_contributors": 500,
            "total_sloc": 5000000,
            "generated_at": "2024-06-15T10:00:00Z",
        }
        mock_s3_client.get_object.return_value = {
            "Body": MagicMock(read=lambda: json.dumps(precomputed_summary).encode())
        }

        with patch(
            "app.services.analytics_service.is_super_admin", return_value=True
        ):
            service = AnalyticsService(mock_session, mock_super_admin_user)
            result = service.get_org_summary()

        # Should return pre-computed summary, not aggregate from codebases
        assert result == precomputed_summary

