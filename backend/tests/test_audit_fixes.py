import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.config import settings
from backend.app.seed import seed_database
from backend.app.models import Incident, IncidentStatus, AgentResult, ActionType
from backend.app.repositories import (
    get_incident, save_incident, get_mock_ticket_by_incident,
    list_audit_events, get_simulated_time
)

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_clean_db():
    seed_database(drop_existing=True)

# ------------------------------------------------------------------------------
# Ponto 1: POST /api/internal/mock-tickets exige aprovação humana persistida
# ------------------------------------------------------------------------------
def test_mock_ticket_blocked_without_human_approval():
    headers = {"X-Internal-Key": settings.INTERNAL_API_KEY}
    payload = {
        "incident_id": "INC-1042",
        "priority": "high",
        "category": "late_delivery",
        "description": "Tentativa não autorizada",
        "created_by_workflow_id": "WF02_unauthorized"
    }
    # INC-1042 está em DETECTED no seed (sem aprovação humana)
    response = client.post("/api/internal/mock-tickets", json=payload, headers=headers)
    assert response.status_code == 403
    assert "não possui aprovação humana persistida" in response.json()["detail"]

    # Verificar registro na trilha de auditoria
    audits = list_audit_events(incident_id="INC-1042")
    events = [a.event_type for a in audits]
    assert "unauthorized_ticket_creation_attempt" in events

def test_mock_ticket_blocked_for_non_ticket_actions():
    headers = {"X-Internal-Key": settings.INTERNAL_API_KEY}
    inc = get_incident("INC-1042")
    inc.status = IncidentStatus.APPROVED
    inc.approved_at = datetime.now(timezone.utc)
    # Ação recomendada é NO_ACTION, não CREATE_INTERNAL_TICKET
    inc.agent_result = AgentResult(
        incident_id=inc.id,
        summary="Nenhuma ação necessária",
        evidence=[],
        hypotheses=[],
        recommended_action=ActionType.NO_ACTION,
        priority="low",
        action_arguments={},
        operator_message="OK",
        requires_human_approval=True
    )
    save_incident(inc)

    payload = {
        "incident_id": "INC-1042",
        "priority": "low",
        "category": "inquiry",
        "description": "Tentativa indevida com ação NO_ACTION",
        "created_by_workflow_id": "WF02_test"
    }
    response = client.post("/api/internal/mock-tickets", json=payload, headers=headers)
    assert response.status_code == 400
    assert "CREATE_INTERNAL_TICKET" in response.json()["detail"]

# ------------------------------------------------------------------------------
# Ponto 4: Máquina de Estados e Supervisão Humana
# ------------------------------------------------------------------------------
def test_state_machine_cannot_approve_rejected_incident():
    # 1. Preparar proposta
    inc = get_incident("INC-1042")
    inc.status = IncidentStatus.PROPOSED
    inc.agent_result = AgentResult(
        incident_id=inc.id,
        summary="Atraso moderado",
        evidence=[],
        hypotheses=[],
        recommended_action=ActionType.CREATE_INTERNAL_TICKET,
        priority="medium",
        action_arguments={},
        operator_message="Verificar cozinha",
        requires_human_approval=True
    )
    save_incident(inc)

    # 2. Operador rejeita a proposta
    resp_reject = client.post("/api/incidents/INC-1042/decision", json={"decision": "reject", "reason": "Falso positivo"})
    assert resp_reject.status_code == 200
    assert resp_reject.json()["status"] == "rejected"

    # 3. Tentar aprovar um incidente já rejeitado deve falhar com 400
    resp_approve = client.post("/api/incidents/INC-1042/decision", json={"decision": "approve"})
    assert resp_approve.status_code == 400
    assert "rejeitado não pode ser aprovado" in resp_approve.json()["detail"]

def test_state_machine_cannot_reject_approved_incident():
    # 1. Preparar proposta e aprovar
    inc = get_incident("INC-1042")
    inc.status = IncidentStatus.PROPOSED
    inc.agent_result = AgentResult(
        incident_id=inc.id,
        summary="Atraso severo",
        evidence=[],
        hypotheses=[],
        recommended_action=ActionType.CREATE_INTERNAL_TICKET,
        priority="high",
        action_arguments={},
        operator_message="Supervisão necessária",
        requires_human_approval=True
    )
    save_incident(inc)

    resp_approve = client.post("/api/incidents/INC-1042/decision", json={"decision": "approve"})
    assert resp_approve.status_code == 200

    # 2. Tentar rejeitar um incidente já aprovado deve falhar com 400
    resp_reject = client.post("/api/incidents/INC-1042/decision", json={"decision": "reject", "reason": "Mudei de ideia"})
    assert resp_reject.status_code == 400
    assert "não pode ser rejeitado" in resp_reject.json()["detail"]

