from typing import Optional, Any

from pydantic import BaseModel, Field, ConfigDict

from src.models.base import SchedulaBaseModel


class FairnessReportBase(SchedulaBaseModel):
    schedule_id: int
    lecturer_internal_id: int
    score: float = Field(..., ge=0)
    fullfilled_constraints_json: Optional[Any] = None
    broken_constraints_json: Optional[Any] = None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "schedule_id": 10,
                "lecturer_internal_id": 42,
                "score": 0.91,
                "fullfilled_constraints_json": {"count": 9},
                "broken_constraints_json": {"count": 1}
            }
        }
    )


class FairnessReportCreate(FairnessReportBase):
    pass


class FairnessReportUpdate(BaseModel):
    score: Optional[float] = Field(None, ge=0)
    fullfilled_constraints_json: Optional[Any] = None
    broken_constraints_json: Optional[Any] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "score": 0.95,
                "fullfilled_constraints_json": {"count": 10},
                "broken_constraints_json": {"count": 0}
            }
        }
    )


class FairnessReportResponse(FairnessReportBase):
    pass


class FairnessReport(FairnessReportBase):
    report_id: int = Field(..., description="Internal PK (BIGINT)")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "report_id": 51,
                "schedule_id": 10,
                "lecturer_internal_id": 42,
                "score": 0.91,
                "fullfilled_constraints_json": {"count": 9},
                "broken_constraints_json": {"count": 1}
            }
        }
    )
