from secrets import compare_digest

from fastapi import APIRouter, HTTPException, Header, Depends, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Literal
from datetime import datetime, timezone
from backend.app.config import INSECURE_DEFAULT_SECRETS, settings
from backend.app.models import (
    Incident, IncidentStatus, AgentResult, MockTicket,
    ActionType, AuditEvent
)
from backend.app.repositories import (
    get_incident, save_incident, get_order, get_order_events,
    get_policy, list_policies, record_audit_event,
    create_mock_ticket, atomic_create_mock_ticket, get_mock_ticket_by_incident,
    atomic_apply_analysis_proposal, atomic_apply_action_result
)

router = APIRouter(prefix="/api/internal", tags=["Internal Service APIs"])

def verify_internal_secret(
    x_internal_key: Optional[str] = Header(None, alias="X-Internal-Key"),
    authorization: Optional[str] = Header(None),
):
    """
    Garante autenticação obrigatória e segura entre serviços (API <-> n8n).
    Bloqueia estritamente segredos padrão e exige chave com entropia (Fix Prioridade 5).
    """
    token = x_internal_key
    if not token and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticação interna obrigatória. Chave de serviço X-Internal-Key não fornecida."
        )

    # Rejeição de chave padrão fraca
    if token in INSECURE_DEFAULT_SECRETS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chave interna padrão insegura rejeitada. Configure uma chave segura no .env."
        )

    if settings.INTERNAL_API_KEY in INSECURE_DEFAULT_SECRETS:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Configuração de servidor insegura: defina uma INTERNAL_API_KEY válida e segura no arquivo .env."
        )

    if not compare_digest(token.encode("utf-8"), settings.INTERNAL_API_KEY.encode("utf-8")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chave de serviço interna incorreta."
        )
    return True

# ------------------------------------------------------------------------------
# Schemas de Entrada / Saída das rotas internas
# ------------------------------------------------------------------------------

class AnalysisResultPayload(BaseModel):
    incident_id: str
    job_id: str = Field(min_length=1)
    correlation_id: Optional[str] = None
    agent_result: AgentResult

class MockTicketCreatePayload(BaseModel):
    incident_id: str
    priority: str
    category: str
    description: str
    created_by_workflow_id: str

class ActionResultPayload(BaseModel):
    incident_id: str
    status: Literal["executed", "failed"]
    workflow_execution_id: Optional[str] = None
    error_message: Optional[str] = None
    correlation_id: Optional[str] = None

