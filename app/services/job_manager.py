"""
Job manager for async processing of video analysis tasks.
"""
import logging
import asyncio
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum

from app.models import AnalysisRequest, AnalysisResponse, JobStatus, VideoResult, ErrorInfo
from app.logging import log_with_context
from app.services.batch_processor import default_batch_processor

logger = logging.getLogger(__name__)


class JobState(Enum):
    """Job processing states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobManager:
    """Manages async job processing."""
    
    def __init__(self):
        """Initialize the job manager."""
        self.jobs: Dict[str, JobStatus] = {}
        self.running_tasks: Dict[str, asyncio.Task] = {}
    
    async def create_job(self, request: AnalysisRequest) -> str:
        """
        Create a new async job.
        
        Args:
            request: Analysis request
            
        Returns:
            Job ID
        """
        job_id = str(uuid.uuid4())
        
        # Create job status
        job_status = JobStatus(
            job_id=job_id,
            status=JobState.PENDING.value,
            created_at=datetime.now(),
            completed_at=None,
            result=None,
            error=None
        )
        
        self.jobs[job_id] = job_status
        
        # Start processing task
        task = asyncio.create_task(self._process_job(job_id, request))
        self.running_tasks[job_id] = task
        
        log_with_context("info", f"Created async job {job_id} for {len(request.urls)} URLs")
        return job_id
    
    async def get_job_status(self, job_id: str) -> Optional[JobStatus]:
        """
        Get job status by ID.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job status or None if not found
        """
        return self.jobs.get(job_id)
    
    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a running job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if cancelled, False if not found or already completed
        """
        if job_id not in self.jobs:
            return False
        
        job = self.jobs[job_id]
        if job.status in [JobState.COMPLETED.value, JobState.FAILED.value]:
            return False
        
        # Cancel the task
        if job_id in self.running_tasks:
            task = self.running_tasks[job_id]
            task.cancel()
            del self.running_tasks[job_id]
        
        # Update job status
        job.status = JobState.FAILED.value
        job.completed_at = datetime.now()
        job.error = ErrorInfo(
            code="JOB_CANCELLED",
            message="Job was cancelled by user"
        )
        
        log_with_context("info", f"Cancelled job {job_id}")
        return True
    
    async def _process_job(self, job_id: str, request: AnalysisRequest):
        """
        Process a job asynchronously.
        
        Args:
            job_id: Job identifier
            request: Analysis request
        """
        try:
            # Update job status to running
            job = self.jobs[job_id]
            job.status = JobState.RUNNING.value
            
            log_with_context("info", f"Started processing job {job_id}")
            
            # Process the batch
            response = await default_batch_processor.process_batch(
                [str(url) for url in request.urls],
                request.options,
                job_id
            )
            
            # Update job with result
            job.status = JobState.COMPLETED.value
            job.completed_at = datetime.now()
            job.result = response
            
            log_with_context("info", f"Completed job {job_id}: {response.aggregation.succeeded} succeeded, {response.aggregation.failed} failed")
            
        except asyncio.CancelledError:
            # Job was cancelled
            job = self.jobs[job_id]
            job.status = JobState.FAILED.value
            job.completed_at = datetime.now()
            job.error = ErrorInfo(
                code="JOB_CANCELLED",
                message="Job was cancelled"
            )
            log_with_context("info", f"Job {job_id} was cancelled")
            
        except Exception as e:
            # Job failed with error
            job = self.jobs[job_id]
            job.status = JobState.FAILED.value
            job.completed_at = datetime.now()
            job.error = ErrorInfo(
                code="JOB_ERROR",
                message=str(e)
            )
            log_with_context("error", f"Job {job_id} failed: {str(e)}")
            
        finally:
            # Clean up running task
            if job_id in self.running_tasks:
                del self.running_tasks[job_id]
    
    def get_job_count(self) -> Dict[str, int]:
        """Get job statistics."""
        total = len(self.jobs)
        pending = sum(1 for job in self.jobs.values() if job.status == JobState.PENDING.value)
        running = sum(1 for job in self.jobs.values() if job.status == JobState.RUNNING.value)
        completed = sum(1 for job in self.jobs.values() if job.status == JobState.COMPLETED.value)
        failed = sum(1 for job in self.jobs.values() if job.status == JobState.FAILED.value)
        
        return {
            "total": total,
            "pending": pending,
            "running": running,
            "completed": completed,
            "failed": failed
        }
    
    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Clean up old completed jobs."""
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
        
        jobs_to_remove = []
        for job_id, job in self.jobs.items():
            if (job.status in [JobState.COMPLETED.value, JobState.FAILED.value] and 
                job.completed_at and 
                job.completed_at.timestamp() < cutoff_time):
                jobs_to_remove.append(job_id)
        
        for job_id in jobs_to_remove:
            del self.jobs[job_id]
        
        if jobs_to_remove:
            log_with_context("info", f"Cleaned up {len(jobs_to_remove)} old jobs")


# Global instance
job_manager = JobManager()
