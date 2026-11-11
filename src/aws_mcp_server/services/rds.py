"""Amazon RDS control-plane tools."""

from typing import Any

import boto3
from fastmcp import FastMCP

from ..config import Settings
from ..utils import jsonable
from .base import BaseService


class RDSService(BaseService):
    def __init__(self, settings: Settings, session: boto3.Session) -> None:
        super().__init__(settings, session)
        self.client = session.client("rds")

    def register(self, mcp: FastMCP) -> None:
        for function in (
            self.rds_list_instances,
            self.rds_describe_instance,
            self.rds_list_snapshots,
            self.rds_get_events,
            self.rds_create_snapshot,
            self.rds_reboot_instance,
        ):
            mcp.tool(function)

    @staticmethod
    def _summarize(db: dict) -> dict:
        endpoint = db.get("Endpoint", {})
        return {
            "identifier": db["DBInstanceIdentifier"],
            "status": db["DBInstanceStatus"],
            "engine": db["Engine"],
            "engine_version": db["EngineVersion"],
            "instance_class": db["DBInstanceClass"],
            "endpoint": endpoint.get("Address"),
            "port": endpoint.get("Port"),
            "allocated_storage_gb": db.get("AllocatedStorage"),
            "multi_az": db.get("MultiAZ"),
            "publicly_accessible": db.get("PubliclyAccessible"),
            "storage_encrypted": db.get("StorageEncrypted"),
            "iam_auth_enabled": db.get("IAMDatabaseAuthenticationEnabled"),
            "availability_zone": db.get("AvailabilityZone"),
            "backup_retention_days": db.get("BackupRetentionPeriod"),
        }

    async def rds_list_instances(self) -> list[dict]:
        """List all RDS DB instances in the configured region."""

        def list_instances() -> list[dict]:
            instances: list[dict] = []
            paginator = self.client.get_paginator("describe_db_instances")
            for page in paginator.paginate():
                instances.extend(self._summarize(item) for item in page["DBInstances"])
            return instances

        return jsonable(await self._run(list_instances))

    async def rds_describe_instance(self, db_instance_identifier: str) -> dict:
        """Get detailed configuration for one RDS DB instance."""
        response = await self._run(
            self.client.describe_db_instances,
            DBInstanceIdentifier=db_instance_identifier,
        )
        db = response["DBInstances"][0]
        detail = self._summarize(db)
        detail.update(
            {
                "vpc_security_groups": [
                    group["VpcSecurityGroupId"]
                    for group in db.get("VpcSecurityGroups", [])
                ],
                "parameter_groups": [
                    group["DBParameterGroupName"]
                    for group in db.get("DBParameterGroups", [])
                ],
                "subnet_group": db.get("DBSubnetGroup", {}).get("DBSubnetGroupName"),
                "preferred_backup_window": db.get("PreferredBackupWindow"),
                "preferred_maintenance_window": db.get("PreferredMaintenanceWindow"),
                "latest_restorable_time": db.get("LatestRestorableTime"),
                "performance_insights": db.get("PerformanceInsightsEnabled"),
                "deletion_protection": db.get("DeletionProtection"),
            }
        )
        return jsonable(detail)

    async def rds_list_snapshots(
        self,
        db_instance_identifier: str | None = None,
        max_records: int = 50,
        marker: str | None = None,
    ) -> dict:
        """List one page of snapshots; pass next_marker to fetch another page."""
        params: dict[str, Any] = {"MaxRecords": max(20, min(max_records, 100))}
        if db_instance_identifier:
            params["DBInstanceIdentifier"] = db_instance_identifier
        if marker:
            params["Marker"] = marker

        response = await self._run(self.client.describe_db_snapshots, **params)
        snapshots = [
            {
                "snapshot": item["DBSnapshotIdentifier"],
                "instance": item["DBInstanceIdentifier"],
                "type": item.get("SnapshotType"),
                "status": item.get("Status"),
                "created": item.get("SnapshotCreateTime"),
                "size_gb": item.get("AllocatedStorage"),
                "encrypted": item.get("Encrypted"),
            }
            for item in response["DBSnapshots"]
        ]
        return jsonable(
            {"snapshots": snapshots, "next_marker": response.get("Marker")}
        )

    async def rds_get_events(
        self,
        db_instance_identifier: str,
        duration_minutes: int = 360,
        marker: str | None = None,
    ) -> dict:
        """Get one page of recent events; pass next_marker to fetch another page."""
        params: dict[str, Any] = {
            "SourceIdentifier": db_instance_identifier,
            "SourceType": "db-instance",
            "Duration": max(1, min(duration_minutes, 20160)),
        }
        if marker:
            params["Marker"] = marker

        response = await self._run(self.client.describe_events, **params)
        events = [
            {
                "time": item["Date"],
                "message": item["Message"],
                "categories": item["EventCategories"],
            }
            for item in response["Events"]
        ]
        return jsonable({"events": events, "next_marker": response.get("Marker")})

    async def rds_create_snapshot(
        self, db_instance_identifier: str, snapshot_identifier: str
    ) -> dict:
        """Create a manual DB snapshot. Requires ALLOW_WRITES=true."""
        self._require_writes("rds_create_snapshot")
        response = await self._run(
            self.client.create_db_snapshot,
            DBInstanceIdentifier=db_instance_identifier,
            DBSnapshotIdentifier=snapshot_identifier,
        )
        snapshot = response["DBSnapshot"]
        return jsonable(
            {
                "snapshot": snapshot["DBSnapshotIdentifier"],
                "status": snapshot["Status"],
            }
        )

    async def rds_reboot_instance(
        self,
        db_instance_identifier: str,
        force_failover: bool = False,
    ) -> dict:
        """Reboot an RDS instance. Requires ALLOW_WRITES=true."""
        self._require_writes("rds_reboot_instance")
        response = await self._run(
            self.client.reboot_db_instance,
            DBInstanceIdentifier=db_instance_identifier,
            ForceFailover=force_failover,
        )
        instance = response["DBInstance"]
        return {
            "identifier": instance["DBInstanceIdentifier"],
            "status": instance["DBInstanceStatus"],
        }