"""Service for reading analytics JSON from S3.

Authorization Pattern:
- Uses primary_asset_grant_filter to filter codebases by admin access
- Super Admins (is_super_admin=True) see all codebases
- Source Admins (asset_admin role on codebases) see only their administered codebases
"""

import json
import logging
from typing import Any
from uuid import UUID

import boto3
from botocore.exceptions import ClientError
from sqlmodel import Session

from app.api.auth import UserToken
from app.core.config import settings
from app.utils.aws_s3 import org_id_to_hash
from database.models import PrimaryAsset
from shared.authorization.helpers import is_super_admin
from shared.authorization.query_filters import (
    PrimaryAssetRole,
    primary_asset_grant_filter,
)

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for reading pre-computed analytics JSON from S3.

    Filters results based on user's admin access to codebases.
    """

    def __init__(self, session: Session, user: UserToken):
        self.session = session
        self.user = user
        self.organization_id = str(user.organization_id)
        self.bucket = org_id_to_hash(self.organization_id)
        self.s3_client = boto3.client(
            "s3",
            region_name=settings.AWS_REGION,
            aws_access_key_id=(
                settings.S3ADMIN_AWS_ACCESS_KEY_ID
                if not settings.IS_PRIVATE_DEPLOY
                else None
            ),
            aws_secret_access_key=(
                settings.S3ADMIN_AWS_SECRET_ACCESS_KEY
                if not settings.IS_PRIVATE_DEPLOY
                else None
            ),
            endpoint_url=(
                settings.AWS_S3_ENDPOINT_URL if settings.AWS_S3_ENDPOINT_URL else None
            ),
        )

    def _read_json(self, key: str) -> dict[str, Any] | None:
        """Read a JSON file from S3. Returns None if not found."""
        try:
            response = self.s3_client.get_object(Bucket=self.bucket, Key=key)
            content = response["Body"].read().decode("utf-8")
            return json.loads(content)
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.info(f"Analytics file not found: {key}")
                return None
            logger.error(f"Error reading analytics file {key}: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {key}: {e}")
            return None

    def _get_administered_codebase_ids(self) -> set[UUID] | None:
        """Get IDs of codebases this user can administer.

        Returns None if user is Super Admin (meaning all codebases).
        Returns set of codebase IDs if user is Source Admin.
        """
        if is_super_admin(self.session, self.user.user_id, self.organization_id):
            return None  # Super Admin sees all

        # Source Admin - filter by asset_admin role
        filter_clause = primary_asset_grant_filter(
            self.session,
            self.user.user_id,
            self.organization_id,
            role=PrimaryAssetRole.asset_admin,
        )

        query = self.session.query(PrimaryAsset.id).where(filter_clause)
        return {row[0] for row in query.all()}

    # === Organization-Level Methods ===

    def get_org_summary(self) -> dict[str, Any] | None:
        """Get organization-level analytics summary.

        For Source Admins, computes a filtered summary based on their administered codebases.
        Super Admins get the full pre-computed org summary.
        """
        administered_ids = self._get_administered_codebase_ids()

        if administered_ids is None:
            # Super Admin - return pre-computed full org summary
            return self._read_json("analytics/org_summary.json")

        # Source Admin - compute filtered summary from codebases list
        codebases_data = self._read_json("analytics/codebases_list.json")
        if not codebases_data:
            return None

        # Filter to administered codebases and aggregate metrics
        filtered_codebases = [
            cb
            for cb in codebases_data.get("codebases", [])
            if UUID(cb["codebase_id"]) in administered_ids
        ]

        # Compute aggregated summary from filtered codebases
        return {
            "organization_id": self.organization_id,
            "total_codebases": len(filtered_codebases),
            "codebases_with_analytics": len(
                [
                    cb
                    for cb in filtered_codebases
                    if cb.get("analytics_status") == "complete"
                ]
            ),
            "total_commits": sum(
                cb.get("total_commits", 0) for cb in filtered_codebases
            ),
            "total_contributors": sum(
                cb.get("total_contributors", 0) for cb in filtered_codebases
            ),
            "total_sloc": sum(cb.get("current_sloc", 0) for cb in filtered_codebases),
            "generated_at": codebases_data.get("generated_at"),
        }

    def get_codebases_list(self) -> dict[str, Any] | None:
        """Get list of codebases with analytics status.

        Super Admins see all codebases.
        Source Admins see only codebases they administer.
        """
        data = self._read_json("analytics/codebases_list.json")
        if not data:
            return None

        administered_ids = self._get_administered_codebase_ids()

        if administered_ids is None:
            # Super Admin - return all
            return data

        # Source Admin - filter to only administered codebases
        filtered_codebases = [
            cb
            for cb in data.get("codebases", [])
            if UUID(cb["codebase_id"]) in administered_ids
        ]

        return {
            **data,
            "codebases": filtered_codebases,
            "total_codebases": len(filtered_codebases),
        }

    # === Codebase-Level Methods ===

    def get_overview(self, codebase_id: str) -> dict[str, Any] | None:
        """Get overview metrics for a codebase."""
        return self._read_json(f"analytics/{codebase_id}/overview.json")

    def get_branches(self, codebase_id: str) -> dict[str, Any] | None:
        """Get branch data for a codebase."""
        return self._read_json(f"analytics/{codebase_id}/branches.json")

    def get_activity(self, codebase_id: str) -> dict[str, Any] | None:
        """Get activity data for a codebase."""
        return self._read_json(f"analytics/{codebase_id}/activity.json")

    def get_ownership(self, codebase_id: str) -> dict[str, Any] | None:
        """Get code ownership data for a codebase."""
        return self._read_json(f"analytics/{codebase_id}/ownership.json")

    def get_status(self, codebase_id: str) -> dict[str, Any]:
        """Get analytics status for a codebase."""
        metadata = self._read_json(f"analytics/{codebase_id}/metadata.json")
        if metadata:
            return metadata
        # If no metadata, return a "none" status
        return {
            "codebase_id": codebase_id,
            "status": "none",
            "generated_at": None,
            "generation_seconds": None,
        }

