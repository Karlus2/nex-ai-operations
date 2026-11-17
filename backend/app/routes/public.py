import httpx
import uuid
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Header, status
from pydantic import BaseModel

OPERATOR_SLUG_REGEX = re.compile(r"^[a-zA-Z0-9_\-\.]{2,50}$")

def sanitize_operator_attribution(raw_operator_id: Optional[str]) -> str:
    """
    Higieniza a atribuição do perfil de operador local demonstrativo.
    AVISO DE SEGURANÇA (Prioridade 4): X-Operator-Id é puramente um metadado de rastreabilidade
    para a interface demonstrativa local, NÃO consistindo em autenticação criptográfica.
    """
    if not raw_operator_id:
        return "operator:default"
    clean_id = raw_operator_id.strip()
    if not OPERATOR_SLUG_REGEX.match(clean_id):
        return "operator:default"
    return f"operator:{clean_id}"

from backend.app.config import settings
from backend.app.models import (
    Order, OrderStatus, Incident, IncidentStatus, RiskLevel,
    ActionType, MockTicket, AuditEvent
)
from backend.app.repositories import (
    get_order, list_orders, get_order_events,
    get_incident, get_incident_by_order, list_incidents,
    record_audit_event, list_audit_events,
    get_mock_ticket_by_incident, create_mock_ticket, get_summary, list_policies,
    get_simulated_time, advance_simulated_time, atomic_initiate_analysis,
    atomic_apply_action_result, atomic_apply_analysis_proposal,
    atomic_record_analysis_dispatch_issue, atomic_record_human_decision
)
from backend.app.risk_engine import evaluate_order_risk
from backend.app.seed import seed_database
from backend.app.services.agent_service import run_gemini_triage

router = APIRouter(prefix="/api", tags=["Public Operator APIs"])

# ------------------------------------------------------------------------------
# Schemas
# ------------------------------------------------------------------------------
class DecisionPayload(BaseModel):
    decision: str  # "approve" ou "reject"
    reason: Optional[str] = None

class AdvanceTimePayload(BaseModel):
    minutes: int = 5

# ------------------------------------------------------------------------------
# 1. KPIs / Summary
# ------------------------------------------------------------------------------
@router.get("/summary")
def get_dashboard_summary():
    """Retorna os 4 KPIs essenciais para o topo da visão geral."""
    return get_summary()

@router.get("/metrics")
def get_system_metrics():
    """Retorna estatísticas da demonstração conforme especificação (Seção 8)."""
    simulated_now = get_simulated_time()
    summary = get_summary()
    orders = list_orders()
    incidents = list_incidents()
    audit_events = list_audit_events(limit=200)

    status_counts = {}
    for inc in incidents:
        status_counts[inc.status.value] = status_counts.get(inc.status.value, 0) + 1

    return {
        "simulated_time": simulated_now.isoformat(),
        "summary": summary,
        "total_orders": len(orders),
        "total_incidents": len(incidents),
        "incidents_by_status": status_counts,
        "total_audit_events": len(audit_events)
    }

# ------------------------------------------------------------------------------
# 2. Orders
# ------------------------------------------------------------------------------
@router.get("/orders")
def get_orders(
    status: Optional[str] = Query(None, description="Filtrar por status do pedido"),
    risk: Optional[str] = Query(None, description="Filtrar por nível de risco: low, medium, high"),
    search: Optional[str] = Query(None, description="Buscar por ID ou nome do restaurante")
):
    """Lista pedidos sintéticos com score, nível de risco e filtros operacionais."""
    return list_orders(status=status, risk=risk, search=search)

@router.get("/orders/{order_id}")
def get_order_detail(order_id: str):
    """Retorna o detalhe de um pedido, seus eventos na timeline e o incidente associado."""
    order = get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Pedido {order_id} não encontrado.")

    events = get_order_events(order_id)
    incident = get_incident_by_order(order_id)
    simulated_now = get_simulated_time()
    risk_info = evaluate_order_risk(order, evaluation_time=simulated_now)

    ticket = None
    if incident:
        ticket = get_mock_ticket_by_incident(incident.id)

    return {
        "order": order.model_dump(),
        "events": [e.model_dump() for e in events],
        "calculated_risk": risk_info.to_dict(),
        "incident": incident.model_dump() if incident else None,
        "mock_ticket": ticket.model_dump() if ticket else None
    }

