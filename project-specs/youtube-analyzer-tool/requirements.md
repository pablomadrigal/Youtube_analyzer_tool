# Requirements Document - YouTube Analyzer Tool

## Introduction

The YouTube Analyzer Tool processes one or more YouTube URLs, extracts available video metadata and transcripts in Spanish and English, and generates structured summaries in both languages. The primary users are students, professionals, researchers, and creators who need fast, comprehensible insights from educational videos, especially for Spanish-speaking audiences. The tool is implemented as an HTTP service exposing a REST endpoint that returns JSON responses containing video metadata, bilingual transcripts (when available), and bilingual summaries. Technologies include Python (with virtual environment isolation), FastAPI for the API layer, yt-dlp for metadata, youtube-transcript-api for transcripts, and LLM providers via LiteLLM for summarization.

## Requirements

### Requirement R1: HTTP API input and invocation
**User Story:** As an API client, I want to POST one or multiple YouTube URLs so that I can analyze one or many videos within a single request.

#### Acceptance Criteria
1. WHEN the client POSTs to `/api/analyze` with a single valid URL in the request body, THEN the system SHALL process that video and return a 200 response with a single result object.
2. IF the client POSTs multiple URLs, THEN the system SHALL process them as a batch and return a 200 response with an array of per-item results.
3. IF any provided URL is invalid or unreachable, THEN the system SHALL include an error object for that item without failing the entire request; request-level validation errors SHALL return an appropriate 4xx.
4. WHILE processing a batch, the system SHALL continue processing remaining items even if some items fail and include per-item statuses.

### Requirement R2: Video metadata extraction
**User Story:** As a user, I want basic video metadata captured so that the output file contains essential context about the video.

#### Acceptance Criteria
1. WHEN processing starts, THEN the system SHALL retrieve at minimum: title, channel name, publish date, duration, video ID, and URL using yt-dlp.
2. IF metadata retrieval fails, THEN the system SHALL emit a clear error and skip dependent steps that require metadata for that item.
3. WHILE metadata retrieval is successful, the system SHALL embed the metadata in the JSON response for that item.

### Requirement R3: Transcript extraction (Spanish and English)
**User Story:** As a user, I want transcripts in Spanish and English so that I can read or analyze the content bilingually.

#### Acceptance Criteria
1. WHEN processing a video, THEN the system SHALL attempt to fetch transcripts for Spanish (es) and English (en) using youtube-transcript-api.
2. IF one or both transcripts are not available from YouTube, THEN the system SHALL record unavailability with the reason (e.g., disabled, not provided, auto-generated unavailable) and proceed with available artifacts.
3. WHILE transcripts are retrieved, the system SHALL include them verbatim (with appropriate attribution if auto-generated) within the JSON response in separate language fields.

### Requirement R4: Bilingual structured summaries
**User Story:** As a user, I want structured summaries in Spanish and English so that I can quickly grasp key points regardless of language preference.

#### Acceptance Criteria
1. WHEN at least one transcript is available, THEN the system SHALL produce a structured summary in Spanish and a structured summary in English using an LLM via LiteLLM.
2. IF only one transcript language is available, THEN the system SHALL still generate both language summaries based on the available content (translation is permitted for the missing-language summary).
3. IF no transcripts are available, THEN the system SHALL skip summarization for that video and mark the output accordingly with an explanatory note.
4. WHILE generating summaries, the system SHALL produce a consistent structure (e.g., key topics, bullet points, notable quotes, action items, optional timestamps when available) to keep outputs uniform across videos.

### Requirement R5: Response format and schema
**User Story:** As a user, I want a predictable JSON response so that artifacts are easy to store, search, and integrate.

