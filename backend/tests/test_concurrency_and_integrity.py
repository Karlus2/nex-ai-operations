import pytest
import httpx
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import partial
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.config import settings
from backend.app.database import get_connection
from backend.app.seed import seed_database
from backend.app.models import IncidentStatus, AgentResult, ActionType
from backend.app.routes import public
from backend.app.repositories import (
    get_incident, save_incident, get_mock_ticket_by_incident,
    list_audit_events
)

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_clean_db():
    seed_database(drop_existing=True)


@pytest.mark.parametrize(
    ("failure", "require_n8n", "pending"),
    [
        (httpx.ConnectError, True, False),
        (httpx.ReadTimeout, True, True),
        (httpx.ReadTimeout, False, True),
    ],
)
def test_n8n_dispatch_failure_does_not_run_fallbacks(monkeypatch, failure, require_n8n, pending):
    def fail_request(request):
        raise failure("Falha no envio ao n8n", request=request)

    async def unexpected_fallback(*args):
        pytest.fail("O Gemini direto não deveria ser chamado")

    transport = httpx.MockTransport(fail_request)
    monkeypatch.setattr(public.httpx, "AsyncClient", partial(httpx.AsyncClient, transport=transport))
    monkeypatch.setattr(settings, "REQUIRE_N8N", require_n8n)
    monkeypatch.setattr(public, "run_gemini_triage", unexpected_fallback)

    assert client.post("/api/orders/NEX-1042/analyze").status_code == 200
    incident = get_incident("INC-1042")
    assert incident.status == (IncidentStatus.ANALYZING if pending else IncidentStatus.FAILED)
    assert ("confirmação pendente" if pending else "conectar") in incident.error_message

    result = AgentResult(
        incident_id=incident.id,
        summary="Ocorrência de preparo",
        recommended_action=ActionType.CREATE_INTERNAL_TICKET,
        priority="medium",
        action_arguments={"category": "restaurant_backlog"},
        operator_message="Abrir chamado após aprovação",
    )
    headers = {"X-Internal-Key": settings.INTERNAL_API_KEY}
    if pending:
        callback = client.post("/api/internal/analyses/result", headers=headers, json={
            "incident_id": incident.id, "job_id": incident.analysis_job_id,
            "agent_result": result.model_dump(mode="json"),
        })
        assert callback.status_code == 200
        assert get_incident(incident.id).error_message is None
    else:
        incident.status = IncidentStatus.PROPOSED
        incident.agent_result = result
        save_incident(incident)

    decision = client.post(f"/api/incidents/{incident.id}/decision", json={"decision": "approve"})
    assert decision.status_code == 200
    current = get_incident(incident.id)
    assert current.status == (IncidentStatus.APPROVED if pending else IncidentStatus.FAILED)
    assert ("confirmação pendente" if pending else "conectar") in current.error_message
    assert get_mock_ticket_by_incident(incident.id) is None
    assert client.post("/api/orders/NEX-1042/analyze").status_code == 409

    if pending:
        auth = client.get(f"/api/internal/actions/{incident.id}/authorization", headers=headers).json()
        assert (auth["is_authorized"], auth["priority"], auth["category"]) == (True, "medium", "restaurant_backlog")
        ticket = {
            "incident_id": incident.id, "priority": auth["priority"], "category": auth["category"],
            "description": "Chamado de preparo", "created_by_workflow_id": "WF02_n8n_executor",
        }
        assert client.post("/api/internal/mock-tickets", json=ticket, headers=headers).status_code == 200
        callback = client.post("/api/internal/actions/result", headers=headers, json={
            "incident_id": incident.id, "status": "executed",
        })
        assert callback.status_code == 200
        assert get_incident(incident.id).error_message is None

# ------------------------------------------------------------------------------
# 1. Testes de Concorrência: Decisão Humana Simultânea
# ------------------------------------------------------------------------------
def test_concurrent_approvals_race_condition():
    # Preparar INC-1042 como 'proposed'
    inc = get_incident("INC-1042")
    inc.status = IncidentStatus.PROPOSED
    inc.agent_result = AgentResult(
        incident_id=inc.id,
        summary="Atraso severo na cozinha",
        evidence=[],
        hypotheses=[],
        recommended_action=ActionType.CREATE_INTERNAL_TICKET,
        priority="high",
        action_arguments={"category": "late_delivery"},
        operator_message="Supervisão necessária",
        requires_human_approval=True
    )
    save_incident(inc)

    def send_approval(_):
        local_client = TestClient(app)
        return local_client.post("/api/incidents/INC-1042/decision", json={"decision": "approve"})

    # Disparar 5 aprovações concorrentes
    with ThreadPoolExecutor(max_workers=5) as executor:
        responses = list(executor.map(send_approval, range(5)))

    status_codes = [r.status_code for r in responses]
    assert all(code == 200 for code in status_codes)

    results = [r.json()["status"] for r in responses]
    assert results.count("approved") == 1
    assert results.count("already_approved") == 4