# ------------------------------------------------------------------------------
# 3. Incidents
# ------------------------------------------------------------------------------
@router.get("/incidents")
def get_incidents(status: Optional[str] = Query(None, description="Filtrar por status do incidente")):
    """Lista ocorrências registradas com status e recomendação do agente."""
    incidents = list_incidents(status=status)
    return [inc.model_dump() for inc in incidents]

@router.get("/incidents/{incident_id}")
def get_incident_detail(incident_id: str):
    """Retorna o detalhe do incidente, histórico de auditoria e ticket gerado se houver."""
    incident = get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incidente {incident_id} não encontrado.")

    order = get_order(incident.order_id)
    audit_events = list_audit_events(incident_id=incident.id)
    ticket = get_mock_ticket_by_incident(incident.id)

    return {
        "incident": incident.model_dump(),
        "order": order.model_dump() if order else None,
        "audit_events": [a.model_dump() for a in audit_events],
        "mock_ticket": ticket.model_dump() if ticket else None
    }

# ------------------------------------------------------------------------------
# 4. Trigger de Análise com IA (Assíncrono via n8n)
# ------------------------------------------------------------------------------
async def _send_n8n_webhook(url: str, payload: dict, timeout: float) -> tuple[str, Optional[int]]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload, headers={"X-Internal-Key": settings.INTERNAL_API_KEY})
    except (httpx.ConnectError, httpx.ConnectTimeout):
        return "unavailable", None
    except httpx.RequestError:
        return "unconfirmed", None

    code = response.status_code
    if 200 <= code < 300:
        return "accepted", code
    if 300 <= code < 500 and code != 408:
        return "rejected", code
    return "unconfirmed", code


async def _trigger_n8n_triage(incident_id: str, order_id: str, job_id: str, correlation_id: str):
    payload = {
        "incident_id": incident_id,
        "order_id": order_id,
        "job_id": job_id,
        "correlation_id": correlation_id
    }
    dispatch, code = await _send_n8n_webhook(settings.N8N_WEBHOOK_TRIAGE_URL, payload, timeout=3.0)
    if dispatch == "accepted":
        record_audit_event(
            actor="system", event_type="triage_dispatched_to_n8n", incident_id=incident_id,
            payload={"status_code": code, "job_id": job_id}, correlation_id=correlation_id
        )
        return

    if settings.REQUIRE_N8N or dispatch != "unavailable":
        pending = dispatch == "unconfirmed"
        if pending:
            message = "WF01: confirmação pendente. O n8n pode ter recebido a triagem."
        elif code is not None:
            message = f"WF01: o webhook recusou a triagem (HTTP {code})."
        else:
            message = "WF01: não foi possível conectar ao n8n."
        if atomic_record_analysis_dispatch_issue(incident_id, job_id, message, pending=pending):
            record_audit_event(
                actor="system",
                event_type="analysis_confirmation_pending" if pending else "analysis_failed",
                incident_id=incident_id, payload={"detail": message, "job_id": job_id},
                correlation_id=correlation_id
            )
        return

    incident = get_incident(incident_id)
    if not incident or incident.status != IncidentStatus.ANALYZING or incident.analysis_job_id != job_id:
        return

    try:
        order = get_order(order_id)
        events = get_order_events(order_id)
        if not order:
            return

        context = {
            "incident_id": incident_id,
            "order_id": order.id,
            "risk_score": incident.risk_score,
            "risk_level": incident.risk_level.value,
            "risk_signals": incident.risk_signals,
            "order": order.model_dump(mode="json"),
            "order_events": [ev.model_dump(mode="json") for ev in events]
        }

        agent_result = await run_gemini_triage(incident_id, context)

        # Atualização atômica condicional protegida contra concorrência
        success, updated_inc, msg = atomic_apply_analysis_proposal(
            incident_id=incident_id,
            job_id=job_id,
            correlation_id=correlation_id,
            agent_result=agent_result
        )

        if success and updated_inc:
            record_audit_event(
                actor="agent:gemini_fallback",
                event_type="analysis_completed",
                incident_id=updated_inc.id,
                payload={
                    "action": agent_result.recommended_action.value,
                    "summary": agent_result.summary,
                    "evidence_count": len(agent_result.evidence),
                    "priority": agent_result.priority,
                    "model_used": agent_result.model_used,
                    "execution_source": agent_result.execution_source,
                    "latency_ms": agent_result.latency_ms
                },
                correlation_id=correlation_id
            )
    except Exception as exc:
        if atomic_record_analysis_dispatch_issue(incident_id, job_id, f"Falha na análise com IA ({exc})"):
            record_audit_event(
                actor="system",
                event_type="analysis_failed",
                incident_id=incident_id,
                payload={"error": str(exc)},
                correlation_id=correlation_id
            )

