from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Enum, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid
from datetime import datetime
import enum


class WorkerAvailability(str, enum.Enum):
    AVAILABLE = "Available"
    UNAVAILABLE = "Unavailable"
    ON_LEAVE = "On Leave"


class Worker(Base):
    __tablename__ = "workers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    worker_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    department = Column(String(50), nullable=False)
    shift = Column(String(20), default="Day")
    availability = Column(Enum(WorkerAvailability), default=WorkerAvailability.AVAILABLE)
    availability_factor = Column(Float, default=1.0)  # mean fractional availability (0-1) from source data
    max_hours_per_week = Column(Integer, default=40)
    current_hours = Column(Integer, default=0)
    overtime_hours = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    skills = relationship("WorkerSkill", back_populates="worker", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("ix_workers_department", "department"),
        Index("ix_workers_availability", "availability"),
    )


class WorkerSkill(Base):
    __tablename__ = "worker_skills"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    worker_id = Column(String(50), ForeignKey("workers.worker_id"), nullable=False)
    machine_type = Column(String(50), nullable=False)
    proficiency = Column(Float, default=1.0)
    certified = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    worker = relationship("Worker", back_populates="skills")
    
    __table_args__ = (
        Index("ix_worker_skills_worker_machine", "worker_id", "machine_type", unique=True),
    )