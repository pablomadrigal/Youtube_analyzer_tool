# YouTube Analyzer Tool

A service that analyzes YouTube videos and generates structured bilingual summaries in Spanish and English.

## Features

- **Video Metadata Extraction**: Extract title, channel, publish date, duration, and other metadata
- **Bilingual Transcripts**: Fetch transcripts in Spanish and English
- **AI-Powered Summaries**: Generate structured summaries using LLM providers
- **Whisper Fallback**: Automatic audio transcription using OpenAI Whisper when transcripts aren't available
- **Batch Processing**: Analyze multiple videos in a single request
- **REST API**: Simple HTTP API for integration
- **Optional Markdown**: Include Markdown-formatted outputs

## Quick Start

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd youtube_analyzer_tool
```

2. Create and activate a virtual environment:
```bash
# Using venv (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Or using conda
conda create -n youtube-analyzer python=3.11
conda activate youtube-analyzer
```

3. Install dependencies:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp env.example .env
# Edit .env with your API keys and security token
```

5. Generate a secure API token:
```bash
python generate_token.py
# Add the generated token to your .env file as API_TOKEN=
```

6. Run the service:
```bash
python main.py
```

The service will be available at `http://localhost:8001`

### Virtual Environment Management

This project requires a virtual environment to isolate dependencies. Here are the key commands:

```bash
# Activate virtual environment (do this every time you work on the project)
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Deactivate when done
deactivate

# Remove virtual environment (if needed)
rm -rf venv

# Recreate virtual environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Important**: Always activate your virtual environment before running any project commands.

### API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8001/docs`
- ReDoc: `http://localhost:8001/redoc`

## Security

The API uses static token authentication for the `/api/analyze` endpoint. All requests to this endpoint must include a valid API token in the Authorization header.

### Authentication

Include your API token in the Authorization header using the Bearer scheme:

```bash
curl -X POST "http://localhost:8001/api/analyze" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -d '{
    "urls": ["https://www.youtube.com/watch?v=VIDEO_ID"],
    "options": {
      "include_markdown": true,
      "languages": ["es", "en"],
      "provider": "openai/gpt-4o-mini",
      "temperature": 0.2,
      "max_tokens": 1200
    }
  }'
```

### Token Generation

Generate a secure API token using the provided utility:

```bash
python generate_token.py
```

This will output a cryptographically secure token that you can add to your `.env` file:

```
API_TOKEN=your_generated_token_here
```

**Note**: If no `API_TOKEN` is configured in your environment, authentication will be disabled (for development purposes only).

## API Usage

### Analyze Videos

### Health Check

```bash
curl "http://localhost:8001/health"
```

## Configuration

The service can be configured using environment variables:

- `OPENAI_API_KEY`: OpenAI API key
- `ANTHROPIC_API_KEY`: Anthropic API key
- `LOG_LEVEL`: Logging level (default: INFO)
- `DEFAULT_PROVIDER`: Default LLM provider (default: openai/gpt-4o-mini)
- `DEFAULT_TEMPERATURE`: Default temperature (default: 0.2)
- `DEFAULT_MAX_TOKENS`: Default max tokens (default: 1200)
- `REQUEST_TIMEOUT`: Request timeout in seconds (default: 300)
- `MAX_CONCURRENT_REQUESTS`: Max concurrent requests (default: 3)
- `USE_WHISPER_FALLBACK`: Enable Whisper fallback for transcript fetching (default: true)
- `WHISPER_MAX_AUDIO_DURATION`: Maximum audio duration for Whisper in seconds (default: 3600)
- `WHISPER_CHUNK_DURATION`: Chunk duration for long audio files in seconds (default: 600)
- `WHISPER_MODEL`: Whisper model to use (default: base)
- `WHISPER_DEVICE`: Device to run Whisper on (default: cpu)
- `WHISPER_COMPUTE_TYPE`: Compute type for Whisper (default: int8)

## Development

### Running Tests

```bash
# Make sure virtual environment is activated
source venv/bin/activate
pytest
```

### Project Structure

```
youtube_analyzer_tool/
├── main.py              # FastAPI application entry point
├── config.py            # Configuration management
├── models.py            # Pydantic models
├── app_logging.py       # Logging configuration
├── api/
│   ├── __init__.py
│   ├── analyze.py       # Analysis endpoints
│   ├── jobs.py          # Job management endpoints
│   └── monitoring.py    # Monitoring endpoints
├── services/
│   ├── __init__.py
│   ├── orchestrator.py  # Main processing orchestrator
│   ├── metadata_fetcher.py     # Video metadata extraction
│   ├── transcript_fetcher.py   # Transcript fetching
│   ├── transcript_chunker.py   # Transcript chunking
│   ├── summarization_service.py # AI summarization
│   ├── response_formatter.py   # Response formatting
│   ├── whisper_transcriber.py  # Whisper fallback
│   ├── audio_downloader.py     # Audio downloading
│   ├── batch_processor.py      # Batch processing
│   ├── cache.py               # Caching service
│   ├── job_manager.py         # Job management
│   └── observability.py       # Observability features
└── tests/
    ├── __init__.py
    ├── test_main.py
    ├── test_metadata_fetcher.py
    ├── test_summarization_service.py
    ├── test_transcript_chunker.py
    ├── test_transcript_fetcher.py
    └── test_whisper_fallback.py
```

## Requirements

- Python 3.8+
- FastAPI
- yt-dlp
- youtube-transcript-api
- LiteLLM
- OpenAI or Anthropic API key
- Whisper (for audio transcription fallback)
- librosa and soundfile (for audio processing)