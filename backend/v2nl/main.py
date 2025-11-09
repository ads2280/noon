"""
Voice-to-natural-language transcription service using Deepgram.
Provides a class-based interface for transcribing audio files with optional custom vocabulary support.
"""

import os
import io
from pathlib import Path
from typing import Optional, List, Tuple, Union, BinaryIO
from dotenv import load_dotenv
import logging
import httpx

# Load .env file from v2nl directory
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TranscriptionService:
    """
    Service for transcribing audio files using Deepgram's prerecorded API.
    
    Example usage:
        service = TranscriptionService()
        text = await service.transcribe("path/to/audio.wav", vocabulary="term1,term2")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "nova-3",
        language: str = "en-US",
        smart_format: bool = True,
        punctuate: bool = True,
    ):
        """
        Initialize the transcription service.
        
        Args:
            api_key: Deepgram API key. If not provided, will use DEEPGRAM_API_KEY env var.
            model: Deepgram model to use (default: "nova-3")
            language: Language code (default: "en-US")
            smart_format: Enable smart formatting (default: True)
            punctuate: Enable punctuation (default: True)
        """
        self.api_key = api_key or os.getenv("DEEPGRAM_API_KEY")
        self.model = model
        self.language = language
        self.smart_format = smart_format
        self.punctuate = punctuate

        if not self.api_key:
            logger.warning("DEEPGRAM_API_KEY not found in environment variables")

    def _parse_vocabulary(self, vocab_str: Optional[str]) -> List[str]:
        """Parse comma-separated vocabulary string into list of terms."""
        if not vocab_str:
            return []
        parts = [p.strip() for p in vocab_str.split(",")]
        return [p for p in parts if p]

    def _vocabulary_param_name(self, model_name: str) -> str:
        """Return the Deepgram query parameter for boosted vocabulary."""
        if model_name.lower().startswith("nova-3"):
            return "keyterm"
        return "keywords"

    def _guess_mime_type(self, filename: str) -> str:
        """Guess MIME type from file extension."""
        ext = Path(filename).suffix.lower()
        MIME_MPEG = "audio/mpeg"
        MIME_MP4 = "audio/mp4"
        mime_types = {
            ".mp3": MIME_MPEG,
            ".mp4": MIME_MP4,
            ".mpeg": MIME_MPEG,
            ".mpga": MIME_MPEG,
            ".m4a": MIME_MP4,
            ".wav": "audio/wav",
            ".webm": "audio/webm",
            ".flac": "audio/flac",
            ".ogg": "audio/ogg",
            ".opus": "audio/opus",
            ".aac": "audio/aac",
            ".mp2": MIME_MPEG,
            ".3gp": "audio/3gpp",
        }
        return mime_types.get(ext, "application/octet-stream")

    def _extract_transcript_from_deepgram(self, json_payload: dict) -> str:
        """Extract transcript text from Deepgram API response."""
        try:
            channels = json_payload.get("results", {}).get("channels", [])
            if not channels:
                return ""
            alts = channels[0].get("alternatives", [])
            if not alts:
                return ""
            return alts[0].get("transcript", "") or ""
        except Exception:
            return ""

    async def transcribe(
        self,
        file: Union[str, Path, BinaryIO, bytes],
        vocabulary: Optional[str] = None,
        filename: Optional[str] = None,
        mime_type: Optional[str] = None,
    ) -> str:
        """
        Transcribe an audio file using Deepgram's prerecorded API.
        
        Args:
            file: Audio file as:
                - File path (str or Path)
                - File-like object (BinaryIO)
                - Bytes object
            vocabulary: Optional comma-separated custom vocabulary terms
            filename: Optional filename (used for MIME type detection if file is bytes or BinaryIO)
            mime_type: Optional MIME type (overrides auto-detection)
            
        Returns:
            Transcribed text as string
            
        Raises:
            ValueError: If API key is not configured or file is empty
            httpx.HTTPStatusError: If Deepgram API returns an error
        """
        if not self.api_key:
            raise ValueError(
                "Deepgram API key not configured. Please set DEEPGRAM_API_KEY or pass api_key to __init__."
            )

        # Read audio bytes from various input types
        audio_bytes: bytes
        actual_filename: str
        
        if isinstance(file, (str, Path)):
            # File path
            file_path = Path(file)
            if not file_path.exists():
                raise FileNotFoundError(f"Audio file not found: {file_path}")
            actual_filename = file_path.name
            with open(file_path, "rb") as f:
                audio_bytes = f.read()
        elif isinstance(file, bytes):
            # Bytes object
            audio_bytes = file
            actual_filename = filename or "audio.wav"
        elif isinstance(file, io.IOBase):
            # File-like object
            audio_bytes = file.read()
            actual_filename = filename or getattr(file, "name", "audio.wav")
        else:
            raise TypeError(
                f"Unsupported file type: {type(file)}. Expected str, Path, bytes, or file-like object."
            )

        if not audio_bytes:
            raise ValueError("Empty file")

        # Validate file size (25 MB limit to mirror prior behavior)
        if len(audio_bytes) > 25 * 1024 * 1024:
            raise ValueError("File size exceeds 25 MB limit")

        # Determine MIME type
        if mime_type:
            content_type = mime_type
        else:
            content_type = self._guess_mime_type(actual_filename)

        # Build query params
        vocab_terms = self._parse_vocabulary(vocabulary)
        params: List[Tuple[str, str]] = [
            ("model", self.model),
            ("smart_format", "true" if self.smart_format else "false"),
            ("punctuate", "true" if self.punctuate else "false"),
            ("language", self.language),
        ]
        vocab_param = self._vocabulary_param_name(self.model)
        for term in vocab_terms:
            # Deepgram supports repeating vocabulary params
            params.append((vocab_param, term))

        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": content_type,
        }

        logger.info(
            f"Deepgram prerecord transcription start: {actual_filename}, {len(audio_bytes)} bytes"
        )
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.deepgram.com/v1/listen",
                params=params,
                headers=headers,
                content=audio_bytes,
            )
            resp.raise_for_status()
            payload = resp.json()

        text = self._extract_transcript_from_deepgram(payload)
        logger.info("Deepgram prerecord transcription completed")
        return text
