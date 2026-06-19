from time import perf_counter
from typing import Any, Dict
import json

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

from src.utils.logger import get_logger


SENSITIVE_KEYS = {"password", "password_hash", "authorization"}


def _mask_sensitive(obj: Any) -> Any:
    try:
        if isinstance(obj, dict):
            masked: Dict[str, Any] = {}
            for k, v in obj.items():
                if k.lower() in SENSITIVE_KEYS:
                    masked[k] = "***"
                else:
                    masked[k] = _mask_sensitive(v)
            return masked
        if isinstance(obj, list):
            return [_mask_sensitive(v) for v in obj]
        return obj
    except Exception:
        return obj


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        logger = get_logger()
        start = perf_counter()

        # Read request body (cached by Starlette so downstream can re-read)
        body_text = ""
        body_obj: Any = None
        try:
            body_bytes = await request.body()
            if body_bytes:
                body_text = body_bytes.decode("utf-8", errors="replace")
                try:
                    body_obj = json.loads(body_text)
                except Exception:
                    body_obj = None
        except Exception:
            body_text = "<unable to read body>"

        route = request.url.path
        client = request.client.host if request.client else "-"
        method = request.method
        query = dict(request.query_params)

        masked_body = _mask_sensitive(body_obj) if body_obj is not None else body_text

        # Log incoming request
        logger.info(
            f"REQUEST {method} {route} query={query} body={masked_body}",
            extra={"route": route, "client": client},
        )

        try:
            response: Response = await call_next(request)
            duration_ms = (perf_counter() - start) * 1000.0

            # Capture response body by consuming the body_iterator
            preview = "<unavailable>"
            try:
                # All Starlette responses use body_iterator under the hood
                body_chunks = []
                async for chunk in response.body_iterator:
                    body_chunks.append(chunk)
                
                # Reconstruct the body
                body_bytes = b"".join(body_chunks)
                
                # Create preview
                if body_bytes:
                    text = body_bytes.decode("utf-8", errors="replace")
                    if response.media_type and "json" in response.media_type:
                        try:
                            obj = json.loads(text)
                            text = json.dumps(_mask_sensitive(obj), ensure_ascii=False)
                        except Exception:
                            pass
                    # Truncate to avoid noisy logs (first 1000 chars for better visibility)
                    preview = text[:1000] if len(text) > 1000 else text
                else:
                    preview = "<empty>"
                
                # Re-create the response with the buffered body
                # This preserves the original response type behavior
                response = Response(
                    content=body_bytes,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type,
                )
            except Exception as e:
                preview = f"<error capturing body: {str(e)}>"

            logger.info(
                f"RESPONSE {method} {route} status={response.status_code} duration_ms={duration_ms:.2f} body={preview}",
                extra={"route": route, "client": client},
            )
            return response
        except Exception as exc:
            duration_ms = (perf_counter() - start) * 1000.0
            logger.error(
                f"ERROR {method} {route} duration_ms={duration_ms:.2f} err={exc}",
                extra={"route": route, "client": client},
            )
            raise