# ------------------------------------------------------------------------------
# 1. GET /api/internal/incidents/{id}/context & GET /api/internal/orders/{id}/context
# ------------------------------------------------------------------------------
@router.get("/incidents/{incident_id}/context", dependencies=[Depends(verify_internal_secret)])
def get_incident_context(incident_id: str):
    """
    Retorna o contexto completo do incidente e pedido para ser consumido pelo agente Gemini no n8n.
    """
    incident = get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incidente {incident_id} não encontrado.")

    order = get_order(incident.order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Pedido {incident.order_id} associado não encontrado.")

    events = get_order_events(order.id)
    policies = list_policies()

    return {
        "incident_id": incident.id,
        "order_id": order.id,
        "risk_score": incident.risk_score,
        "risk_level": incident.risk_level.value,
        "risk_signals": incident.risk_signals,
        "order": {
            "id": order.id,
            "restaurant_name": order.restaurant_name,
            "status": order.status.value,
            "created_at": order.created_at.isoformat(),
            "promised_at": order.promised_at.isoformat(),
            "courier_assigned": order.courier_assigned,
            "last_status_update_at": order.last_status_update_at.isoformat(),
            "restaurant_backlog": order.restaurant_backlog,
            "estimated_prep_minutes_remaining": order.estimated_prep_minutes_remaining,
            "distance_km": order.distance_km,
            "items": [it.model_dump() for it in order.items],
            "customer_notes": order.customer_notes
        },
        "order_events": [ev.model_dump() for ev in events],
        "available_policy_codes": [p.code for p in policies]
    }

@router.get("/orders/{order_id}/context", dependencies=[Depends(verify_internal_secret)])
def get_order_context_for_tool(order_id: str):
    """
    Endpoint consumido diretamente pela ferramenta get_order_context do AI Agent via HTTP Request Tool.
    """
    order = get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Pedido {order_id} não encontrado.")

    events = get_order_events(order.id)
    from backend.app.repositories import get_incident_by_order, get_simulated_time
    from backend.app.risk_engine import evaluate_order_risk
    incident = get_incident_by_order(order.id)
    simulated_now = get_simulated_time()
    risk = evaluate_order_risk(order, evaluation_time=simulated_now)

    return {
        "order_id": order.id,
        "incident_id": incident.id if incident else None,
        "restaurant_name": order.restaurant_name,
        "status": order.status.value,
        "promised_at": order.promised_at.isoformat(),
        "courier_assigned": order.courier_assigned,
        "restaurant_backlog": order.restaurant_backlog,
        "estimated_prep_minutes_remaining": order.estimated_prep_minutes_remaining,
        "distance_km": order.distance_km,
        "customer_notes": order.customer_notes,
        "items": [it.model_dump() for it in order.items],
        "events": [ev.model_dump() for ev in events],
        "calculated_risk": risk.to_dict()
    }

# ------------------------------------------------------------------------------
# 2. GET /api/internal/policies & GET /api/internal/policies/{code}
# ------------------------------------------------------------------------------
@router.get("/policies", dependencies=[Depends(verify_internal_secret)])
def get_all_policies_internal(category: Optional[str] = None):
    """
    Retorna a lista completa ou filtrada de políticas para a ferramenta get_operations_policy do agente Gemini.
    """
    policies = list_policies()
    if category and category.lower() != "all":
        filtered = [p for p in policies if p.category.lower() == category.lower()]
        if filtered:
            return [p.model_dump() for p in filtered]
    return [p.model_dump() for p in policies]

@router.get("/policies/{code}", dependencies=[Depends(verify_internal_secret)])
def get_policy_by_code(code: str):
    """
    Permite que o agente consulte uma política específica por meio de Tool Calling.
    """
    policy = get_policy(code)
    if not policy:
        raise HTTPException(status_code=404, detail=f"Política com código {code} não encontrada.")
    return policy.model_dump()

# ------------------------------------------------------------------------------
# 3. POST /api/internal/analyses/result
# ------------------------------------------------------------------------------
@router.post("/analyses/result", dependencies=[Depends(verify_internal_secret)])
def receive_analysis_result(payload: AnalysisResultPayload):
    """
    Callback chamado pelo workflow n8n WF01 com a recomendação estruturada do Gemini.
    Atualiza o incidente para status 'proposed' por meio de transição atômica condicional.
    Protegido contra sobrescrita de estados terminais e callbacks com job_id divergente (Fix Prioridades 2 e 5).
    """
    # 1. Validar que a ação recomendada é permitida
    allowed_actions = {a.value for a in ActionType}
    if payload.agent_result.recommended_action.value not in allowed_actions:
        raise HTTPException(
            status_code=400,
            detail=f"Ação recomendada inválida: {payload.agent_result.recommended_action}. Permitidas: {allowed_actions}"
        )

    payload.agent_result.execution_source = "n8n_workflow"

    # 3. Atualização condicional atômica no banco
    success, incident, message = atomic_apply_analysis_proposal(
        incident_id=payload.incident_id,
        job_id=payload.job_id,
        correlation_id=payload.correlation_id,
        agent_result=payload.agent_result
    )

    if not success:
        if message == "not_found":
            raise HTTPException(status_code=404, detail=f"Incidente {payload.incident_id} não encontrado.")

        record_audit_event(
            actor="system",
            event_type="late_callback_ignored",
            incident_id=payload.incident_id,
            payload={
                "detail": message,
                "attempted_action": payload.agent_result.recommended_action.value,
                "job_id": payload.job_id
            },
            correlation_id=payload.correlation_id
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=message
        )

    record_audit_event(
        actor="agent",
        event_type="analysis_completed",
        incident_id=incident.id,
        payload={
            "action": payload.agent_result.recommended_action.value,
            "summary": payload.agent_result.summary,
            "evidence_count": len(payload.agent_result.evidence),
            "priority": payload.agent_result.priority,
            "model_used": payload.agent_result.model_used,
            "execution_source": payload.agent_result.execution_source
        },
        correlation_id=payload.correlation_id
    )

    return {"status": "success", "incident_id": incident.id, "current_status": incident.status.value}

# ------------------------------------------------------------------------------
# 4. GET /api/internal/actions/{incident_id}/authorization
# ------------------------------------------------------------------------------
@router.get("/actions/{incident_id}/authorization", dependencies=[Depends(verify_internal_secret)])
def check_action_authorization(incident_id: str):
    """
    Verifica se a ação recomendada foi de fato aprovada por um operador humano antes do n8n executar.
    """
    incident = get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incidente não encontrado.")

    result = incident.agent_result
    is_approved = (
        incident.status in (IncidentStatus.APPROVED, IncidentStatus.EXECUTING)
        and incident.approved_at is not None
        and result is not None
        and result.recommended_action == ActionType.CREATE_INTERNAL_TICKET
    )
    return {
        "incident_id": incident.id,
        "is_authorized": is_approved,
        "status": incident.status.value,
        "approved_at": incident.approved_at.isoformat() if incident.approved_at else None,
        "recommended_action": result.recommended_action.value if result else None,
        "priority": result.priority if is_approved else None,
        "category": (result.action_arguments.get("category") or "late_delivery") if is_approved else None,
    }

# ------------------------------------------------------------------------------
# 5. POST /api/internal/mock-tickets (Idempotente & Protegido por Autorização)
# ------------------------------------------------------------------------------
@router.post("/mock-tickets", dependencies=[Depends(verify_internal_secret)])
def create_internal_ticket(payload: MockTicketCreatePayload):
    """
    Cria um ticket fictício de forma estritamente idempotente e atômica.
    Exige aprovação persistida do operador humano (Fix Ponto 1).
    """
    incident = get_incident(payload.incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incidente não encontrado.")

    # 1. BLOQUEIO DE CRIAÇÃO SEM APROVAÇÃO PERSISTIDA (Fix Ponto 1)
    if incident.status not in (IncidentStatus.APPROVED, IncidentStatus.EXECUTING) or not incident.approved_at:
        record_audit_event(
            actor="system",
            event_type="unauthorized_ticket_creation_attempt",
            incident_id=payload.incident_id,
            payload={
                "attempted_by": payload.created_by_workflow_id,
                "current_status": incident.status.value
            }
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Ação não autorizada. O incidente {payload.incident_id} possui status '{incident.status.value}' e não possui aprovação humana persistida."
        )

    # 2. Validação de ação permitida para geração de tickets
    if not incident.agent_result or incident.agent_result.recommended_action != ActionType.CREATE_INTERNAL_TICKET:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é permitido criar ticket interno para incidentes sem recomendação de ação CREATE_INTERNAL_TICKET."
        )

    # 3. Criação atômica e idempotente no banco com proteção de concorrência
    ticket_id = f"TCK-{payload.incident_id.replace('INC-', '')}"
    new_ticket = MockTicket(
        id=ticket_id,
        incident_id=payload.incident_id,
        priority=payload.priority,
        category=payload.category,
        description=payload.description,
        created_at=datetime.now(timezone.utc),
        created_by_workflow_id=payload.created_by_workflow_id
    )
    created, saved = atomic_create_mock_ticket(new_ticket)

    if not created:
        return {
            "status": "already_exists",
            "ticket": saved.model_dump(),
            "message": "Ticket já havia sido criado anteriormente para este incidente."
        }

    record_audit_event(
        actor="system",
        event_type="ticket_created",
        incident_id=payload.incident_id,
        payload={"ticket_id": ticket_id, "priority": payload.priority, "category": payload.category}
    )

    return {"status": "created", "ticket": saved.model_dump()}

# ------------------------------------------------------------------------------
# 6. POST /api/internal/actions/result
# ------------------------------------------------------------------------------
@router.post("/actions/result", dependencies=[Depends(verify_internal_secret)])
def record_action_result(payload: ActionResultPayload):
    """
    Workflow n8n WF02 notifica a conclusão da execução.
    Atualiza status do incidente para 'executed' ou 'failed' com validação estrita (Fix Prioridade 3).
    Exige aprovação humana prévia e, para CREATE_INTERNAL_TICKET, comprovação de criação do ticket no SQLite.
    """
    success, incident, message = atomic_apply_action_result(
        incident_id=payload.incident_id,
        status_update=payload.status,
        workflow_execution_id=payload.workflow_execution_id,
        error_message=payload.error_message
    )

    if not success:
        if message == "not_found":
            raise HTTPException(status_code=404, detail=f"Incidente {payload.incident_id} não encontrado.")
        if message.startswith("unauthorized"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Ação não autorizada: o incidente {payload.incident_id} não possui aprovação humana persistida."
            )
        if message.startswith("unproven_execution"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Execução não comprovada: o ticket interno para o incidente {payload.incident_id} não foi criado no banco de dados."
            )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)

    record_audit_event(
        actor="system",
        event_type="action_executed" if payload.status == "executed" else "action_failed",
        incident_id=incident.id,
        payload={
            "status": payload.status,
            "workflow_execution_id": payload.workflow_execution_id,
            "error_message": payload.error_message,
            "is_simulated": False
        },
        correlation_id=payload.correlation_id
    )

    return {"status": "success", "incident_id": incident.id, "current_status": incident.status.value}
