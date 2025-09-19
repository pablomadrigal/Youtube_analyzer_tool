"""
Observability service for monitoring and metrics.
"""
import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque

from app.logging import log_with_context

logger = logging.getLogger(__name__)


@dataclass
class Metrics:
    """Service metrics."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_processing_time: float = 0.0
    average_processing_time: float = 0.0
    requests_per_minute: float = 0.0
    error_counts: Dict[str, int] = field(default_factory=dict)
    provider_usage: Dict[str, int] = field(default_factory=dict)
    language_usage: Dict[str, int] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.now)


class ObservabilityService:
    """Service for monitoring and observability."""
    
    def __init__(self):
        """Initialize the observability service."""
        self.metrics = Metrics()
        self.request_history = deque(maxlen=1000)  # Keep last 1000 requests
        self.start_time = datetime.now()
    
    def record_request(self, request_type: str, success: bool, processing_time: float, 
                      error_code: Optional[str] = None, provider: Optional[str] = None,
                      languages: Optional[list] = None):
        """Record a request for metrics."""
        now = datetime.now()
        
        # Update basic metrics
        self.metrics.total_requests += 1
        if success:
            self.metrics.successful_requests += 1
        else:
            self.metrics.failed_requests += 1
            if error_code:
                self.metrics.error_counts[error_code] = self.metrics.error_counts.get(error_code, 0) + 1
        
        # Update processing time metrics
        self.metrics.total_processing_time += processing_time
        self.metrics.average_processing_time = (
            self.metrics.total_processing_time / self.metrics.total_requests
        )
        
        # Update provider usage
        if provider:
            self.metrics.provider_usage[provider] = self.metrics.provider_usage.get(provider, 0) + 1
        
        # Update language usage
        if languages:
            for lang in languages:
                self.metrics.language_usage[lang] = self.metrics.language_usage.get(lang, 0) + 1
        
        # Update requests per minute
        self._update_requests_per_minute()
        
        # Record in history
        self.request_history.append({
            "timestamp": now,
            "type": request_type,
            "success": success,
            "processing_time": processing_time,
            "error_code": error_code,
            "provider": provider,
            "languages": languages
        })
        
        self.metrics.last_updated = now
        
        log_with_context("info", f"Recorded {request_type} request: success={success}, time={processing_time:.2f}s")
    
    def _update_requests_per_minute(self):
        """Update requests per minute metric."""
        now = datetime.now()
        one_minute_ago = now - timedelta(minutes=1)
        
        recent_requests = [
            req for req in self.request_history
            if req["timestamp"] >= one_minute_ago
        ]
        
        self.metrics.requests_per_minute = len(recent_requests)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics."""
        uptime = (datetime.now() - self.start_time).total_seconds()
        
        return {
            "uptime_seconds": uptime,
            "uptime_human": str(timedelta(seconds=int(uptime))),
            "total_requests": self.metrics.total_requests,
            "successful_requests": self.metrics.successful_requests,
            "failed_requests": self.metrics.failed_requests,
            "success_rate": (
                self.metrics.successful_requests / self.metrics.total_requests * 100
                if self.metrics.total_requests > 0 else 0
            ),
            "average_processing_time": self.metrics.average_processing_time,
            "requests_per_minute": self.metrics.requests_per_minute,
            "error_counts": dict(self.metrics.error_counts),
            "provider_usage": dict(self.metrics.provider_usage),
            "language_usage": dict(self.metrics.language_usage),
            "last_updated": self.metrics.last_updated.isoformat()
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status."""
        now = datetime.now()
        uptime = (now - self.start_time).total_seconds()
        
        # Check if service is healthy
        is_healthy = True
        issues = []
        
        # Check success rate
        if self.metrics.total_requests > 0:
            success_rate = (self.metrics.successful_requests / self.metrics.total_requests) * 100
            if success_rate < 80:  # Less than 80% success rate
                is_healthy = False
                issues.append(f"Low success rate: {success_rate:.1f}%")
        
        # Check average processing time
        if self.metrics.average_processing_time > 300:  # More than 5 minutes
            is_healthy = False
            issues.append(f"High average processing time: {self.metrics.average_processing_time:.1f}s")
        
        # Check error rate
        if self.metrics.failed_requests > 0:
            error_rate = (self.metrics.failed_requests / self.metrics.total_requests) * 100
            if error_rate > 20:  # More than 20% error rate
                is_healthy = False
                issues.append(f"High error rate: {error_rate:.1f}%")
        
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "uptime_seconds": uptime,
            "uptime_human": str(timedelta(seconds=int(uptime))),
            "total_requests": self.metrics.total_requests,
            "success_rate": (
                self.metrics.successful_requests / self.metrics.total_requests * 100
                if self.metrics.total_requests > 0 else 100
            ),
            "issues": issues,
            "timestamp": now.isoformat()
        }
    
    def get_recent_requests(self, limit: int = 10) -> list:
        """Get recent requests."""
        return list(self.request_history)[-limit:]
    
    def reset_metrics(self):
        """Reset all metrics."""
        self.metrics = Metrics()
        self.request_history.clear()
        self.start_time = datetime.now()
        log_with_context("info", "Metrics reset")


# Global instance
observability_service = ObservabilityService()