# ------------------------------------------------------------------------------
# 2. Testes de Concorrência: Criação de Mock Ticket Idempotente
# ------------------------------------------------------------------------------
def test_concurrent_ticket_creation_idempotency():
    inc = get_incident("INC-1042")
    inc.status = IncidentStatus.APPROVED
    inc.approved_at = datetime.now(timezone.utc)
    inc.agent_result = AgentResult(
        incident_id=inc.id,
        summary="Atraso severo",
        evidence=[],
        hypotheses=[],
        recommended_action=ActionType.CREATE_INTERNAL_TICKET,
        priority="high",
        action_arguments={"category": "late_delivery"},
        operator_message="Supervisão aprovada",
        requires_human_approval=True
    )
    save_incident(inc)

    headers = {"X-Internal-Key": settings.INTERNAL_API_KEY}
    payload = {
        "incident_id": "INC-1042",
        "priority": "high",
        "category": "late_delivery",
        "description": "Ticket sob estresse de concorrência",
        "created_by_workflow_id": "WF02_concurrency_test"
    }

    def send_ticket_req(_):
        local_client = TestClient(app)
        return local_client.post("/api/internal/mock-tickets", json=payload, headers=headers)

    # Disparar 5 requisições simultâneas de criação de ticket
    with ThreadPoolExecutor(max_workers=5) as executor:
        responses = list(executor.map(send_ticket_req, range(5)))

    status_codes = [r.status_code for r in responses]
    assert all(code == 200 for code in status_codes)

    results = [r.json()["status"] for r in responses]
    assert results.count("created") == 1
    assert results.count("already_exists") == 4

# ------------------------------------------------------------------------------
# 3. Callbacks Antigos / Job Divergente Rejeitados
# ------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("job_fields", "expected_status"),
    [
        ({}, 422),
        ({"job_id": None}, 422),
        ({"job_id": ""}, 422),
        ({"job_id": "JOB-OLD-STALE-11"}, 409),
        ({"job_id": "JOB-CURRENT-ACTIVE-99"}, 200),
    ],
)
def test_analysis_callback_requires_active_job(job_fields, expected_status):
    headers = {"X-Internal-Key": settings.INTERNAL_API_KEY}
    inc = get_incident("INC-1042")
    inc.status = IncidentStatus.ANALYZING
    inc.analysis_job_id = "JOB-CURRENT-ACTIVE-99"
    save_incident(inc)

    payload = {
        "incident_id": "INC-1042",
        **job_fields,
        "correlation_id": "CORR-OLD",
        "agent_result": {
            "incident_id": "INC-1042",
            "summary": "Proposta vinda de job antigo atrasado",
            "evidence": [],
            "hypotheses": [],
            "recommended_action": "NO_ACTION",
            "priority": "low",
            "action_arguments": {},
            "operator_message": "Old",
            "requires_human_approval": True
        }
    }

    response = client.post("/api/internal/analyses/result", json=payload, headers=headers)
    assert response.status_code == expected_status

    current = get_incident("INC-1042")
    assert current.analysis_job_id == "JOB-CURRENT-ACTIVE-99"
    if expected_status == 200:
        assert current.status == IncidentStatus.PROPOSED
        assert current.agent_result == AgentResult.model_validate(payload["agent_result"])
    else:
        assert current.status == IncidentStatus.ANALYZING
        assert current.agent_result == inc.agent_result


@pytest.mark.parametrize("stored_recommendation", [None, "{}", '{"recommended_action":"UNKNOWN"}'])
def test_approval_requires_valid_stored_recommendation(stored_recommendation):
    inc = get_incident("INC-1042")
    inc.status = IncidentStatus.PROPOSED
    inc.agent_result = None
    save_incident(inc)

    conn = get_connection()
    try:
        conn.execute(
            "UPDATE incidents SET agent_result_json = ? WHERE id = ?",
            (stored_recommendation, inc.id),
        )
        conn.commit()

        response = client.post(f"/api/incidents/{inc.id}/decision", json={"decision": "approve"})
        assert response.status_code == 400

        current = conn.execute(
            "SELECT status, approved_at, executed_at, agent_result_json FROM incidents WHERE id = ?",
            (inc.id,),
        ).fetchone()
        assert tuple(current) == ("proposed", None, None, stored_recommendation)
        assert get_mock_ticket_by_incident(inc.id) is None
    finally:
        conn.close()

# ------------------------------------------------------------------------------
# 4. Bloqueio de Reanálise em Estados Terminais
# ------------------------------------------------------------------------------
def test_reanalyze_blocked_on_terminal_states():
    # 4.1. Incidentes aprovados não podem ser reanalisados
    inc = get_incident("INC-1042")
    inc.status = IncidentStatus.APPROVED
    inc.approved_at = datetime.now(timezone.utc)
    save_incident(inc)

    resp_app = client.post("/api/orders/NEX-1042/analyze")
    assert resp_app.status_code == 409
    assert "Reanálise não permitida" in resp_app.json()["detail"]

    # 4.2. Incidentes rejeitados não podem ser reanalisados
    inc.status = IncidentStatus.REJECTED
    save_incident(inc)
    resp_rej = client.post("/api/orders/NEX-1042/analyze")
    assert resp_rej.status_code == 409
    assert "Reanálise não permitida" in resp_rej.json()["detail"]

    # 4.3. Incidentes executados não podem ser reanalisados
    inc.status = IncidentStatus.EXECUTED
    inc.executed_at = datetime.now(timezone.utc)
    save_incident(inc)
    resp_exec = client.post("/api/orders/NEX-1042/analyze")
    assert resp_exec.status_code == 409
    assert "Reanálise não permitida" in resp_exec.json()["detail"]

