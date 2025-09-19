# Compact Product Description - YouTube Analyzer Service

## Project Summary
A service that exposes an HTTP API endpoint to receive one or more YouTube URLs, extract video metadata and transcripts in Spanish and English, and generate structured summaries in both languages.

## Problem/Motivation
Spanish-speaking users need tools that process YouTube content in multiple languages and deliver understandable, structured summaries. Many existing tools are optimized only for English, limiting access to educational and professional content for Spanish-speaking audiences.

## Key Features
1. **Transcript extraction** in Spanish and English
2. **Structured summaries** generated in both languages
3. **HTTP API endpoint** to analyze one or multiple videos per request
4. **Response format** as JSON containing metadata, transcripts, and summaries, with optional Markdown fields
5. **Batch support** for multiple videos in a single request

## Target Users
- Students and professionals consuming educational YouTube content
- Researchers analyzing videos in multiple languages
- Creators summarizing their own videos
- Users seeking insights from educational Spanish content

## Proposed Technologies
- **Python** as the primary language
- **FastAPI** for the HTTP service layer
- **yt-dlp** for YouTube metadata extraction
- **youtube-transcript-api** for transcript retrieval
- **OpenAI/Anthropic API** for AI-generated summaries
- **LiteLLM** for unified LLM provider handling