@router.post("/orders/{order_id}/analyze")
async def analyze_order_with_ai(
    order_id: str,
    background_tasks: BackgroundTasks,
    operator_id: Optional[str] = Header(None, alias="X-Operator-Id")
):
    """
    Inicia o job de análise com IA para um pedido.
    Transiciona status para 'analyzing' e dispara o workflow WF01 do n8n de forma assíncrona.
    Identifica o operador responsável via header X-Operator-Id (Fix Ponto 6).
    """
    order = get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Pedido {order_id} não encontrado.")

    simulated_now = get_simulated_time()
    risk_info = evaluate_order_risk(order, evaluation_time=simulated_now)
    new_job_id = f"JOB-{uuid.uuid4().hex[:8].upper()}"

    # Transição atômica condicional: bloqueia reanálise se já estiver em estado terminal (Fix Prioridade 2)
    success, incident, message = atomic_initiate_analysis(
        order_id=order_id,
        new_job_id=new_job_id,
        risk_score=risk_info.score,
        risk_level=risk_info.level,
        risk_signals=risk_info.signals
    )

    if not success or not incident:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=message
        )

    actor = sanitize_operator_attribution(operator_id)
    correlation_id = f"CORR-{uuid.uuid4().hex[:8]}"
    record_audit_event(
        actor=actor,
        event_type="analysis_requested",
        incident_id=incident.id,
        payload={"job_id": new_job_id, "score": incident.risk_score},
        correlation_id=correlation_id
    )

    # Disparar n8n em background
    background_tasks.add_task(_trigger_n8n_triage, incident.id, order.id, new_job_id, correlation_id)

    return {
        "status": "analyzing",
        "incident_id": incident.id,
        "job_id": new_job_id,
        "correlation_id": correlation_id
    }

# ------------------------------------------------------------------------------
# 5. Decisão Humana (Aprovar / Rejeitar com Idempotência e Integridade de Estados)
# ------------------------------------------------------------------------------
async def _trigger_n8n_action(incident_id: str, correlation_id: str):
    """
    Dispara o workflow WF02 no n8n após aprovação humana.
    Apenas incidentes com ação CREATE_INTERNAL_TICKET geram tickets.
    """
    incident = get_incident(incident_id)
    if not incident or not incident.agent_result:
        return

    # Bloqueio estrito de segurança: nunca executar ação sem aprovação persistida
    if incident.status not in (IncidentStatus.APPROVED, IncidentStatus.EXECUTING) or not incident.approved_at:
        return

    # Apenas CREATE_INTERNAL_TICKET deve gerar ticket no WF02
    if incident.agent_result.recommended_action != ActionType.CREATE_INTERNAL_TICKET:
        return

    payload = {
        "incident_id": incident_id,
        "approved_action": incident.agent_result.recommended_action.value,
        "correlation_id": correlation_id
    }
    dispatch, code = await _send_n8n_webhook(settings.N8N_WEBHOOK_ACTION_URL, payload, timeout=4.0)
    if dispatch == "accepted":
        return

    if settings.REQUIRE_N8N or dispatch != "unavailable":
        pending = dispatch == "unconfirmed"
        if pending:
            message = "WF02: confirmação pendente. O n8n pode estar executando a ação."
        elif code is not None:
            message = f"WF02: o webhook recusou a ação (HTTP {code})."
        else:
            message = "WF02: não foi possível conectar ao n8n."

        updated, _, _ = atomic_apply_action_result(
            incident_id, "pending" if pending else "failed", error_message=message
        )
        if updated:
            record_audit_event(
                actor="system",
                event_type="action_confirmation_pending" if pending else "action_failed",
                incident_id=incident_id, payload={"detail": message}, correlation_id=correlation_id
            )
        return

    if dispatch == "unavailable":
        now = datetime.now(timezone.utc)
        ticket_id = f"TCK-{incident_id.replace('INC-', '')}"
        ticket = MockTicket(
            id=ticket_id,
            incident_id=incident_id,
            priority=incident.agent_result.priority,
            category=incident.agent_result.action_arguments.get("category", "late_delivery"),
            description=incident.agent_result.action_arguments.get(
                "description",
                f"Ação aprovada pelo operador: {incident.agent_result.summary}"
            ),
            created_at=now,
            created_by_workflow_id="WF02_LocalRunner"
        )
        create_mock_ticket(ticket)

        updated, _, _ = atomic_apply_action_result(incident_id, "executed")
        if not updated:
            return

        record_audit_event(
            actor="system",
            event_type="ticket_created_local_runner",
            incident_id=incident.id,
            payload={"ticket_id": ticket_id, "action": incident.agent_result.recommended_action.value},
            correlation_id=correlation_id
        )

