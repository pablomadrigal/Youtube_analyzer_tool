# Implementation Plan

- [ ] 1. Set up development environment and project structure
  - Create Python virtual environment using `venv` or `conda`
  - Create `requirements.txt` with all necessary dependencies
  - Set up project directory structure
  - Create `.gitignore` to exclude virtual environment and sensitive files
  - Create `README.md` with virtual environment setup instructions
  - _Requirements: R11_

- [ ] 2. Set up FastAPI service and base project structure
  - Create FastAPI app with `POST /api/analyze` and health endpoint
  - Add Pydantic models for request/response schemas
  - Configure logging with `requestId` correlation
  - Set configuration loader for provider keys, models, timeouts
  - _Requirements: R1, R5, R7, R9_

- [ ] 3. Implement Metadata Fetcher (yt-dlp wrapper)
  - Add function to resolve videoId and retrieve title, channel, publish date, duration, canonical URL
  - Normalize outputs and error categories
  - Unit tests with fixtures/mocks
  - _Requirements: R2, R9_

- [ ] 4. Implement Transcript Fetcher (youtube-transcript-api)
  - Fetch transcripts for `es` and `en` with source attribution
  - Return availability reasons for missing transcripts
  - Unit tests for happy/edge cases
  - _Requirements: R3, R9_

- [ ] 5. Implement Transcript Chunker
  - Chunk by token/char limits preserving boundaries; expose parameters
  - Property tests to ensure coverage and boundaries
  - _Requirements: R8_

- [ ] 6. Implement Summarization Service (LiteLLM integration)
  - Prompt templates to produce consistent bilingual structured outputs
  - Retry/backoff, configurable temperature/max tokens
  - Unit tests with mocked providers
  - _Requirements: R4, R7, R8_

- [ ] 7. Implement Orchestrator for per-item processing
  - Sequence: metadata -> transcripts -> chunk -> summarize -> format
  - Per-item error isolation and status mapping
  - Unit tests spanning success/partial failure
  - _Requirements: R1, R2, R3, R4, R8, R9, R10_

- [ ] 8. Implement Response Formatter and optional Markdown
  - Build JSON schema including `markdown.*` fields when requested
  - Snapshot tests for stable shape
  - _Requirements: R5, R10_

- [ ] 9. Batch handling and limited concurrency
  - Process arrays of URLs sequentially by default, parameterized concurrency
  - Aggregation summary and per-item statuses
  - Tests for batch flows and partial failures
  - _Requirements: R1, R6, R9_

- [ ] 10. Optional async jobs API
  - Return 202 with `jobId` when `async=true`
  - Implement `GET /api/jobs/{jobId}` for status/result
  - Tests for happy/error paths
  - _Requirements: R6_

- [ ] 11. Observability and configuration hardening
  - Verbose/quiet modes, redacted secrets in logs
  - Structured error codes and messages
  - _Requirements: R7, R9, R10_