def test_state_machine_no_action_approval_creates_no_ticket():
    # 1. Preparar incidente com proposta NO_ACTION
    inc = get_incident("INC-1042")
    inc.status = IncidentStatus.PROPOSED
    inc.agent_result = AgentResult(
        incident_id=inc.id,
        summary="Operação normal dentro da tolerância",
        evidence=[],
        hypotheses=[],
        recommended_action=ActionType.NO_ACTION,
        priority="low",
        action_arguments={},
        operator_message="Nenhuma intervenção necessária.",
        requires_human_approval=True
    )
    save_incident(inc)

    # 2. Operador aprova a recomendação NO_ACTION
    resp = client.post("/api/incidents/INC-1042/decision", json={"decision": "approve"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "resolved_no_action"
    assert data["current_status"] == "executed"

    # 3. Garantir que NENHUM ticket foi criado no banco
    ticket = get_mock_ticket_by_incident("INC-1042")
    assert ticket is None

    # 4. Verificar evento de auditoria
    audits = list_audit_events(incident_id="INC-1042")
    events = [a.event_type for a in audits]
    assert "no_action_resolved" in events

def test_state_machine_customer_message_approval_creates_no_ticket():
    # 1. Preparar proposta DRAFT_CUSTOMER_MESSAGE
    inc = get_incident("INC-1042")
    inc.status = IncidentStatus.PROPOSED
    inc.agent_result = AgentResult(
        incident_id=inc.id,
        summary="Atraso leve na preparação",
        evidence=[],
        hypotheses=[],
        recommended_action=ActionType.DRAFT_CUSTOMER_MESSAGE,
        priority="medium",
        action_arguments={},
        operator_message="Olá! Seu pedido está sendo finalizado e sairá em instantes.",
        requires_human_approval=True
    )
    save_incident(inc)

    # 2. Operador aprova
    resp = client.post("/api/incidents/INC-1042/decision", json={"decision": "approve"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "executed_customer_message"

    # 3. Garantir que NENHUM ticket de suporte interno foi aberto
    ticket = get_mock_ticket_by_incident("INC-1042")
    assert ticket is None

    # 4. Verificar auditoria
    audits = list_audit_events(incident_id="INC-1042")
    events = [a.event_type for a in audits]
    assert "customer_message_dispatched" in events

# ------------------------------------------------------------------------------
# Ponto 5: Proteção de Callbacks Tardios (409 Conflict)
# ------------------------------------------------------------------------------
def test_late_callback_rejected_with_409_on_terminal_state():
    headers = {"X-Internal-Key": settings.INTERNAL_API_KEY}
    inc = get_incident("INC-1042")
    inc.status = IncidentStatus.APPROVED
    inc.analysis_job_id = "JOB-LATE-01"
    inc.approved_at = datetime.now(timezone.utc)
    save_incident(inc)

    payload = {
        "incident_id": "INC-1042",
        "job_id": "JOB-LATE-01",
        "correlation_id": "CORR-LATE-01",
        "agent_result": {
            "incident_id": "INC-1042",
            "summary": "Proposta tardia vinda do n8n",
            "evidence": [{"source": "order", "field": "status", "finding": "preparing"}],
            "hypotheses": ["Atraso"],
            "recommended_action": "CREATE_INTERNAL_TICKET",
            "priority": "high",
            "action_arguments": {},
            "operator_message": "Tardio",
            "requires_human_approval": True
        }
    }

    # Callback recebido após o incidente já ter sido aprovado
    response = client.post("/api/internal/analyses/result", json=payload, headers=headers)
    assert response.status_code == 409
    assert "já está no estado terminal" in response.json()["detail"]

    # Verificar registro de auditoria de descarte
    audits = list_audit_events(incident_id="INC-1042")
    events = [a.event_type for a in audits]
    assert "late_callback_ignored" in events

# ------------------------------------------------------------------------------
# Ponto 6: Captura de Identidade do Operador (X-Operator-Id)
# ------------------------------------------------------------------------------
def test_operator_identity_header_logged_in_audit_trail():
    operator_name = "carlos_supervisor_77"
    headers = {"X-Operator-Id": operator_name}

    # Disparar análise informando operador
    resp_analyze = client.post("/api/orders/NEX-1042/analyze", headers=headers)
    assert resp_analyze.status_code == 200

    # Verificar que o actor registrado reflete o operador
    audits = list_audit_events(incident_id="INC-1042")
    analysis_events = [a for a in audits if a.event_type == "analysis_requested"]
    assert len(analysis_events) > 0
    assert analysis_events[0].actor == f"operator:{operator_name}"

# ------------------------------------------------------------------------------
# Ponto 7: Relógio Simulado e Recálculo Determinístico
# ------------------------------------------------------------------------------
def test_advance_simulated_time_recalculates_risk_deterministically():
    initial_time = get_simulated_time()

    # Avançar 15 minutos no relógio simulado
    resp = client.post("/api/demo/advance-time", json={"minutes": 15})
    assert resp.status_code == 200
    data = resp.json()
    assert data["minutes_advanced"] == 15
    assert data["orders_updated"] > 0

    new_time = get_simulated_time()
    diff_minutes = (new_time - initial_time).total_seconds() / 60
    assert diff_minutes == 15

# ------------------------------------------------------------------------------
# Ponto 3: Ferramentas do Agente (Endpoints de Suporte a Tool Calling)
# ------------------------------------------------------------------------------
def test_internal_order_context_tool_endpoint():
    headers = {"X-Internal-Key": settings.INTERNAL_API_KEY}
    resp = client.get("/api/internal/orders/NEX-1042/context", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["order_id"] == "NEX-1042"
    assert "calculated_risk" in data
    assert "events" in data

def test_internal_policies_tool_endpoint():
    headers = {"X-Internal-Key": settings.INTERNAL_API_KEY}
    resp = client.get("/api/internal/policies", headers=headers)
    assert resp.status_code == 200
    policies = resp.json()
    assert len(policies) >= 3
    codes = [p["code"] for p in policies]
    assert "POL-DELAY-01" in codes
    assert "POL-KITCHEN-02" in codes
    assert "POL-COMM-03" in codes

# ------------------------------------------------------------------------------
# Métricas do Piloto (Seção 8 do PRD)
# ------------------------------------------------------------------------------
def test_metrics_endpoint():
    resp = client.get("/api/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "simulated_time" in data
    assert "total_orders" in data
    assert "total_incidents" in data
    assert "incidents_by_status" in data
    assert data["total_orders"] >= 40
