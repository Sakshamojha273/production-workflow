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
    
    # Validate file type by extension. Browsers send CSVs as text/csv,
    # application/vnd.ms-excel or text/plain, so the content type alone can't tell a
    # .csv from a .txt; the .csv extension is required.
    file_extension = ""
    if file.filename and "." in file.filename:
        file_extension = "." + file.filename.rsplit(".", 1)[-1].lower()

    if file_extension != ".csv":
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {file.filename or 'unnamed file'}. Only .csv files are accepted.",
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

    # A rejected file is kept as a Failed report (visible in the history), but the
    # upload itself must fail with the real reason instead of a 200/500.
    if report.status == DataQualityStatus.FAILED:
        raise HTTPException(status_code=422, detail=report.error_message or "Upload failed")

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