@router.post("/incidents/{incident_id}/decision")
async def record_human_decision(
    incident_id: str,
    payload: DecisionPayload,
    background_tasks: BackgroundTasks,
    operator_id: Optional[str] = Header(None, alias="X-Operator-Id")
):
    """
    Registra a supervisão humana sobre a recomendação do agente com validação estrita da máquina de estados.
    - Se 'reject': encerra com status 'rejected'. Impede rejeitar incidentes já aprovados/executados (Fix Ponto 4).
    - Se 'approve': valida se status é 'proposed'.
        - NO_ACTION: resolve a ocorrência sem gerar tickets.
        - DRAFT_CUSTOMER_MESSAGE: registra mensagem despachada sem gerar tickets.
        - CREATE_INTERNAL_TICKET: transiciona para 'approved' e dispara o WF02.
    - Identifica o operador via header X-Operator-Id (Fix Ponto 6).
    """
    now = datetime.now(timezone.utc)
    correlation_id = f"DEC-{uuid.uuid4().hex[:8]}"
    actor = sanitize_operator_attribution(operator_id)

    decision_action = payload.decision.lower().strip()
    if decision_action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="Decisão inválida. Use 'approve' ou 'reject'.")

    # Transição de decisão atômica condicional no banco de dados
    success, updated_incident, code = atomic_record_human_decision(incident_id, decision_action, now)

    if not success:
        if code == "not_found":
            raise HTTPException(status_code=404, detail=f"Incidente {incident_id} não encontrado.")
        if code == "invalid_recommendation":
            raise HTTPException(status_code=400, detail="Não é possível aprovar um incidente sem recomendação válida.")
        if code == "cannot_reject_approved":
            raise HTTPException(
                status_code=400,
                detail=f"Operação inválida. O incidente já foi aprovado/executado ({updated_incident.status.value}) e não pode ser rejeitado."
            )
        if code == "cannot_approve_rejected":
            raise HTTPException(
                status_code=400,
                detail="Operação inválida. Incidente rejeitado não pode ser aprovado."
            )
        if code == "already_approved":
            return {
                "status": "already_approved",
                "incident_id": updated_incident.id,
                "current_status": updated_incident.status.value,
                "message": "Incidente já aprovado previamente."
            }
        if code == "already_rejected":
            return {
                "status": "already_rejected",
                "incident_id": updated_incident.id,
                "current_status": "rejected",
                "message": "Incidente já havia sido rejeitado previamente."
            }
        if code.startswith("invalid_status"):
            cur_st = updated_incident.status.value if updated_incident else "unknown"
            raise HTTPException(
                status_code=400,
                detail=f"Apenas incidentes no status 'proposed' podem sofrer decisão (status atual: '{cur_st}')."
            )
        raise HTTPException(status_code=409, detail="Conflito de concorrência ao processar decisão.")

    incident = updated_incident

    if decision_action == "reject":
        record_audit_event(
            actor=actor,
            event_type="recommendation_rejected",
            incident_id=incident.id,
            payload={"reason": payload.reason or "Operador rejeitou recomendação da IA"},
            correlation_id=correlation_id
        )
        return {"status": "rejected", "incident_id": incident.id, "current_status": "rejected"}

    recommended_action = incident.agent_result.recommended_action

    if recommended_action == ActionType.NO_ACTION:
        record_audit_event(
            actor=actor,
            event_type="no_action_resolved",
            incident_id=incident.id,
            payload={
                "action": "NO_ACTION",
                "is_simulated": True,
                "action_nature": "simulated",
                "execution_label": "Ação Simulada: Ocorrência Arquivada / Nenhuma Intervenção Externa",
                "reason": payload.reason or "Operador confirmou que nenhuma ação corretiva é necessária"
            },
            correlation_id=correlation_id
        )
        return {
            "status": "resolved_no_action",
            "incident_id": incident.id,
            "current_status": "executed",
            "is_simulated": True,
            "message": "Recomendação NO_ACTION confirmada. Ocorrência resolvida sem geração de tickets."
        }

    elif recommended_action == ActionType.DRAFT_CUSTOMER_MESSAGE:
        record_audit_event(
            actor=actor,
            event_type="customer_message_dispatched",
            incident_id=incident.id,
            payload={
                "action": "DRAFT_CUSTOMER_MESSAGE",
                "is_simulated": True,
                "action_nature": "simulated",
                "execution_label": "Ação Simulada: Notificação do Cliente Registrada em Auditoria (Sem Envio Externo)",
                "operator_message": incident.agent_result.operator_message
            },
            correlation_id=correlation_id
        )
        return {
            "status": "executed_customer_message",
            "incident_id": incident.id,
            "current_status": "executed",
            "is_simulated": True,
            "message": "Mensagem ao cliente despachada em ambiente simulado. Ocorrência resolvida sem abertura de ticket."
        }

    elif recommended_action == ActionType.CREATE_INTERNAL_TICKET:
        record_audit_event(
            actor=actor,
            event_type="recommendation_approved",
            incident_id=incident.id,
            payload={
                "action": incident.agent_result.recommended_action.value,
                "is_simulated": False,
                "action_nature": "authorized",
                "execution_label": "Abertura de chamado interno autorizada",
                "approved_priority": incident.agent_result.priority
            },
            correlation_id=correlation_id
        )

        background_tasks.add_task(_trigger_n8n_action, incident.id, correlation_id)

        return {
            "status": "approved",
            "incident_id": incident.id,
            "current_status": "approved",
            "is_simulated": False,
            "message": "Incidente aprovado. Ação de ticket interno enviada para execução."
        }
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Ação recomendada desconhecida: {recommended_action}"
        )

