from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from src.models.base import SchedulaBaseModel


class ApprovalStatus(str, Enum):
    PEN = "PEN"
    APP = "APP"
    REJ = "REJ"

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        schema = handler(core_schema)
        schema["example"] = "APP"
        return schema


class ScheduleApprovalBase(SchedulaBaseModel):
    schedule_id: int = Field(..., description="Schedule ID (INTEGER FK)")
    status: ApprovalStatus

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "schedule_id": 10,
                "status": "APP"
            }
        }
    )


class ScheduleApprovalCreate(ScheduleApprovalBase):
    status: ApprovalStatus = ApprovalStatus.PEN


class ScheduleApprovalUpdate(BaseModel):
    status: Optional[ApprovalStatus] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"status": "REJ"}
        }
    )


class ScheduleApprovalResponse(ScheduleApprovalBase):
    pass


class ScheduleApproval(ScheduleApprovalBase):
    scheapprov_id: int = Field(..., description="Internal PK (BIGINT)")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "scheapprov_id": 501,
                "schedule_id": 10,
                "status": "APP"
            }
        }
    )
