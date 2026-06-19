# src/routes/auth.py

from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Body, status
from datetime import timedelta

from src.models.auth import LoginPayload, LoginSuccess, TokenResponse
from src.models.user import UserResponse
from src.repositories import users as users_repo
from src.utils.auth import create_access_token
from src.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    response_model=LoginSuccess,
    responses={
        200: {
            "description": "Login successful and access token generated",
            "content": {"application/json": {"example":
                                                 {"message": "Login successful",
                                                  "token": {
                                                      "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                                                      "token_type": "bearer",
                                                      "expires_in": 1800,
                                                  },
                                                  "user_data": {
                                                      "first_name": "Moshe", "last_name": "Cohen",
                                                      "email": "moshe.c@ac.il", "role": "L",
                                                      "department_id": 1, "user_name": "MCohen"}
                                                  }
                                             }},
        },
        401: {
            "description": "Unauthorized - Invalid credentials (user_name/user_id mismatch)",
            "content": {"application/json": {"example": {"detail": "Invalid credentials."}}},
        },
        404: {
            "description": "User not found",
            "content": {"application/json": {"example": {"detail": "User not found."}}},
        },
    },
)
async def login_for_access_token(
        payload: LoginPayload = Body(
            ...,
            examples=[{"user_name": "MCohen", "user_id": "123456789"}]
        )
) -> LoginSuccess:
    """
    Authenticate user by username and user_id and generate an access token (JWT).
    """
    # Fetch user by user_name
    user_data = await users_repo.get_user_by_name(payload.user_name)

    if not user_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    # Authentication Check: Verify user_id matches the retrieved user
    if user_data.get('user_id') != payload.user_id or user_data.get('user_name') != payload.user_name:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

    # Token Generation
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    access_token = create_access_token(
        data={"sub": str(user_data["user_internal_id"]), "role": user_data["role"]},
        expires_delta=access_token_expires
    )

    # Prepare Response Data

    # Remove internal IDs before sending to frontend
    user_response_data = user_data.copy()
    user_response_data.pop("user_internal_id", None)
    user_response_data.pop("user_id", None)
    user_response_data.pop("phone_num", None)

    token_response = TokenResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, 
        user_data=UserResponse(**user_response_data)
    )

    return LoginSuccess(
        message="Login successful",
        token=token_response
    )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Logout successful",
            "content": {
                "application/json": {"example": {"message": "Logout successful. Client should discard token."}}},
        }
    }
)
async def logout_user() -> Dict[str, str]:
    """
    Log out the user (instructs the client to discard the JWT token).
    """
    return {"message": "Logout successful. Client should discard token."}