#### Acceptance Criteria
1. WHEN processing completes for a video, THEN the system SHALL return a result object with: metadata, transcripts.es, transcripts.en, summaries.es, summaries.en, and per-field availability notes.
2. IF the client requests optional Markdown, THEN the system SHALL include additional Markdown fields (e.g., `markdown.summary_es`, `markdown.summary_en`, `markdown.transcript_es`, `markdown.transcript_en`).
3. WHILE returning a batch response, the system SHALL include a top-level `requestId`, an array of per-item results, and an `aggregation` section with counts of successes and failures.

### Requirement R6: Batch processing and optional async
**User Story:** As a user, I want robust batch processing and the option to run long analyses asynchronously so that I can analyze multiple or long videos efficiently.

#### Acceptance Criteria
1. WHEN provided a list of URLs, THEN the system SHALL process them sequentially by default and MAY support configurable limited concurrency.
2. IF any item fails, THEN the system SHALL continue with remaining items and include per-item errors; the response SHALL include an aggregation summary.
3. IF the client sets `async=true`, THEN the system SHALL return a 202 with a `jobId`, and provide `GET /api/jobs/{jobId}` for status and retrieval upon completion.

### Requirement R7: Configuration and API options
**User Story:** As a power user, I want configurable options so that I can tailor performance and outputs to my needs.

#### Acceptance Criteria
1. WHEN invoking the API, THEN the system SHALL allow request parameters for: optional Markdown inclusion, model/provider selection (via LiteLLM), temperature/max-tokens (if applicable), rate-limit/backoff parameters, language preferences, and verbosity.
2. IF required provider credentials are missing, THEN the system SHALL return 500 with a clear error and instructions (e.g., required environment variable names).
3. WHILE running, the system SHALL log effective configuration at request start in verbose mode without leaking secrets.

### Requirement R8: Performance and limits
**User Story:** As a user, I want the tool to handle typical educational videos without failing due to size or rate limits.

#### Acceptance Criteria
1. WHEN processing videos up to several hours in duration, THEN the system SHALL chunk transcripts as needed to stay within provider token limits.
2. IF external API rate limits or transient errors occur, THEN the system SHALL implement exponential backoff and retry up to a configurable limit.
3. WHILE processing large transcripts, the system SHALL stream or incrementally summarize to avoid excessive memory consumption where feasible.

### Requirement R9: Error handling and observability
**User Story:** As a user, I want clear error messages and logs so that I can diagnose issues quickly.

#### Acceptance Criteria
1. WHEN any step fails for an item, THEN the system SHALL return a concise per-item error with a machine-actionable code/category and human-readable detail; request-level failures SHALL use standard HTTP status codes.
2. IF one or more items fail in a batch, THEN the system SHALL still return 200 with per-item statuses unless the request itself is invalid (4xx) or the server fails (5xx).
3. WHILE running, the system SHALL support quiet and verbose modes controlling log verbosity and correlate logs with `requestId`.

### Requirement R10: Reproducibility and determinism
**User Story:** As a researcher, I want reasonable reproducibility so that repeated runs give consistent, comparable outputs.

#### Acceptance Criteria
1. WHEN the same input is processed with the same configuration, THEN the system SHOULD produce semantically consistent summaries (not necessarily token-identical) and identical metadata/transcript sections.
2. IF a provider supports seed or deterministic modes, THEN the system MAY expose such options through configuration.
3. WHILE producing outputs, the system SHALL embed the effective configuration and provider/model identifiers in the response `config` section for traceability.

### Requirement R11: Development environment isolation
**User Story:** As a developer, I want a clean, isolated development environment so that project dependencies don't conflict with system packages or other projects.

#### Acceptance Criteria
1. WHEN setting up the development environment, THEN the system SHALL provide clear instructions for creating and managing a Python virtual environment using either `venv` or `conda`.
2. IF dependencies are installed, THEN they SHALL be isolated within the virtual environment and not affect the global Python installation.
3. WHILE developing, the system SHALL ensure all commands and scripts assume the virtual environment is activated and provide clear error messages if it's not.
4. IF the virtual environment is corrupted or needs recreation, THEN the system SHALL provide simple commands to recreate it from scratch.