# ------------------------------------------------------------------------------
# 6. Auditoria & Políticas
# ------------------------------------------------------------------------------
@router.get("/audit")
def get_audit_trail(limit: int = Query(50, ge=1, le=200)):
    """Retorna eventos recentes da trilha de auditoria para o painel de governança."""
    events = list_audit_events(limit=limit)
    return [ev.model_dump() for ev in events]

@router.get("/policies")
def get_all_policies():
    """Retorna as políticas operacionais ativas na base de conhecimento simulada."""
    policies = list_policies()
    return [p.model_dump() for p in policies]

# ------------------------------------------------------------------------------
# 7. Relógio Simulado & Reset da Demonstração
# ------------------------------------------------------------------------------
@router.post("/demo/advance-time")
def advance_simulated_clock(
    payload: AdvanceTimePayload,
    operator_id: Optional[str] = Header(None, alias="X-Operator-Id")
):
    """
    Avança o relógio simulado determinístico e recalcula o score de risco de todos os pedidos ativos.
    (Fix Ponto 7)
    """
    result = advance_simulated_time(payload.minutes)
    return result

@router.post("/demo/reset")
def reset_demonstration_dataset():
    """Restaura integralmente a base de dados determinística para o estado de seed inicial."""
    result = seed_database(drop_existing=True)
    return {
        "status": "reset_successful",
        "details": result,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
