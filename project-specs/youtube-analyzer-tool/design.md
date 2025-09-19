# Design Document - YouTube Analyzer Service

## High-Level Summary
An HTTP service that accepts one or more YouTube URLs and returns JSON results with video metadata, transcripts in Spanish and English, and structured summaries in both languages. The API is implemented with FastAPI. Content extraction uses yt-dlp and youtube-transcript-api. Summarization uses LiteLLM to route to OpenAI/Anthropic or other LLM providers. The system supports batch requests, per-item error isolation, optional async jobs, and optional Markdown fields in the response.

## Architecture
The service is decomposed into modular components to improve testability and maintainability.

```mermaid
flowchart TD
  C[Client] -->|POST /api/analyze| A[FastAPI API Layer]
  A --> O[Request Orchestrator]
  O --> M[Metadata Fetcher (yt-dlp)]
  O --> T[Transcript Fetcher (youtube-transcript-api)]
  O --> CH[Transcript Chunker]
  CH --> S[Summarization Service (LiteLLM)]
  S --> F[Response Formatter]
  T --> F
  M --> F
  O --> Q[(Async Jobs Optional)]
  Q --> A
  F --> A
  A -->|200/202 JSON| C
```

## Components and Interfaces

- API Layer (FastAPI)
  - Endpoint: `POST /api/analyze`
  - Optional Endpoint: `GET /api/jobs/{jobId}` (for async)
  - Validates request schema, assigns `requestId`, routes to orchestrator

- Request Orchestrator
  - Coordinates per-URL workflow: metadata -> transcript -> chunk -> summarize -> format
  - Handles per-item error isolation, aggregation counts
  - Supports sequential processing with optional limited concurrency

- Metadata Fetcher
  - Wrapper around yt-dlp to fetch: title, channel, publish date, duration, videoId, canonical URL

- Transcript Fetcher
  - Wrapper around youtube-transcript-api to fetch transcripts for `es` and `en`
  - Returns structured transcript entries and availability reasons when missing

- Transcript Chunker
  - Splits transcripts to fit LLM token limits; preserves paragraph/timestamp boundaries when possible

- Summarization Service
  - Uses LiteLLM to call providers (e.g., OpenAI, Anthropic)
  - Produces consistent structured outputs (key topics, bullets, quotes, action items, opted timestamps)

- Response Formatter
  - Normalizes JSON schema
  - Optionally generates Markdown fields: `markdown.summary_es`, `markdown.summary_en`, `markdown.transcript_es`, `markdown.transcript_en`

- Configuration & Secrets
  - Environment-based configuration for provider keys, models, timeouts, retry/backoff
  - No secrets returned in responses; redact in logs

- Async Jobs (Optional)
  - If `async=true`, POST returns 202 with `jobId`
  - Job status/result via `GET /api/jobs/{jobId}`

## Data Models (Pydantic)

- Request
```json
{
  "urls": ["https://www.youtube.com/watch?v=..."],
  "options": {
    "include_markdown": true,
    "languages": ["es", "en"],
    "provider": "openai/gpt-4o-mini",
    "temperature": 0.2,
    "max_tokens": 1200,
    "async": false
  }
}
```

- Response (success with batch)
```json
{
  "requestId": "uuid-...",
  "results": [
    {
      "url": "https://...",
      "videoId": "abc123",
      "status": "ok",
      "metadata": { "title": "...", "channel": "...", "publishedAt": "...", "durationSec": 1234, "url": "..." },
      "transcripts": {
        "es": { "source": "auto|manual", "segments": [{"text": "...", "start": 0.0, "duration": 3.1}] },
        "en": { "source": "auto|manual", "segments": [] },
        "unavailable": { "es": "disabled", "en": "not_provided" }
      },
      "summaries": {
        "es": { "topics": ["..."], "bullets": ["..."], "quotes": ["..."], "actions": ["..."] },
        "en": { "topics": ["..."], "bullets": ["..."], "quotes": ["..."], "actions": ["..."] }
      },
      "markdown": {
        "summary_es": "# Resumen...\n- ...",
        "summary_en": "# Summary...\n- ...",
        "transcript_es": "...",
        "transcript_en": "..."
      }
    },
    { "url": "...", "status": "error", "error": {"code": "TRANSCRIPT_UNAVAILABLE", "message": "..."} }
  ],
  "aggregation": { "total": 2, "succeeded": 1, "failed": 1 },
  "config": { "provider": "openai/gpt-4o-mini", "temperature": 0.2, "max_tokens": 1200 }
}
```

## Error Handling

- Request-level validation errors: 400 with details per field
- Unauthorized/misconfiguration (missing provider keys): 500 with guidance (no secrets)
- Per-item errors are embedded in `results[]` with `status = error` and `error.code`
- Standardized error codes: METADATA_ERROR, TRANSCRIPT_UNAVAILABLE, SUMMARIZATION_ERROR, RATE_LIMIT, TIMEOUT

## Testing Strategy

- Unit tests for each component (metadata, transcript, chunker, summarization, formatter)
- Contract tests for `POST /api/analyze` covering single and batch, partial failures, and options
- Mock LLM/provider calls; consider VCR-style fixtures for yt-dlp and transcript API
- Property tests for chunking boundaries and response schema validation


