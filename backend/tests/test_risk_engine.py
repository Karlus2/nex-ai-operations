from datetime import datetime, timezone, timedelta
import pytest
from backend.app.models import Order, OrderStatus, RiskLevel
from backend.app.risk_engine import evaluate_order_risk

@pytest.fixture
def base_time():
    return datetime(2026, 11, 12, 12, 35, 0, tzinfo=timezone.utc)

def test_delivered_order_has_zero_risk(base_time):
    order = Order(
        id="NEX-TEST-1",
        restaurant_name="Restaurante Teste",
        created_at=base_time - timedelta(minutes=50),
        promised_at=base_time - timedelta(minutes=15),
        status=OrderStatus.DELIVERED,
        courier_assigned=True,
        last_status_update_at=base_time - timedelta(minutes=14),
        restaurant_backlog=8,
        estimated_prep_minutes_remaining=0,
        distance_km=2.0
    )
    result = evaluate_order_risk(order, evaluation_time=base_time)
    assert result.score == 0
    assert result.level == RiskLevel.LOW
    assert len(result.signals) == 0

def test_cancelled_order_has_zero_risk(base_time):
    order = Order(
        id="NEX-TEST-2",
        restaurant_name="Restaurante Teste",
        created_at=base_time - timedelta(minutes=40),
        promised_at=base_time - timedelta(minutes=10),
        status=OrderStatus.CANCELLED,
        courier_assigned=False,
        last_status_update_at=base_time - timedelta(minutes=20),
        restaurant_backlog=9,
        estimated_prep_minutes_remaining=0,
        distance_km=2.0
    )
    result = evaluate_order_risk(order, evaluation_time=base_time)
    assert result.score == 0
    assert result.level == RiskLevel.LOW
    assert len(result.signals) == 0

def test_on_time_normal_order(base_time):
    order = Order(
        id="NEX-TEST-3",
        restaurant_name="Restaurante Teste",
        created_at=base_time - timedelta(minutes=10),
        promised_at=base_time + timedelta(minutes=25),
        status=OrderStatus.PREPARING,
        courier_assigned=True,
        last_status_update_at=base_time - timedelta(minutes=2),
        restaurant_backlog=2,
        estimated_prep_minutes_remaining=15,
        distance_km=2.0
    )
    result = evaluate_order_risk(order, evaluation_time=base_time)
    assert result.score == 0
    assert result.level == RiskLevel.LOW
    assert len(result.signals) == 0

def test_sla_breach_and_no_courier(base_time):
    order = Order(
        id="NEX-TEST-4",
        restaurant_name="Restaurante Teste",
        created_at=base_time - timedelta(minutes=30),  # > 15m ago
        promised_at=base_time - timedelta(minutes=5),  # SLA breached (+45)
        status=OrderStatus.READY,
        courier_assigned=False,                        # Sem entregador (+20)
        last_status_update_at=base_time - timedelta(minutes=5),
        restaurant_backlog=2,
        estimated_prep_minutes_remaining=0,
        distance_km=2.0
    )
    result = evaluate_order_risk(order, evaluation_time=base_time)
    # 45 (SLA) + 20 (No courier) = 65
    assert result.score == 65
    assert result.level == RiskLevel.HIGH
    assert len(result.signals) == 2

def test_near_deadline_in_prep_and_high_backlog(base_time):
    order = Order(
        id="NEX-TEST-5",
        restaurant_name="Restaurante Teste",
        created_at=base_time - timedelta(minutes=10),  # < 15 min
        promised_at=base_time + timedelta(minutes=8),   # <= 10 min (+25)
        status=OrderStatus.PREPARING,
        courier_assigned=True,
        last_status_update_at=base_time - timedelta(minutes=5),
        restaurant_backlog=6,                          # Backlog >= 5 (+10)
        estimated_prep_minutes_remaining=12,
        distance_km=2.0
    )
    result = evaluate_order_risk(order, evaluation_time=base_time)
    # 25 (Near deadline) + 10 (Backlog) = 35
    assert result.score == 35
    assert result.level == RiskLevel.MEDIUM
    assert any("Prazo encerra em" in s for s in result.signals)
    assert any("backlog elevado" in s for s in result.signals)

def test_score_clamping_at_100(base_time):
    # Condição extrema onde todas as regras disparariam:
    # 45 (SLA) + 20 (No courier) + 15 (No update) + 10 (Backlog) = 90
    # Note: "+25 near deadline" só dispara se ref_time <= promised_at.
    order = Order(
        id="NEX-TEST-6",
        restaurant_name="Restaurante Teste",
        created_at=base_time - timedelta(minutes=40),
        promised_at=base_time - timedelta(minutes=10),  # +45
        status=OrderStatus.PREPARING,
        courier_assigned=False,                         # +20
        last_status_update_at=base_time - timedelta(minutes=25), # +15
        restaurant_backlog=10,                          # +10
        estimated_prep_minutes_remaining=20,
        distance_km=4.0
    )
    result = evaluate_order_risk(order, evaluation_time=base_time)
    assert result.score == 90
    assert result.level == RiskLevel.HIGH
    assert len(result.signals) == 4

def test_primary_demo_case_nex_1042(base_time):
    order = Order(
        id="NEX-1042",
        restaurant_name="Bistrô Aurora (Fictício)",
        created_at=base_time - timedelta(minutes=35),
        promised_at=base_time - timedelta(minutes=5),
        status=OrderStatus.PREPARING,
        courier_assigned=False,
        last_status_update_at=base_time - timedelta(minutes=17),
        restaurant_backlog=7,
        estimated_prep_minutes_remaining=9,
        distance_km=3.2
    )
    result = evaluate_order_risk(order, evaluation_time=base_time)
    # 45 (prazo) + 20 (sem entregador) + 15 (sem update) + 10 (backlog) = 90
    assert result.score == 90
    assert result.level == RiskLevel.HIGH
    assert len(result.signals) == 4
