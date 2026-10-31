from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.core.database import get_db
from app.core.config import settings
from app.models.data_quality_report import DataQualityReport, DataQualityStatus
from app.services.data_processor import DataProcessor
from app.schemas.data import DataUploadResponse, DataQualityResponse

router = APIRouter()


@router.post("/upload", response_model=DataUploadResponse)
async def upload_dataset(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Upload and process CSV dataset"""
    
    # Validate file type - check both content type and file extension
    allowed_content_types = settings.UPLOAD_ALLOWED_TYPES + ["text/plain", "application/vnd.ms-excel"]
    allowed_extensions = [".csv"]
    
    file_extension = ""
    if file.filename:
        file_extension = "." + file.filename.split(".")[-1].lower()
    
    is_valid_type = (
        (file.content_type and file.content_type in allowed_content_types) or
        file_extension in allowed_extensions
    )
    
    if not is_valid_type:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: CSV files (.csv). Received: {file.content_type or 'unknown'}"
        )
    
    # Read file
    content = await file.read()
    
    # Check file size
    if len(content) > settings.UPLOAD_MAX_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max size: {settings.UPLOAD_MAX_SIZE / 1024 / 1024}MB"
        )
    
    # Process file
    processor = DataProcessor(db)
    try:
        report = await processor.process_csv(content, file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return DataUploadResponse.from_orm(report)


@router.get("/quality", response_model=List[DataQualityResponse])
async def get_data_quality_reports(
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """Get data quality reports"""
    stmt = select(DataQualityReport).order_by(DataQualityReport.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    reports = result.scalars().all()
    
    return [DataQualityResponse.from_orm(r) for r in reports]


@router.get("/quality/{report_id}", response_model=DataQualityResponse)
async def get_data_quality_report(report_id: str, db: AsyncSession = Depends(get_db)):
    """Get specific data quality report"""
    stmt = select(DataQualityReport).where(DataQualityReport.report_id == report_id)
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    return DataQualityResponse.from_orm(report)