# ------------------------------------------------------------------------------
# 5. Comprovação Obrigatória de Execução em /actions/result
# ------------------------------------------------------------------------------
def test_action_result_requires_proof_of_ticket():
    headers = {"X-Internal-Key": settings.INTERNAL_API_KEY}
    inc = get_incident("INC-1042")
    inc.status = IncidentStatus.APPROVED
    inc.approved_at = datetime.now(timezone.utc)
    inc.agent_result = AgentResult(
        incident_id=inc.id,
        summary="Atraso severo",
        evidence=[],
        hypotheses=[],
        recommended_action=ActionType.CREATE_INTERNAL_TICKET,
        priority="high",
        action_arguments={"category": "late_delivery"},
        operator_message="Supervisão aprovada",
        requires_human_approval=True
    )
    save_incident(inc)

    # Tentar reportar 'executed' ANTES do ticket ter sido criado na tabela mock_tickets
    payload = {
        "incident_id": "INC-1042",
        "status": "executed",
        "workflow_execution_id": "EXEC-FAKE-01"
    }
    resp = client.post("/api/internal/actions/result", json=payload, headers=headers)
    assert resp.status_code == 422
    assert "Execução não comprovada" in resp.json()["detail"]

    # Criar o ticket de forma legítima
    ticket_payload = {
        "incident_id": "INC-1042",
        "priority": "high",
        "category": "late_delivery",
        "description": "Ticket comprovado",
        "created_by_workflow_id": "WF02"
    }
    resp_tck = client.post("/api/internal/mock-tickets", json=ticket_payload, headers=headers)
    assert resp_tck.status_code == 200

    # Agora a chamada a /actions/result deve suceder comprovando o ticket
    resp_ok = client.post("/api/internal/actions/result", json=payload, headers=headers)
    assert resp_ok.status_code == 200
    assert resp_ok.json()["current_status"] == "executed"

def test_action_result_blocked_without_human_approval():
    headers = {"X-Internal-Key": settings.INTERNAL_API_KEY}
    # INC-1042 no seed está em 'detected' sem aprovação
    payload = {
        "incident_id": "INC-1042",
        "status": "executed"
    }
    resp = client.post("/api/internal/actions/result", json=payload, headers=headers)
    assert resp.status_code == 403
    assert "não possui aprovação humana persistida" in resp.json()["detail"]

# ------------------------------------------------------------------------------
# 6. Rejeição de Segredo Fraco Padrão
# ------------------------------------------------------------------------------
def test_insecure_default_secret_rejected():
    headers = {"X-Internal-Key": "nex_internal_dev_secret_replace_in_prod"}
    resp = client.get("/api/internal/policies", headers=headers)
    assert resp.status_code == 401
    assert "padrão insegura rejeitada" in resp.json()["detail"]

# ------------------------------------------------------------------------------
# 7. Sanitização de Operador e Distinção de Ações Simuladas
# ------------------------------------------------------------------------------
def test_operator_attribution_sanitization_and_injection_defense():
    # Injeção maliciosa no header
    headers = {"X-Operator-Id": "<script>alert(1)</script>"}
    resp = client.post("/api/orders/NEX-1042/analyze", headers=headers)
    assert resp.status_code == 200

    audits = list_audit_events(incident_id="INC-1042")
    evt = next(a for a in audits if a.event_type == "analysis_requested")
    # Deve fazer fallback seguro para operator:default
    assert evt.actor == "operator:default"

def test_audit_event_distinguishes_simulated_from_executed():
    inc = get_incident("INC-1042")
    inc.status = IncidentStatus.PROPOSED
    inc.agent_result = AgentResult(
        incident_id=inc.id,
        summary="Atraso leve",
        evidence=[],
        hypotheses=[],
        recommended_action=ActionType.DRAFT_CUSTOMER_MESSAGE,
        priority="medium",
        action_arguments={},
        operator_message="Seu pedido está quase pronto!",
        requires_human_approval=True
    )
    save_incident(inc)

    resp = client.post("/api/incidents/INC-1042/decision", json={"decision": "approve"})
    assert resp.status_code == 200
    assert resp.json()["is_simulated"] is True

    audits = list_audit_events(incident_id="INC-1042")
    msg_event = next(a for a in audits if a.event_type == "customer_message_dispatched")
    assert msg_event.payload_redacted.get("is_simulated") is True
    assert msg_event.payload_redacted.get("action_nature") == "simulated"

