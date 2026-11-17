import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.config import settings
from backend.app.seed import seed_database

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_clean_db():
    seed_database(drop_existing=True)

def test_healthcheck():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "nex-backend-api"

def test_summary_kpis():
    response = client.get("/api/summary")
    assert response.status_code == 200
    data = response.json()
    assert "active_orders" in data
    assert "high_risk_orders" in data
    assert "pending_approvals" in data
    assert "executed_actions" in data
    assert data["active_orders"] > 0

def test_list_and_filter_orders():
    # Sem filtro
    response = client.get("/api/orders")
    assert response.status_code == 200
    orders = response.json()
    assert len(orders) >= 40

    # Filtro por status
    response_prep = client.get("/api/orders?status=preparing")
    assert response_prep.status_code == 200
    prep_orders = response_prep.json()
    assert all(o["status"] == "preparing" for o in prep_orders)

    # Filtro por risco
    response_high = client.get("/api/orders?risk=high")
    assert response_high.status_code == 200
    high_orders = response_high.json()
    assert all(o["incident"]["risk_level"] == "high" for o in high_orders if o["incident"])

def test_order_detail_nex_1042():
    response = client.get("/api/orders/NEX-1042")
    assert response.status_code == 200
    data = response.json()
    assert data["order"]["id"] == "NEX-1042"
    assert data["order"]["restaurant_name"] == "Bistrô Aurora (Fictício)"
    assert len(data["events"]) >= 3
    assert data["calculated_risk"]["score"] == 90
    assert data["calculated_risk"]["level"] == "high"

def test_internal_api_authentication():
    # Sem cabeçalho -> Deve retornar 401
    resp_unauth = client.get("/api/internal/policies/POL-DELAY-01")
    assert resp_unauth.status_code == 401

    # Com chave errada -> Deve retornar 401
    resp_bad = client.get(
        "/api/internal/policies/POL-DELAY-01",
        headers={"X-Internal-Key": "wrong_key"}
    )
    assert resp_bad.status_code == 401

    # Com chave correta -> Deve retornar 200
    resp_ok = client.get(
        "/api/internal/policies/POL-DELAY-01",
        headers={"X-Internal-Key": settings.INTERNAL_API_KEY}
    )
    assert resp_ok.status_code == 200
    policy = resp_ok.json()
    assert policy["code"] == "POL-DELAY-01"
    assert policy["recommended_action"] == "CREATE_INTERNAL_TICKET"

def test_mock_ticket_requires_human_approval():
    headers = {"X-Internal-Key": settings.INTERNAL_API_KEY}
    payload = {
        "incident_id": "INC-1042",
        "priority": "high",
        "category": "late_delivery",
        "description": "Tentativa não autorizada de criar ticket",
        "created_by_workflow_id": "WF02_test"
    }
    # INC-1042 no seed está em status 'detected' (sem aprovação humana)
    resp = client.post("/api/internal/mock-tickets", json=payload, headers=headers)
    assert resp.status_code == 403
    assert "não possui aprovação humana persistida" in resp.json()["detail"]

def test_mock_ticket_idempotency():
    headers = {"X-Internal-Key": settings.INTERNAL_API_KEY}
    
    # Preparar INC-1042 com proposta do agente e aprovação do operador
    from backend.app.repositories import get_incident, save_incident
    from backend.app.models import IncidentStatus, AgentResult, ActionType
    from datetime import datetime, timezone
    
    inc = get_incident("INC-1042")
    inc.status = IncidentStatus.APPROVED
    inc.approved_at = datetime.now(timezone.utc)
    inc.agent_result = AgentResult(
        incident_id=inc.id,
        summary="Atraso severo sem entregador alocado",
        evidence=[],
        hypotheses=[],
        recommended_action=ActionType.CREATE_INTERNAL_TICKET,
        priority="high",
        action_arguments={"category": "late_delivery"},
        operator_message="Supervisão aprovada",
        requires_human_approval=True
    )
    save_incident(inc)

    payload = {
        "incident_id": "INC-1042",
        "priority": "high",
        "category": "late_delivery",
        "description": "Atraso operacional severo e sem entregador alocado",
        "created_by_workflow_id": "WF02_test"
    }

    # Primeira criação
    resp1 = client.post("/api/internal/mock-tickets", json=payload, headers=headers)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["status"] == "created"
    assert data1["ticket"]["id"] == "TCK-1042"

    # Segunda chamada com mesmo ID (Idempotência)
    resp2 = client.post("/api/internal/mock-tickets", json=payload, headers=headers)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["status"] == "already_exists"
    assert data2["ticket"]["id"] == "TCK-1042"
    data2 = resp2.json()
    assert data2["status"] == "already_exists"
    assert data2["ticket"]["id"] == "TCK-1042"

def test_demo_reset_endpoint():
    response = client.post("/api/demo/reset")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "reset_successful"
