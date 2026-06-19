# src/middleware/auth.py

from typing import Dict, Any
from fastapi import HTTPException, status
from fastapi.security import HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from src.utils.auth import decode_token
from jose import JWTError


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Middleware for automatic JWT authentication based on route prefixes.
    
    Protected Routes:
    - /lecturer/* - Requires valid JWT with role "L"
    - /secretary/* - Requires valid JWT with role "S"
    
    Public Routes (no authentication):
    - /auth/* - Login/logout endpoints
    - /dev/* - Development/testing endpoints
    - /docs, /openapi.json, /redoc - API documentation
    
    Authenticated requests populate request.state with:
    - request.state.user_payload: Full JWT payload (dict)
    - request.state.user_internal_id: User's internal ID (int)
    - request.state.user_role: User's role ("L" or "S")
    """
    
    # Route prefixes that require authentication
    PROTECTED_PREFIXES = {
        "/lecturer": "L",  # Requires Lecturer role
        "/secretary": "S",  # Requires Secretary role
    }
    
    # Route prefixes that are always public (no auth required)
    PUBLIC_PREFIXES = (
        "/auth",
        "/dev",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/ws",  # WebSocket endpoints
        "/webhooks", # Webhook endpoints
    )
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request and enforce authentication based on path."""
        path = request.url.path
        
        # Skip authentication for public routes
        if any(path.startswith(prefix) for prefix in self.PUBLIC_PREFIXES):
            return await call_next(request)

        # Skip authentication for OPTIONS response
        if request.method == "OPTIONS":
            return await call_next(request)
        
        # Check if path requires authentication
        required_role = None
        for prefix, role in self.PROTECTED_PREFIXES.items():
            if path.startswith(prefix):
                required_role = role
                break
        
        # If no protected prefix matches, allow request (default: unprotected)
        if required_role is None:
            return await call_next(request)
        
        # Extract Bearer token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid or missing authentication token"}
            )
        
        token = auth_header.split("Bearer ")[1]
        
        # Validate JWT and extract payload
        try:
            payload = decode_token(token)
        except HTTPException as exc:
            # decode_token raises HTTPException for invalid/expired tokens
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail}
            )
        except JWTError:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid authentication token"}
            )
        
        # Verify token contains required claims
        user_internal_id = payload.get("sub")
        user_role = payload.get("role")
        
        if user_internal_id is None or user_role is None:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid token payload"}
            )
        
        # Enforce role-based access control
        if user_role != required_role:
            role_names = {"L": "Lecturer", "S": "Secretary"}
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": f"User does not have {role_names.get(required_role, 'required')} privileges"}
            )
        
        # Store user context in request.state for endpoint access
        request.state.user_payload = payload
        request.state.user_internal_id = int(user_internal_id)
        request.state.user_role = user_role
        
        # Proceed to endpoint
        return await call_next(request)
