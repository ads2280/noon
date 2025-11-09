"""Async agent service for background processing of calendar events."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from services.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


class AsyncAgentService:
    """Service for managing async agent jobs."""

    def __init__(self):
        self.supabase = get_supabase_client()

    def create_job(
        self,
        user_id: UUID | str,
        job_type: str,
        payload: Dict[str, Any],
        agent_action: Optional[str] = None,
        agent_state: Optional[Dict[str, Any]] = None,
        scheduled_at: Optional[datetime] = None,
        priority: int = 5,
    ) -> str:
        """
        Create a new async agent job.

        Args:
            user_id: User ID
            job_type: Type of job ('calendar_sync', 'event_reminder', 'pattern_analysis', 'bulk_operation')
            payload: Job-specific parameters
            agent_action: Agent action to perform
            agent_state: Full agent state for the job
            scheduled_at: When to run (None = immediate)
            priority: Priority 1-10 (1 = highest)

        Returns:
            Job ID
        """
        job_id = str(uuid4())

        try:
            self.supabase.table("async_agent_jobs").insert(
                {
                    "id": job_id,
                    "user_id": str(user_id),
                    "job_type": job_type,
                    "job_status": "pending",
                    "priority": priority,
                    "payload": payload,
                    "agent_action": agent_action,
                    "agent_state": agent_state or {},
                    "scheduled_at": scheduled_at.isoformat() if scheduled_at else None,
                }
            ).execute()

            logger.info(f"Created async job {job_id} for user {user_id}, type {job_type}")
            return job_id

        except Exception as e:
            logger.error(f"Failed to create async job: {e}", exc_info=True)
            raise

    def get_pending_jobs(
        self,
        job_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[Dict[str, Any]]:
        """
        Get pending jobs ready to process.

        Args:
            job_type: Filter by job type (optional)
            limit: Maximum number of jobs to return

        Returns:
            List of job dictionaries
        """
        try:
            now = datetime.now(timezone.utc).isoformat()
            # Get pending jobs where scheduled_at is null or <= now
            query = (
                self.supabase.table("async_agent_jobs")
                .select("*")
                .eq("job_status", "pending")
                .order("priority", desc=False)
                .order("created_at", desc=False)
                .limit(limit)
            )
            
            # Filter by scheduled_at in Python (Supabase client doesn't support OR easily)
            result = query.execute()
            jobs = result.data or []
            
            # Filter jobs where scheduled_at is null or <= now
            filtered_jobs = [
                job for job in jobs
                if not job.get("scheduled_at") or job.get("scheduled_at") <= now
            ]
            
            if job_type:
                filtered_jobs = [job for job in filtered_jobs if job.get("job_type") == job_type]
            
            return filtered_jobs[:limit]


        except Exception as e:
            logger.error(f"Failed to get pending jobs: {e}", exc_info=True)
            return []

    def update_job_status(
        self,
        job_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Update job status.

        Args:
            job_id: Job ID
            status: New status ('running', 'completed', 'failed', 'cancelled')
            result: Job result (if completed)
            error_message: Error message (if failed)
        """
        try:
            update_data: Dict[str, Any] = {"job_status": status}

            now = datetime.now(timezone.utc).isoformat()
            if status == "running":
                update_data["started_at"] = now
            elif status in ("completed", "failed", "cancelled"):
                update_data["completed_at"] = now

            if result:
                update_data["result"] = result

            if error_message:
                update_data["error_message"] = error_message

            self.supabase.table("async_agent_jobs").update(update_data).eq(
                "id", job_id
            ).execute()

            logger.info(f"Updated job {job_id} to status {status}")

        except Exception as e:
            logger.error(f"Failed to update job {job_id}: {e}", exc_info=True)
            raise

    def retry_job(self, job_id: str) -> bool:
        """
        Retry a failed job if retry count hasn't exceeded max.

        Args:
            job_id: Job ID

        Returns:
            True if job was retried, False if max retries exceeded
        """
        try:
            # Get current job
            result = (
                self.supabase.table("async_agent_jobs")
                .select("*")
                .eq("id", job_id)
                .execute()
            )

            if not result.data:
                return False

            job = result.data[0]

            if job["retry_count"] >= job["max_retries"]:
                logger.warning(
                    f"Job {job_id} exceeded max retries ({job['max_retries']})"
                )
                return False

            # Reset job to pending
            self.supabase.table("async_agent_jobs").update(
                {
                    "job_status": "pending",
                    "retry_count": job["retry_count"] + 1,
                    "error_message": None,
                }
            ).eq("id", job_id).execute()

            logger.info(f"Retrying job {job_id} (attempt {job['retry_count'] + 1})")
            return True

        except Exception as e:
            logger.error(f"Failed to retry job {job_id}: {e}", exc_info=True)
            return False


# Common job types
class JobType:
    """Job type constants."""

    CALENDAR_SYNC = "calendar_sync"
    EVENT_REMINDER = "event_reminder"
    PATTERN_ANALYSIS = "pattern_analysis"
    BULK_OPERATION = "bulk_operation"
    SCHEDULE_OPTIMIZATION = "schedule_optimization"


# Singleton instance
async_agent_service = AsyncAgentService()

