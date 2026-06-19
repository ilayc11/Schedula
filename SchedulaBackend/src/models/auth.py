from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from src.models.user import UserResponse

class LoginPayload(BaseModel):
    """Payload for user login attempt based on two identifiers (user_name + user_id)."""
    user_name: str = Field(..., description="Unique username for login")
    user_id: str = Field(..., min_length=9, max_length=9, description="External client-supplied ID (e.g., identity number)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"user_name": "MCohen", "user_id": "123456789"}
        }
    )


class TokenData(BaseModel):
    """Data stored inside the JWT token payload (claims)."""
    sub: Optional[str] = Field(None, description="Subject: The user_internal_id stored as a string")
    role: Optional[str] = Field(None, description="User's role for authorization checks")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"sub": "42", "role": "L"}
        }
    )


class TokenResponse(BaseModel):
    """Response model for successful login containing the JWT."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Token expiration time in seconds")
    user_data: UserResponse

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 1800,
                "user_data": {
                    "first_name": "Moshe",
                    "last_name": "Cohen",
                    "email": "moshe.c@example.com",
                    "role": "L",
                    "department_id": 1,
                    "user_name": "MCohen"
                }
            }
        }
    )


class LoginSuccess(BaseModel):
    """The full success response combining token and user data."""
    message: str = "Login successful"
    token: TokenResponse

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "Login successful",
                "token": {
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "token_type": "bearer",
                    "expires_in": 1800,
                    "user_data": {
                        "first_name": "Moshe",
                        "last_name": "Cohen",
                        "email": "moshe.c@example.com",
                        "role": "L",
                        "department_id": 1,
                        "user_name": "MCohen"
                    }
                }
            }
        }
    )