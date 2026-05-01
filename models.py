from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime, timezone
from database import Base


class JobPosting(Base):
    __tablename__ = "job_postings"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(200))
    company_url = Column(String(500))
    job_title = Column(String(200))
    prefecture = Column(String(50))
    city = Column(String(100))
    employment_type = Column(String(50))
    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    salary_type = Column(String(20))
    description = Column(Text)
    requirements = Column(Text)
    preferred_skills = Column(Text, nullable=True)
    working_hours = Column(Text, nullable=True)
    holidays = Column(Text, nullable=True)
    benefits = Column(Text, nullable=True)
    selection_process = Column(Text, nullable=True)
    appeal_points = Column(Text, nullable=True)  # JSON array as string
    application_url = Column(String(500), nullable=True)
    contact_name = Column(String(100), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    contact_email = Column(String(200), nullable=True)
    original_request = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
