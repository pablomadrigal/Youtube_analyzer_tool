# Whisper Fallback Feature

This document describes the Whisper fallback functionality that automatically transcribes YouTube videos when official transcripts are unavailable.

## Overview

The YouTube Analyzer Tool now includes an automatic fallback mechanism using OpenAI's Whisper API. When YouTube's official transcripts are not available (disabled, not found, or error), the system will:

1. Download the audio from the YouTube video using `yt-dlp`
2. Transcribe the audio using OpenAI's Whisper API
3. Return the transcript in the same format as YouTube transcripts

## Configuration

Add these environment variables to your `.env` file:

```bash
# Whisper Fallback Configuration
USE_WHISPER_FALLBACK=true
WHISPER_MAX_AUDIO_DURATION=3600
WHISPER_CHUNK_DURATION=600
OPENAI_API_KEY=your_openai_api_key_here
```

### Configuration Options

- `USE_WHISPER_FALLBACK`: Enable/disable the Whisper fallback (default: true)
- `WHISPER_MAX_AUDIO_DURATION`: Maximum video duration in seconds for Whisper processing (default: 3600 = 1 hour)
- `WHISPER_CHUNK_DURATION`: Duration of audio chunks for long videos (default: 600 = 10 minutes)
- `OPENAI_API_KEY`: Your OpenAI API key (required for Whisper)

## How It Works

### 1. Normal Flow
- The system first attempts to fetch official YouTube transcripts
- If successful, returns the YouTube transcripts

### 2. Fallback Flow
When YouTube transcripts are unavailable:
- Downloads audio using `yt-dlp` (supports various formats: wav, mp3, etc.)
- Validates audio file size (max 25MB for Whisper API)
- Transcribes audio using OpenAI Whisper API
- Returns transcript with `source: "whisper"` in the metadata

### 3. Error Handling
- If audio download fails: Returns download error
- If audio file too large: Returns file size error
- If Whisper API fails: Returns transcription error
- If video too long: Returns duration error

## Supported Languages

Whisper supports automatic language detection and can transcribe in most languages. The system will attempt transcription for each requested language code.

## File Size Limits

- **Whisper API limit**: 25MB maximum
- **Video duration limit**: Configurable via `WHISPER_MAX_AUDIO_DURATION`
- **Long videos**: Automatically chunked if duration exceeds limits

## Cost Considerations

- OpenAI Whisper API charges per minute of audio
- Consider setting `WHISPER_MAX_AUDIO_DURATION` to limit costs
- The system will reject videos longer than the configured limit

## Dependencies

New dependencies added to `requirements.txt`:
- `openai>=1.0.0` - OpenAI API client
- `librosa>=0.10.0` - Audio processing (for chunking long files)
- `soundfile>=0.12.0` - Audio file I/O (for chunking long files)

## Error Codes

New error codes introduced:
- `WHISPER_FAILED` - Whisper transcription failed for all languages
- `WHISPER_ERROR` - Unexpected error in Whisper fallback
- `FILE_TOO_LARGE` - Audio file exceeds Whisper API limit
- `VIDEO_TOO_LONG` - Video duration exceeds configured limit
- `DOWNLOAD_FAILED` - Audio download failed
- `TEMP_DIR_ERROR` - Failed to create temporary directory

## Testing

Run the tests to verify the functionality:

```bash
pytest tests/test_whisper_fallback.py -v
```

## Security Notes

- Audio files are temporarily downloaded and automatically cleaned up
- Temporary files are stored in system temp directory
- No audio files are permanently stored
- OpenAI API key should be kept secure and not committed to version control

## Troubleshooting

### Common Issues

1. **"OpenAI API key is required"**
   - Set `OPENAI_API_KEY` in your environment

2. **"Audio file is too large"**
   - Reduce `WHISPER_MAX_AUDIO_DURATION` or use chunking for long videos

3. **"Rate limit exceeded"**
   - Wait and retry, or check your OpenAI API usage limits

4. **"Video is too long"**
   - Increase `WHISPER_MAX_AUDIO_DURATION` or use chunking

### Debugging

Enable debug logging to see detailed information:

```bash
LOG_LEVEL=DEBUG
```

This will show:
- Audio download progress
- Whisper API calls
- File cleanup operations
- Error details
