# YouTube Analyzer Tool

A service that analyzes YouTube videos and generates structured bilingual summaries in Spanish and English.

## Features

- **Video Metadata Extraction**: Extract title, channel, publish date, duration, and other metadata
- **Bilingual Transcripts**: Fetch transcripts in Spanish and English
- **AI-Powered Summaries**: Generate structured summaries using LLM providers
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
# Edit .env with your API keys
```

5. Run the service:
```bash
python -m app.main
```

The service will be available at `http://localhost:8000`

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
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## API Usage

### Analyze Videos

```bash
curl -X POST "http://localhost:8000/api/analyze" \
  -H "Content-Type: application/json" \
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

### Health Check

```bash
curl "http://localhost:8000/health"
```

## Configuration

The service can be configured using environment variables:

- `OPENAI_API_KEY`: OpenAI API key
- `ANTHROPIC_API_KEY`: Anthropic API key
- `LOG_LEVEL`: Logging level (default: INFO)
- `DEFAULT_PROVIDER`: Default LLM provider (default: openai/gpt-4o-mini)
- `DEFAULT_TEMPERATURE`: Default temperature (default: 0.2)
- `DEFAULT_MAX_TOKENS`: Default max tokens (default: 1200)

## Development

### Running Tests

```bash
# Make sure virtual environment is activated
source venv/bin/activate
pytest
```

### Project Structure

```
app/
├── __init__.py
├── main.py              # FastAPI application
├── config.py            # Configuration management
├── models.py            # Pydantic models
├── logging.py           # Logging configuration
└── api/
    ├── __init__.py
    └── analyze.py       # Analysis endpoints

tests/
├── __init__.py
└── test_main.py         # Basic tests
```

## Requirements

- Python 3.8+
- FastAPI
- yt-dlp
- youtube-transcript-api
- LiteLLM
- OpenAI or Anthropic API key