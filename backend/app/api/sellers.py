from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.models import Seller, User
from app.db.session import get_db
from app.schemas.content import SellerCreate, SellerOut

router = APIRouter(prefix="/api/sellers", tags=["sellers"])


@router.post("", response_model=SellerOut, status_code=status.HTTP_201_CREATED)
def create_seller(payload: SellerCreate, db: Session = Depends(get_db)) -> Seller:
    # Left unauthenticated for now, matching /api/listings and /api/reviews:
    # in production this would be called by the marketplace backend via a
    # scoped API key (Day 9), not by end users directly.
    seller = Seller(name=payload.name)
    db.add(seller)
    db.commit()
    db.refresh(seller)
    return seller


@router.get("/{seller_id}", response_model=SellerOut)
def get_seller(
    seller_id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> Seller:
    seller = db.get(Seller, seller_id)
    if seller is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Seller not found")
    return seller
