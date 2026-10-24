import datetime
import uuid
from typing import List
from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session
from sqlalchemy import update

from .config import config
from .database import engine, Base, get_db
from .models import Restaurant, MenuItem, Reservation
from .schemas import (
    UniformErrorResponse, ErrorDetail,
    RestaurantCreate, RestaurantResponse,
    MenuItemCreate, MenuItemResponse,
    ReservationCreate, ReservationResponse
)
from .middleware import CorrelationIdMiddleware, logger

# Initialize database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FoodFlow - Restaurant & Menu Service",
    version="1.0.0",
    description="Manages restaurant catalogs, menus, dish inventory, and atomic stock reservations for FoodFlow."
)

app.add_middleware(CorrelationIdMiddleware)

# --- Standardized Exception Handlers ---
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    corr_id = getattr(request.state, "correlation_id", "N/A")
    error_code = "HTTP_ERROR"
    if exc.status_code == 404:
        error_code = "NOT_FOUND"
    elif exc.status_code == 409:
        error_code = "RESOURCE_CONFLICT"
    elif exc.status_code == 422:
        error_code = "UNPROCESSABLE_ENTITY"

    content = {
        "error": {
            "code": error_code,
            "message": str(exc.detail),
            "details": {}
        },
        "correlation_id": corr_id
    }
    return JSONResponse(status_code=exc.status_code, content=content)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    corr_id = getattr(request.state, "correlation_id", "N/A")
    content = {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Invalid request parameters or payload",
            "details": {"errors": exc.errors()}
        },
        "correlation_id": corr_id
    }
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=content)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    corr_id = getattr(request.state, "correlation_id", "N/A")
    logger.exception(f"Unhandled error processing request: {exc}", extra={"correlation_id": corr_id})
    content = {
        "error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred. Please retry later.",
            "details": {}
        },
        "correlation_id": corr_id
    }
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=content)


# --- Operability: Health Check ---
@app.get("/health", tags=["Operability"])
def health_check():
    """Liveness and readiness health probe."""
    return {
        "status": "UP",
        "service": config.SERVICE_NAME,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }


# --- Restaurant Catalog APIs ---
@app.get("/api/v1/restaurants", response_model=List[RestaurantResponse], tags=["Restaurants"])
def list_restaurants(db: Session = Depends(get_db)):
    """Retrieve list of all active restaurants."""
    return db.query(Restaurant).filter(Restaurant.is_active == True).all()

@app.post("/api/v1/restaurants", response_model=RestaurantResponse, status_code=status.HTTP_201_CREATED, tags=["Restaurants"])
def create_restaurant(payload: RestaurantCreate, db: Session = Depends(get_db)):
    """Register a new restaurant."""
    rest = Restaurant(id=str(uuid.uuid4()), name=payload.name, address=payload.address)
    db.add(rest)
    db.commit()
    db.refresh(rest)
    return rest

@app.get("/api/v1/restaurants/{restaurant_id}", response_model=RestaurantResponse, tags=["Restaurants"])
def get_restaurant(restaurant_id: str, db: Session = Depends(get_db)):
    """Retrieve restaurant details."""
    rest = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not rest:
        raise HTTPException(status_code=404, detail=f"Restaurant '{restaurant_id}' not found")
    return rest


# --- Menu & Stock Management APIs ---
@app.get("/api/v1/restaurants/{restaurant_id}/menu", response_model=List[MenuItemResponse], tags=["Menu"])
def list_menu_items(restaurant_id: str, db: Session = Depends(get_db)):
    """Retrieve menu items for a specific restaurant."""
    rest = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not rest:
        raise HTTPException(status_code=404, detail=f"Restaurant '{restaurant_id}' not found")
    return db.query(MenuItem).filter(MenuItem.restaurant_id == restaurant_id).all()

