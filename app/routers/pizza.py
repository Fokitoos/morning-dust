from fastapi import APIRouter, Query

from app.schemas.pizza import PizzaCalcRequest, PizzaCalcResponse, YeastType
from app.services.pizza_service import calculate

router = APIRouter()


@router.get("", response_model=PizzaCalcResponse)
def pizza_calc(
    pizzas: int = Query(default=2, ge=1, le=12),
    hours_min: int = Query(default=8, ge=2, le=72),
    hours_max: int = Query(default=24, ge=2, le=72),
    yeast: YeastType = "dry",
) -> PizzaCalcResponse:
    req = PizzaCalcRequest(pizzas=pizzas, hours_min=hours_min, hours_max=hours_max, yeast=yeast)
    return calculate(req)
