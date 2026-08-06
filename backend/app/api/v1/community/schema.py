"""
Pydantic schema request dan response untuk endpoint community Verifin.
"""

from typing import Optional
from pydantic import BaseModel, Field


class CommunityReportIn(BaseModel):
    company_name: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=32)
    email: str | None = Field(None, max_length=255)
    url: str | None = Field(None, max_length=512)
    report_type: str = Field("penipuan", max_length=24)
    description: str | None = Field(None, max_length=4000)
    reporter_contact: str | None = Field(None, max_length=255)


class CommunityReportOut(BaseModel):
    id: str
    report_type: str
    company_name: str | None
    phone: str | None
    email: str | None
    url: str | None
    description: str | None
    created_at: str