@app.post("/api/v1/restaurants/{restaurant_id}/menu", response_model=MenuItemResponse, status_code=status.HTTP_201_CREATED, tags=["Menu"])
def add_menu_item(restaurant_id: str, payload: MenuItemCreate, db: Session = Depends(get_db)):
    """Add a new dish to the restaurant menu."""
    rest = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not rest:
        raise HTTPException(status_code=404, detail=f"Restaurant '{restaurant_id}' not found")

    item = MenuItem(
        id=str(uuid.uuid4()),
        restaurant_id=restaurant_id,
        name=payload.name,
        description=payload.description or "",
        price=payload.price,
        available_quantity=payload.available_quantity,
        version=1
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@app.get("/api/v1/restaurants/{restaurant_id}/menu/{item_id}", response_model=MenuItemResponse, tags=["Menu"])
def get_menu_item(restaurant_id: str, item_id: str, db: Session = Depends(get_db)):
    """Get single menu item detail and stock."""
    item = db.query(MenuItem).filter(MenuItem.id == item_id, MenuItem.restaurant_id == restaurant_id).first()
    if not item:
        raise HTTPException(status_code=404, detail=f"Menu item '{item_id}' not found")
    return item


# --- Challenge 1 (Concurrency Control) & Stock Reservation ---
@app.post("/api/v1/restaurants/reservations", response_model=ReservationResponse, status_code=status.HTTP_201_CREATED, tags=["Reservations"])
def reserve_stock(payload: ReservationCreate, request: Request, db: Session = Depends(get_db)):
    """
    BR1: Stock Sufficiency & Atomic Concurrency Control.
    Atomically decrements stock if and only if available_quantity >= requested quantity.
    Prevents race conditions / overselling under simultaneous requests.
    """
    corr_id = getattr(request.state, "correlation_id", "N/A")

    # Atomic conditional update
    stmt = (
        update(MenuItem)
        .where(MenuItem.id == payload.item_id, MenuItem.available_quantity >= payload.quantity)
        .values(
            available_quantity=MenuItem.available_quantity - payload.quantity,
            version=MenuItem.version + 1
        )
    )
    result = db.execute(stmt)

    if result.rowcount == 0:
        db.rollback()
        # Find item to provide precise diagnostic
        item = db.query(MenuItem).filter(MenuItem.id == payload.item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail=f"Menu item '{payload.item_id}' not found")
        logger.warning(
            f"BR1 Stock Insufficient: item {payload.item_id} has {item.available_quantity} available, requested {payload.quantity}",
            extra={"correlation_id": corr_id}
        )
        raise HTTPException(
            status_code=409,
            detail=f"Stock insufficient: requested {payload.quantity}, only {item.available_quantity} remaining."
        )

    # Stock decremented successfully, record reservation
    reservation = Reservation(
        id=str(uuid.uuid4()),
        order_id=payload.order_id,
        restaurant_id=payload.restaurant_id,
        item_id=payload.item_id,
        quantity=payload.quantity,
        status="RESERVED"
    )
    db.add(reservation)
    db.commit()
    db.refresh(reservation)

    logger.info(
        f"Reserved {payload.quantity} units of item {payload.item_id} for order {payload.order_id}",
        extra={"correlation_id": corr_id}
    )
    return reservation


# --- Challenge 3C (Saga Compensation) ---
@app.post("/api/v1/restaurants/reservations/{reservation_id}/release", response_model=ReservationResponse, tags=["Reservations"])
def release_reservation(reservation_id: str, request: Request, db: Session = Depends(get_db)):
    """
    Saga Compensating Action:
    Restores previously reserved stock when downstream payment or delivery fails.
    """
    corr_id = getattr(request.state, "correlation_id", "N/A")
    reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()
    if not reservation:
        raise HTTPException(status_code=404, detail=f"Reservation '{reservation_id}' not found")

    if reservation.status == "RELEASED":
        # Idempotent release
        return reservation

    if reservation.status == "CONFIRMED":
        raise HTTPException(status_code=400, detail="Cannot release an already confirmed reservation")

    # Restore stock atomically
    stmt = (
        update(MenuItem)
        .where(MenuItem.id == reservation.item_id)
        .values(
            available_quantity=MenuItem.available_quantity + reservation.quantity,
            version=MenuItem.version + 1
        )
    )
    db.execute(stmt)
    reservation.status = "RELEASED"
    db.commit()
    db.refresh(reservation)

    logger.info(
        f"SAGA COMPENSATION: Released reservation {reservation_id}, restored {reservation.quantity} stock units",
        extra={"correlation_id": corr_id}
    )
    return reservation

@app.post("/api/v1/restaurants/reservations/{reservation_id}/confirm", response_model=ReservationResponse, tags=["Reservations"])
def confirm_reservation(reservation_id: str, request: Request, db: Session = Depends(get_db)):
    """Confirms reservation permanently upon successful payment."""
    corr_id = getattr(request.state, "correlation_id", "N/A")
    reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()
    if not reservation:
        raise HTTPException(status_code=404, detail=f"Reservation '{reservation_id}' not found")

    reservation.status = "CONFIRMED"
    db.commit()
    db.refresh(reservation)

    logger.info(f"Confirmed reservation {reservation_id}", extra={"correlation_id": corr_id})
    return reservation

@app.get("/api/v1/restaurants/reservations/{reservation_id}", response_model=ReservationResponse, tags=["Reservations"])
def get_reservation(reservation_id: str, db: Session = Depends(get_db)):
    """Retrieve reservation details."""
    reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()
    if not reservation:
        raise HTTPException(status_code=404, detail=f"Reservation '{reservation_id}' not found")
    return reservation
