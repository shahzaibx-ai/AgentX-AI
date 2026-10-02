from fastapi import APIRouter, UploadFile, HTTPException, status
from openai import AsyncOpenAI, AuthenticationError, RateLimitError, APIError
from app.deps import SettingsDep

router = APIRouter()

@router.post("/stt")
async def transcribe_audio(
    file: UploadFile,
    settings: SettingsDep
):
    if not file.filename:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "No file provided")

    content = await file.read()
    if not content:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Empty audio file")
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Audio file exceeds 25MB limit")

    if not settings.groq_api_key:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Speech-to-text needs GROQ_API_KEY in api/.env"
        )

    try:
        client = AsyncOpenAI(
            api_key=settings.groq_api_key.get_secret_value(),
            base_url="https://api.groq.com/openai/v1"
        )

        # Groq relies on file extension for format detection.
        # Strip codec params from content_type: "audio/webm;codecs=opus" -> "audio/webm"
        base_mime = file.content_type.split(";")[0] if file.content_type else "audio/webm"
        ext_map = {
            "audio/webm": ".webm",
            "audio/mp4": ".mp4",
            "audio/ogg": ".ogg",
            "audio/wav": ".wav",
        }
        ext = ext_map.get(base_mime, ".webm")

        # Use tuple (filename, bytes, content_type)
        response = await client.audio.transcriptions.create(
            file=(f"recording{ext}", content, base_mime),
            model="whisper-large-v3-turbo",
            response_format="json"
        )
        return {"text": response.text.strip()}

    except AuthenticationError:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Groq rejected the API key")
    except RateLimitError:
        raise HTTPException(status.HTTP_429, "Speech-to-text rate limit reached, try again in a moment")
    except APIError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Groq API error: {e.message if hasattr(e, 'message') else str(e)}")
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Transcription failed: {str(e)}")
