"""
Pydantic schema request dan response untuk endpoint community Verifin.
"""

from typing import Optional
from pydantic import BaseModel, Field


class CommunityReportIn(BaseModel):
    company_name: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=32)
    email: Optional[str] = Field(None, max_length=255)
    url: Optional[str] = Field(None, max_length=512)
    report_type: str = Field("penipuan", max_length=24)
    description: Optional[str] = Field(None, max_length=4000)
    reporter_contact: Optional[str] = Field(None, max_length=255)


class CommunityReportOut(BaseModel):
    id: str
    report_type: str
    company_name: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    url: Optional[str]
    description: Optional[str]
    created_at: str
