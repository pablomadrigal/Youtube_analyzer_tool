"""
Batch processing service with limited concurrency for video analysis.
"""
import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from models import AnalysisOptions, VideoResult, AnalysisResponse, AggregationInfo, ConfigInfo
from app_logging import log_with_context
from services.orchestrator import video_orchestrator

logger = logging.getLogger(__name__)


@dataclass
class BatchConfig:
    """Configuration for batch processing."""
    max_concurrent: int = 3
    timeout_per_video: int = 300
    retry_failed: bool = False
    max_retries: int = 1


class BatchProcessor:
    """Processes multiple videos with limited concurrency."""
    
    def __init__(self, config: BatchConfig = None):
        """Initialize the batch processor."""
        self.config = config or BatchConfig()
        self.semaphore = asyncio.Semaphore(self.config.max_concurrent)
    
    async def process_batch(self, urls: List[str], options: AnalysisOptions, request_id: str) -> AnalysisResponse:
        """
        Process a batch of URLs with limited concurrency.
        
        Args:
            urls: List of YouTube URLs to process
            options: Analysis options
            request_id: Request identifier for correlation
            
        Returns:
            Analysis response with results
        """
        log_with_context("info", f"Starting batch processing: {len(urls)} URLs, max_concurrent={self.config.max_concurrent}")
        
        start_time = datetime.now()
        results = []
        succeeded = 0
        failed = 0
        
        # Create tasks for concurrent processing
        tasks = []
        for i, url in enumerate(urls):
            task = self._process_single_video(url, options, i)
            tasks.append(task)
        
        # Process with limited concurrency
        if self.config.max_concurrent == 1:
            # Sequential processing
            for task in tasks:
                result, success = await task
                results.append(result)
                if success:
                    succeeded += 1
                else:
                    failed += 1
        else:
            # Concurrent processing with semaphore
            completed_tasks = await asyncio.gather(*tasks, return_exceptions=True)
            
            for task_result in completed_tasks:
                if isinstance(task_result, Exception):
                    # Handle task exceptions
                    log_with_context("error", f"Task failed with exception: {str(task_result)}")
                    failed += 1
                    # Create error result
                    error_result = VideoResult(
                        url="unknown",
                        video_id="unknown",
                        status="error",
                        error={
                            "code": "TASK_EXCEPTION",
                            "message": str(task_result)
                        }
                    )
                    results.append(error_result)
                else:
                    result, success = task_result
                    results.append(result)
                    if success:
                        succeeded += 1
                    else:
                        failed += 1
        
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()
        
        log_with_context("info", f"Batch processing completed: {succeeded} succeeded, {failed} failed, took {total_time:.2f}s")
        
        return AnalysisResponse(
            request_id=request_id,
            results=results,
            aggregation=AggregationInfo(
                total=len(urls),
                succeeded=succeeded,
                failed=failed
            ),
            config=ConfigInfo(
                provider=options.provider,
                temperature=options.temperature,
                max_tokens=options.max_tokens
            )
        )
    
    async def _process_single_video(self, url: str, options: AnalysisOptions, index: int) -> Tuple[VideoResult, bool]:
        """
        Process a single video with concurrency control.
        
        Args:
            url: Video URL
            options: Analysis options
            index: Video index in batch
            
        Returns:
            Tuple of (result, success)
        """
        async with self.semaphore:
            try:
                log_with_context("info", f"Processing video {index + 1}: {url}")
                
                # Process with timeout
                result, stats = await asyncio.wait_for(
                    video_orchestrator.process_video(url, options),
                    timeout=self.config.timeout_per_video
                )
                
                if result.status == "ok":
                    log_with_context("info", f"Video {index + 1} completed successfully (took {stats.total_time:.2f}s)")
                    return result, True
                else:
                    log_with_context("warning", f"Video {index + 1} failed: {result.error.message}")
                    return result, False
                    
            except asyncio.TimeoutError:
                log_with_context("error", f"Video {index + 1} timed out after {self.config.timeout_per_video}s")
                error_result = VideoResult(
                    url=url,
                    video_id="unknown",
                    status="error",
                    error={
                        "code": "TIMEOUT",
                        "message": f"Video processing timed out after {self.config.timeout_per_video} seconds"
                    }
                )
                return error_result, False
                
            except Exception as e:
                log_with_context("error", f"Video {index + 1} failed with exception: {str(e)}")
                error_result = VideoResult(
                    url=url,
                    video_id="unknown",
                    status="error",
                    error={
                        "code": "PROCESSING_ERROR",
                        "message": str(e)
                    }
                )
                return error_result, False
    
    async def process_with_retry(self, urls: List[str], options: AnalysisOptions, request_id: str) -> AnalysisResponse:
        """
        Process batch with retry logic for failed videos.
        
        Args:
            urls: List of YouTube URLs to process
            options: Analysis options
            request_id: Request identifier for correlation
            
        Returns:
            Analysis response with results
        """
        if not self.config.retry_failed:
            return await self.process_batch(urls, options, request_id)
        
        log_with_context("info", f"Starting batch processing with retry: {len(urls)} URLs")
        
        # First attempt
        response = await self.process_batch(urls, options, request_id)
        
        # Retry failed videos
        failed_urls = []
        for i, result in enumerate(response.results):
            if result.status == "error":
                failed_urls.append((i, urls[i]))
        
        if failed_urls and self.config.max_retries > 0:
            log_with_context("info", f"Retrying {len(failed_urls)} failed videos")
            
            for retry_attempt in range(self.config.max_retries):
                if not failed_urls:
                    break
                
                log_with_context("info", f"Retry attempt {retry_attempt + 1} for {len(failed_urls)} videos")
                
                # Process failed videos
                retry_tasks = []
                for index, url in failed_urls:
                    task = self._process_single_video(url, options, index)
                    retry_tasks.append((index, task))
                
                # Wait for retry tasks
                retry_results = await asyncio.gather(*[task for _, task in retry_tasks], return_exceptions=True)
                
                # Update results
                new_failed_urls = []
                for i, (original_index, task_result) in enumerate(zip([idx for idx, _ in retry_tasks], retry_results)):
                    if isinstance(task_result, Exception):
                        log_with_context("error", f"Retry failed for video {original_index}: {str(task_result)}")
                        new_failed_urls.append((original_index, urls[original_index]))
                    else:
                        result, success = task_result
                        if success:
                            response.results[original_index] = result
                            response.aggregation.succeeded += 1
                            response.aggregation.failed -= 1
                            log_with_context("info", f"Retry succeeded for video {original_index}")
                        else:
                            new_failed_urls.append((original_index, urls[original_index]))
                            log_with_context("warning", f"Retry failed for video {original_index}: {result.error.message}")
                
                failed_urls = new_failed_urls
                
                if not failed_urls:
                    log_with_context("info", "All videos processed successfully after retry")
                    break
        
        return response


# Global instances
default_batch_processor = BatchProcessor()
sequential_processor = BatchProcessor(BatchConfig(max_concurrent=1))
high_concurrency_processor = BatchProcessor(BatchConfig(max_concurrent=10))
retry_processor = BatchProcessor(BatchConfig(max_concurrent=3, retry_failed=True, max_retries=2))
