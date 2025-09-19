"""
Configuration management for the YouTube Analyzer service.
"""
import os
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class ServiceConfig(BaseModel):
    """Service configuration model."""
    log_level: str = Field(default="INFO", description="Logging level")
    default_provider: str = Field(default="openai/gpt-4o-mini", description="Default LLM provider")
    default_temperature: float = Field(default=0.2, description="Default temperature for LLM")
    default_max_tokens: int = Field(default=1200, description="Default max tokens for LLM")
    request_timeout: int = Field(default=300, description="Request timeout in seconds")
    max_concurrent_requests: int = Field(default=3, description="Max concurrent requests")
    
    # Provider API keys
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    anthropic_api_key: Optional[str] = Field(default=None, description="Anthropic API key")
    
    # Whisper settings
    use_whisper_fallback: bool = Field(default=True, description="Enable Whisper fallback for transcript fetching")
    whisper_max_audio_duration: int = Field(default=3600, description="Maximum audio duration for Whisper (seconds)")
    whisper_chunk_duration: int = Field(default=600, description="Chunk duration for long audio files (seconds)")
    whisper_model: str = Field(default="base", description="Whisper model to use")
    whisper_device: str = Field(default="cpu", description="Device to run Whisper on")
    whisper_compute_type: str = Field(default="int8", description="Compute type for Whisper")
    
    # Custom model configurations
    custom_model_config: Dict[str, Any] = Field(default_factory=dict, description="Custom model configurations")


def load_config() -> ServiceConfig:
    """Load configuration from environment variables."""
    return ServiceConfig(
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        default_provider=os.getenv("DEFAULT_PROVIDER", "openai/gpt-4o-mini"),
        default_temperature=float(os.getenv("DEFAULT_TEMPERATURE", "0.2")),
        default_max_tokens=int(os.getenv("DEFAULT_MAX_TOKENS", "1200")),
        request_timeout=int(os.getenv("REQUEST_TIMEOUT", "300")),
        max_concurrent_requests=int(os.getenv("MAX_CONCURRENT_REQUESTS", "3")),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        use_whisper_fallback=os.getenv("USE_WHISPER_FALLBACK", "true").lower() == "true",
        whisper_max_audio_duration=int(os.getenv("WHISPER_MAX_AUDIO_DURATION", "3600")),
        whisper_chunk_duration=int(os.getenv("WHISPER_CHUNK_DURATION", "600")),
        whisper_model=os.getenv("WHISPER_MODEL", "base"),
        whisper_device=os.getenv("WHISPER_DEVICE", "cpu"),
        whisper_compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
        custom_model_config=eval(os.getenv("CUSTOM_MODEL_CONFIG", "{}"))
    )


# Global configuration instance
config = load_config()
