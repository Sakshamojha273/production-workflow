from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.models.product import Product
from app.schemas.product import ProductListResponse, ProductResponse

router = APIRouter()


@router.get("", response_model=ProductListResponse)
async def get_products(db: AsyncSession = Depends(get_db)):
    """Get all products"""
    stmt = select(Product).order_by(Product.name)
    result = await db.execute(stmt)
    products = result.scalars().all()
    
    return ProductListResponse(
        products=[ProductResponse.from_orm(p) for p in products],
        total=len(products)
    )


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str, db: AsyncSession = Depends(get_db)):
    """Get product by ID"""
    stmt = select(Product).where(Product.product_id == product_id)
    result = await db.execute(stmt)
    product = result.scalar_one_or_none()
    
    if not product:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Product not found")
    
    return ProductResponse.from_orm(product)