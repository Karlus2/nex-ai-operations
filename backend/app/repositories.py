import json
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from pydantic import ValidationError
from backend.app.database import get_connection
from backend.app.models import (
    Order, OrderEvent, OrderItem, OrderStatus,
    Incident, IncidentStatus, RiskLevel, AgentResult,
    AuditEvent, MockTicket, Policy, ActionType
)
from backend.app.risk_engine import evaluate_order_risk

def _parse_iso(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

# ==============================================================================
# Repositório de Pedidos (Orders)
# ==============================================================================

def save_order(order: Order) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    items_json = json.dumps([item.model_dump() for item in order.items])
    cursor.execute("""
        INSERT INTO orders (
            id, restaurant_name, created_at, promised_at, status,
            courier_assigned, last_status_update_at, restaurant_backlog,
            estimated_prep_minutes_remaining, distance_km, items_json, customer_notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            restaurant_name=excluded.restaurant_name,
            created_at=excluded.created_at,
            promised_at=excluded.promised_at,
            status=excluded.status,
            courier_assigned=excluded.courier_assigned,
            last_status_update_at=excluded.last_status_update_at,
            restaurant_backlog=excluded.restaurant_backlog,
            estimated_prep_minutes_remaining=excluded.estimated_prep_minutes_remaining,
            distance_km=excluded.distance_km,
            items_json=excluded.items_json,
            customer_notes=excluded.customer_notes
    """, (
        order.id,
        order.restaurant_name,
        order.created_at.isoformat(),
        order.promised_at.isoformat(),
        order.status.value,
        1 if order.courier_assigned else 0,
        order.last_status_update_at.isoformat(),
        order.restaurant_backlog,
        order.estimated_prep_minutes_remaining,
        order.distance_km,
        items_json,
        order.customer_notes
    ))
    conn.commit()
    conn.close()

def get_order(order_id: str) -> Optional[Order]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None

    items_data = json.loads(row["items_json"])
    items = [OrderItem(**item) for item in items_data]

    return Order(
        id=row["id"],
        restaurant_name=row["restaurant_name"],
        created_at=datetime.fromisoformat(row["created_at"]),
        promised_at=datetime.fromisoformat(row["promised_at"]),
        status=OrderStatus(row["status"]),
        courier_assigned=bool(row["courier_assigned"]),
        last_status_update_at=datetime.fromisoformat(row["last_status_update_at"]),
        restaurant_backlog=row["restaurant_backlog"],
        estimated_prep_minutes_remaining=row["estimated_prep_minutes_remaining"],
        distance_km=row["distance_km"],
        items=items,
        customer_notes=row["customer_notes"]
    )

def list_orders(
    status: Optional[str] = None,
    risk: Optional[str] = None,
    search: Optional[str] = None
) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT o.*, i.id as incident_id, i.risk_score, i.risk_level, 
               i.risk_signals_json, i.status as incident_status
        FROM orders o
        LEFT JOIN incidents i ON o.id = i.order_id
        WHERE 1=1
    """
    params = []

    if status:
        query += " AND o.status = ?"
        params.append(status)
    if risk:
        query += " AND i.risk_level = ?"
        params.append(risk)
    if search:
        query += " AND (o.id LIKE ? OR o.restaurant_name LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term])

    query += " ORDER BY COALESCE(i.risk_score, 0) DESC, o.promised_at ASC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        signals = json.loads(row["risk_signals_json"]) if row["risk_signals_json"] else []
        results.append({
            "id": row["id"],
            "restaurant_name": row["restaurant_name"],
            "created_at": row["created_at"],
            "promised_at": row["promised_at"],
            "status": row["status"],
            "courier_assigned": bool(row["courier_assigned"]),
            "last_status_update_at": row["last_status_update_at"],
            "restaurant_backlog": row["restaurant_backlog"],
            "estimated_prep_minutes_remaining": row["estimated_prep_minutes_remaining"],
            "distance_km": row["distance_km"],
            "customer_notes": row["customer_notes"],
            "incident": {
                "id": row["incident_id"],
                "risk_score": row["risk_score"] if row["risk_score"] is not None else 0,
                "risk_level": row["risk_level"] if row["risk_level"] is not None else "low",
                "risk_signals": signals,
                "status": row["incident_status"] if row["incident_status"] else None
            } if row["incident_id"] else None
        })
    return results

# ==============================================================================
# Repositório de Eventos do Pedido (OrderEvents)
# ==============================================================================

def save_order_event(event: OrderEvent) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO order_events (id, order_id, timestamp, event_type, details_json)
        VALUES (?, ?, ?, ?, ?)
    """, (
        event.id,
        event.order_id,
        event.timestamp.isoformat(),
        event.event_type,
        json.dumps(event.details)
    ))
    conn.commit()
    conn.close()

def get_order_events(order_id: str) -> List[OrderEvent]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM order_events WHERE order_id = ? ORDER BY timestamp ASC", (order_id,))
    rows = cursor.fetchall()
    conn.close()
    events = []
    for row in rows:
        events.append(OrderEvent(
            id=row["id"],
            order_id=row["order_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            event_type=row["event_type"],
            details=json.loads(row["details_json"])
        ))
    return events

# ==============================================================================
# Repositório de Incidentes (Incidents)
# ==============================================================================

def save_incident(incident: Incident) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    agent_result_json = incident.agent_result.model_dump_json() if incident.agent_result else None
    signals_json = json.dumps(incident.risk_signals)

    cursor.execute("""
        INSERT INTO incidents (
            id, order_id, risk_score, risk_level, risk_signals_json, status,
            analysis_job_id, agent_result_json, created_at, updated_at,
            approved_at, executed_at, error_message
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            order_id=excluded.order_id,
            risk_score=excluded.risk_score,
            risk_level=excluded.risk_level,
            risk_signals_json=excluded.risk_signals_json,
            status=excluded.status,
            analysis_job_id=excluded.analysis_job_id,
            agent_result_json=excluded.agent_result_json,
            updated_at=excluded.updated_at,
            approved_at=excluded.approved_at,
            executed_at=excluded.executed_at,
            error_message=excluded.error_message
    """, (
        incident.id,
        incident.order_id,
        incident.risk_score,
        incident.risk_level.value,
        signals_json,
        incident.status.value,
        incident.analysis_job_id,
        agent_result_json,
        incident.created_at.isoformat(),
        incident.updated_at.isoformat(),
        incident.approved_at.isoformat() if incident.approved_at else None,
        incident.executed_at.isoformat() if incident.executed_at else None,
        incident.error_message
    ))
    conn.commit()
    conn.close()

def get_incident(incident_id: str) -> Optional[Incident]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None

    agent_result = None
    if row["agent_result_json"]:
        agent_result = AgentResult.model_validate_json(row["agent_result_json"])

    return Incident(
        id=row["id"],
        order_id=row["order_id"],
        risk_score=row["risk_score"],
        risk_level=RiskLevel(row["risk_level"]),
        risk_signals=json.loads(row["risk_signals_json"]),
        status=IncidentStatus(row["status"]),
        analysis_job_id=row["analysis_job_id"],
        agent_result=agent_result,
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        approved_at=_parse_iso(row["approved_at"]),
        executed_at=_parse_iso(row["executed_at"]),
        error_message=row["error_message"]
    )

def get_incident_by_order(order_id: str) -> Optional[Incident]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM incidents WHERE order_id = ?", (order_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None

    agent_result = None
    if row["agent_result_json"]:
        agent_result = AgentResult.model_validate_json(row["agent_result_json"])

    return Incident(
        id=row["id"],
        order_id=row["order_id"],
        risk_score=row["risk_score"],
        risk_level=RiskLevel(row["risk_level"]),
        risk_signals=json.loads(row["risk_signals_json"]),
        status=IncidentStatus(row["status"]),
        analysis_job_id=row["analysis_job_id"],
        agent_result=agent_result,
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        approved_at=_parse_iso(row["approved_at"]),
        executed_at=_parse_iso(row["executed_at"]),
        error_message=row["error_message"]
    )

def list_incidents(status: Optional[str] = None) -> List[Incident]:
    conn = get_connection()
    cursor = conn.cursor()
    if status:
        cursor.execute("SELECT * FROM incidents WHERE status = ? ORDER BY risk_score DESC, updated_at DESC", (status,))
    else:
        cursor.execute("SELECT * FROM incidents ORDER BY risk_score DESC, updated_at DESC")
    rows = cursor.fetchall()
    conn.close()

    incidents = []
    for row in rows:
        agent_result = AgentResult.model_validate_json(row["agent_result_json"]) if row["agent_result_json"] else None
        incidents.append(Incident(
            id=row["id"],
            order_id=row["order_id"],
            risk_score=row["risk_score"],
            risk_level=RiskLevel(row["risk_level"]),
            risk_signals=json.loads(row["risk_signals_json"]),
            status=IncidentStatus(row["status"]),
            analysis_job_id=row["analysis_job_id"],
            agent_result=agent_result,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            approved_at=_parse_iso(row["approved_at"]),
            executed_at=_parse_iso(row["executed_at"]),
            error_message=row["error_message"]
        ))
    return incidents

# ==============================================================================
# Operações Atômicas Condicionais de Estados (Fix Prioridades 2 e 3)
# ==============================================================================

def atomic_initiate_analysis(
    order_id: str,
    new_job_id: str,
    risk_score: int,
    risk_level: RiskLevel,
    risk_signals: List[str]
) -> Tuple[bool, Optional[Incident], str]:
    """
    Inicia atômica e condicionalmente a triagem de um pedido.
    Bloqueia reanálise se o incidente já estiver em estado terminal (approved, rejected, executed) (Fix Prioridade 2).
    """
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now(timezone.utc)
    signals_json = json.dumps(risk_signals)

    cursor.execute("SELECT * FROM incidents WHERE order_id = ?", (order_id,))
    row = cursor.fetchone()

    if row:
        current_status = row["status"]
        incident_id = row["id"]
        # Bloqueio de reanálise em estados pós-decisão ou terminais
        if row["approved_at"] or current_status in ("approved", "rejected", "executing", "executed"):
            conn.close()
            return False, get_incident(incident_id), f"Incidente {incident_id} já se encontra no estado '{current_status}'. Reanálise não permitida."

        cursor.execute("""
            UPDATE incidents
            SET status = 'analyzing',
                analysis_job_id = ?,
                agent_result_json = NULL,
                risk_score = ?,
                risk_level = ?,
                risk_signals_json = ?,
                error_message = NULL,
                updated_at = ?
            WHERE id = ? AND approved_at IS NULL
              AND status NOT IN ('approved', 'rejected', 'executing', 'executed')
        """, (
            new_job_id,
            risk_score,
            risk_level.value,
            signals_json,
            now.isoformat(),
            incident_id
        ))
        if cursor.rowcount == 0:
            conn.close()
            return False, get_incident(incident_id), f"Conflito de concorrência ao transicionar incidente {incident_id} para 'analyzing'."
    else:
        incident_id = f"INC-{order_id.replace('NEX-', '')}"
        cursor.execute("""
            INSERT INTO incidents (
                id, order_id, risk_score, risk_level, risk_signals_json,
                status, analysis_job_id, agent_result_json, created_at,
                updated_at, approved_at, executed_at, error_message
            ) VALUES (?, ?, ?, ?, ?, 'analyzing', ?, NULL, ?, ?, NULL, NULL, NULL)
        """, (
            incident_id,
            order_id,
            risk_score,
            risk_level.value,
            signals_json,
            new_job_id,
            now.isoformat(),
            now.isoformat()
        ))

    conn.commit()
    conn.close()
    return True, get_incident(incident_id), "ok"

def atomic_record_analysis_dispatch_issue(
    incident_id: str, job_id: str, message: str, *, pending: bool = False
) -> bool:
    conn = get_connection()
    try:
        with conn:
            cursor = conn.execute("""
                UPDATE incidents
                SET status = ?, error_message = ?, updated_at = ?
                WHERE id = ? AND status = 'analyzing' AND analysis_job_id = ?
            """, ("analyzing" if pending else "failed", message, _now_iso(), incident_id, job_id))
            return cursor.rowcount == 1
    finally:
        conn.close()

def atomic_apply_analysis_proposal(
    incident_id: str,
    job_id: str,
    correlation_id: Optional[str],
    agent_result: AgentResult
) -> Tuple[bool, Optional[Incident], str]:
    """
    Aplica atômica e condicionalmente a proposta do agente.
    Valida correspondência estrita com o job_id ativo e impede sobrescrever estados terminais (Fix Prioridade 2).
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False, None, "not_found"

    current_status = row["status"]
    active_job_id = row["analysis_job_id"]

    # Bloqueio de sobrescrita de estados pós-análise ou terminais
    if current_status != "analyzing":
        conn.close()
        return False, get_incident(incident_id), f"Incidente {incident_id} já está no estado terminal ou pós-análise '{current_status}'. Callback tardio ignorado."

    if not job_id or job_id != active_job_id:
        conn.close()
        return False, get_incident(incident_id), f"Inconsistência de job: callback refere-se a '{job_id}', mas o job ativo é '{active_job_id}'."

    if agent_result.incident_id != incident_id:
        conn.close()
        return False, None, "A recomendação deve pertencer ao incidente analisado."

    now = datetime.now(timezone.utc)
    agent_result_json = agent_result.model_dump_json()

    cursor.execute("""
        UPDATE incidents
        SET status = 'proposed',
            agent_result_json = ?,
            error_message = NULL,
            updated_at = ?
        WHERE id = ? AND status = 'analyzing' AND analysis_job_id = ?
    """, (
        agent_result_json,
        now.isoformat(),
        incident_id,
        job_id
    ))

    if cursor.rowcount == 0:
        conn.close()
        return False, get_incident(incident_id), "Conflito de concorrência: estado ou análise ativa mudou durante a operação."

    conn.commit()
    conn.close()
    return True, get_incident(incident_id), "ok"

def atomic_apply_action_result(
    incident_id: str,
    status_update: str,
    workflow_execution_id: Optional[str] = None,
    error_message: Optional[str] = None
) -> Tuple[bool, Optional[Incident], str]:
    """
    Finaliza atômica e condicionalmente a execução de uma ação (Fix Prioridade 3).
    Exige aprovação humana prévia e, para CREATE_INTERNAL_TICKET, comprovação de criação do ticket no SQLite.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False, None, "not_found"

    current_status = row["status"]
    approved_at = row["approved_at"]

    # 1. Bloqueio de autorização prévia
    if current_status not in ("approved", "executing") or not approved_at:
        conn.close()
        return False, get_incident(incident_id), "unauthorized: incidente não possui aprovação humana persistida."

    now = datetime.now(timezone.utc)

    if status_update == "executed":
        # 2. Comprovação de execução: se a ação é ticket, o ticket DEVE existir no banco
        agent_result_raw = row["agent_result_json"]
        if agent_result_raw:
            try:
                res_dict = json.loads(agent_result_raw)
                if res_dict.get("recommended_action") == ActionType.CREATE_INTERNAL_TICKET.value:
                    cursor.execute("SELECT id FROM mock_tickets WHERE incident_id = ?", (incident_id,))
                    ticket_row = cursor.fetchone()
                    if not ticket_row:
                        conn.close()
                        return False, get_incident(incident_id), "unproven_execution: ticket interno obrigatório não foi encontrado no banco de dados."
            except Exception:
                pass

        cursor.execute("""
            UPDATE incidents
            SET status = 'executed',
                executed_at = ?,
                error_message = NULL,
                updated_at = ?
            WHERE id = ? AND status IN ('approved', 'executing')
        """, (now.isoformat(), now.isoformat(), incident_id))
    elif status_update == "pending":
        cursor.execute("""
            UPDATE incidents
            SET error_message = ?, updated_at = ?
            WHERE id = ? AND status IN ('approved', 'executing')
        """, (error_message, now.isoformat(), incident_id))
    else:
        cursor.execute("""
            UPDATE incidents
            SET status = 'failed',
                error_message = ?,
                updated_at = ?
            WHERE id = ? AND status IN ('approved', 'executing')
        """, (error_message or "Falha reportada pelo executor", now.isoformat(), incident_id))

    if cursor.rowcount == 0:
        conn.close()
        return False, get_incident(incident_id), "Conflito de concorrência ao atualizar resultado da ação."

    conn.commit()
    conn.close()
    return True, get_incident(incident_id), "ok"

def atomic_record_human_decision(
    incident_id: str,
    decision: str,
    now: datetime
) -> Tuple[bool, Optional[Incident], str]:
    """
    Registra a decisão humana (approve/reject) de forma atômica e condicional via SQL.
    Garante integridade de máquina de estados sob concorrência intensa.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False, None, "not_found"

    current_status = row["status"]

    if decision == "reject":
        if row["approved_at"] or current_status in ("approved", "executing", "executed"):
            conn.close()
            return False, get_incident(incident_id), "cannot_reject_approved"
        if current_status == "rejected":
            conn.close()
            return False, get_incident(incident_id), "already_rejected"
        if current_status != "proposed":
            conn.close()
            return False, get_incident(incident_id), f"invalid_status_{current_status}"

        cursor.execute("""
            UPDATE incidents
            SET status = 'rejected',
                updated_at = ?
            WHERE id = ? AND status = 'proposed'
        """, (now.isoformat(), incident_id))
        conn.commit()

        if cursor.rowcount == 0:
            conn.close()
            fresh_inc = get_incident(incident_id)
            if fresh_inc and fresh_inc.status == IncidentStatus.REJECTED:
                return False, fresh_inc, "already_rejected"
            return False, fresh_inc, "concurrent_conflict"

        conn.close()
        return True, get_incident(incident_id), "rejected"

    elif decision == "approve":
        if current_status == "rejected":
            conn.close()
            return False, get_incident(incident_id), "cannot_approve_rejected"
        if row["approved_at"] or current_status in ("approved", "executing", "executed"):
            conn.close()
            return False, get_incident(incident_id), "already_approved"
        if current_status != "proposed":
            conn.close()
            return False, get_incident(incident_id), f"invalid_status_{current_status}"

        agent_result_raw = row["agent_result_json"]
        if not agent_result_raw:
            conn.close()
            return False, None, "invalid_recommendation"
        try:
            agent_result = AgentResult.model_validate_json(agent_result_raw)
        except ValidationError:
            conn.close()
            return False, None, "invalid_recommendation"
        if agent_result.incident_id != incident_id:
            conn.close()
            return False, None, "invalid_recommendation"

        target_status = "approved"
        executed_at_iso = None
        if agent_result.recommended_action in (ActionType.NO_ACTION, ActionType.DRAFT_CUSTOMER_MESSAGE):
            target_status = "executed"
            executed_at_iso = now.isoformat()

        cursor.execute("""
            UPDATE incidents
            SET status = ?,
                approved_at = ?,
                executed_at = ?,
                updated_at = ?
            WHERE id = ? AND status = 'proposed' AND analysis_job_id IS ? AND agent_result_json = ?
        """, (
            target_status, now.isoformat(), executed_at_iso, now.isoformat(),
            incident_id, row["analysis_job_id"], agent_result_raw
        ))
        conn.commit()

        if cursor.rowcount == 0:
            conn.close()
            fresh_inc = get_incident(incident_id)
            if fresh_inc and fresh_inc.approved_at:
                return False, fresh_inc, "already_approved"
            return False, fresh_inc, "concurrent_conflict"

        conn.close()
        return True, get_incident(incident_id), "approved"

    conn.close()
    return False, None, "unknown_decision"

# ==============================================================================
# Repositório de Auditoria (AuditEvents)
# ==============================================================================

def record_audit_event(
    actor: str,
    event_type: str,
    incident_id: str,
    payload: Dict[str, Any],
    correlation_id: Optional[str] = None
) -> AuditEvent:
    conn = get_connection()
    cursor = conn.cursor()
    audit_id = f"AUD-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc)
    payload_json = json.dumps(payload)

    cursor.execute("""
        INSERT INTO audit_events (id, incident_id, timestamp, actor, event_type, payload_redacted_json, correlation_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        audit_id,
        incident_id,
        now.isoformat(),
        actor,
        event_type,
        payload_json,
        correlation_id
    ))
    conn.commit()
    conn.close()

    return AuditEvent(
        id=audit_id,
        incident_id=incident_id,
        timestamp=now,
        actor=actor,
        event_type=event_type,
        payload_redacted=payload,
        correlation_id=correlation_id
    )

def list_audit_events(incident_id: Optional[str] = None, limit: int = 50) -> List[AuditEvent]:
    conn = get_connection()
    cursor = conn.cursor()
    if incident_id:
        cursor.execute("SELECT * FROM audit_events WHERE incident_id = ? ORDER BY timestamp DESC LIMIT ?", (incident_id, limit))
    else:
        cursor.execute("SELECT * FROM audit_events ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()

    events = []
    for row in rows:
        events.append(AuditEvent(
            id=row["id"],
            incident_id=row["incident_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            actor=row["actor"],
            event_type=row["event_type"],
            payload_redacted=json.loads(row["payload_redacted_json"]),
            correlation_id=row["correlation_id"]
        ))
    return events

# ==============================================================================
# Repositório de Tickets Fictícios (MockTickets)
# ==============================================================================

def atomic_create_mock_ticket(ticket: MockTicket) -> Tuple[bool, MockTicket]:
    """
    Insere atômica e idempotentemente um ticket para o incidente associado.
    Retorna (True, ticket) se for criado com sucesso pela primeira vez.
    Retorna (False, existing_ticket) se já existia um ticket registrado para o incidente.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO mock_tickets (
            id, incident_id, priority, category, description, created_at, created_by_workflow_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(incident_id) DO NOTHING
    """, (
        ticket.id,
        ticket.incident_id,
        ticket.priority,
        ticket.category,
        ticket.description,
        ticket.created_at.isoformat(),
        ticket.created_by_workflow_id
    ))
    conn.commit()

    if cursor.rowcount > 0:
        conn.close()
        return True, ticket

    cursor.execute("SELECT * FROM mock_tickets WHERE incident_id = ?", (ticket.incident_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        existing = MockTicket(
            id=row["id"],
            incident_id=row["incident_id"],
            priority=row["priority"],
            category=row["category"],
            description=row["description"],
            created_at=datetime.fromisoformat(row["created_at"]),
            created_by_workflow_id=row["created_by_workflow_id"]
        )
        return False, existing
    return False, ticket

def create_mock_ticket(ticket: MockTicket) -> MockTicket:
    _, saved = atomic_create_mock_ticket(ticket)
    return saved

def get_mock_ticket_by_incident(incident_id: str) -> Optional[MockTicket]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM mock_tickets WHERE incident_id = ?", (incident_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return MockTicket(
        id=row["id"],
        incident_id=row["incident_id"],
        priority=row["priority"],
        category=row["category"],
        description=row["description"],
        created_at=datetime.fromisoformat(row["created_at"]),
        created_by_workflow_id=row["created_by_workflow_id"]
    )

# ==============================================================================
# Repositório de Políticas Fictícias (Policies)
# ==============================================================================

def save_policy(policy: Policy) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO policies (
            code, title, version, category, summary, recommended_action, content
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        policy.code,
        policy.title,
        policy.version,
        policy.category,
        policy.summary,
        policy.recommended_action.value,
        policy.content
    ))
    conn.commit()
    conn.close()

def get_policy(code: str) -> Optional[Policy]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM policies WHERE code = ?", (code,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return Policy(
        code=row["code"],
        title=row["title"],
        version=row["version"],
        category=row["category"],
        summary=row["summary"],
        recommended_action=row["recommended_action"],
        content=row["content"]
    )

def list_policies() -> List[Policy]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM policies ORDER BY code ASC")
    rows = cursor.fetchall()
    conn.close()
    return [Policy(
        code=r["code"],
        title=r["title"],
        version=r["version"],
        category=r["category"],
        summary=r["summary"],
        recommended_action=r["recommended_action"],
        content=r["content"]
    ) for r in rows]

# ==============================================================================
# Resumo / KPIs para Visão Geral
# ==============================================================================

def get_summary() -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()

    # Pedidos ativos: created, preparing, ready, picked_up
    cursor.execute("""
        SELECT COUNT(*) as cnt FROM orders 
        WHERE status IN ('created', 'preparing', 'ready', 'picked_up')
    """)
    active_orders = cursor.fetchone()["cnt"]

    # Pedidos com atenção alta (score >= 60)
    cursor.execute("""
        SELECT COUNT(*) as cnt FROM incidents i
        JOIN orders o ON i.order_id = o.id
        WHERE i.risk_score >= 60 
          AND o.status IN ('created', 'preparing', 'ready', 'picked_up')
    """)
    high_risk_orders = cursor.fetchone()["cnt"]

    # Incidentes aguardando aprovação humana (status 'proposed')
    cursor.execute("""
        SELECT COUNT(*) as cnt FROM incidents 
        WHERE status = 'proposed'
    """)
    pending_approvals = cursor.fetchone()["cnt"]

    # Ações executadas com sucesso
    cursor.execute("SELECT COUNT(*) as cnt FROM mock_tickets")
    executed_actions = cursor.fetchone()["cnt"]

    conn.close()

    return {
        "active_orders": active_orders,
        "high_risk_orders": high_risk_orders,
        "pending_approvals": pending_approvals,
        "executed_actions": executed_actions
    }

# ==============================================================================
# Relógio Simulado Determinístico (demo_state)
# ==============================================================================

DEFAULT_SIMULATED_BASE_TIME = datetime(2026, 11, 12, 12, 35, 0, tzinfo=timezone.utc)

def get_simulated_time() -> datetime:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM demo_state WHERE key = 'current_simulated_time'")
    row = cursor.fetchone()
    conn.close()
    if row and row["value"]:
        try:
            return datetime.fromisoformat(row["value"])
        except Exception:
            pass
    return DEFAULT_SIMULATED_BASE_TIME

def set_simulated_time(dt: datetime) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO demo_state (key, value) VALUES ('current_simulated_time', ?)",
        (dt.isoformat(),)
    )
    conn.commit()
    conn.close()

def advance_simulated_time(minutes: int = 5) -> Dict[str, Any]:
    from datetime import timedelta
    current_time = get_simulated_time()
    new_time = current_time + timedelta(minutes=minutes)
    set_simulated_time(new_time)

    # Recalcular risco para todos os pedidos ativos
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM orders WHERE status NOT IN ('delivered', 'cancelled')")
    active_rows = cursor.fetchall()
    conn.close()

    updated_count = 0
    for row in active_rows:
        order = get_order(row["id"])
        if not order:
            continue
        risk_res = evaluate_order_risk(order, evaluation_time=new_time)
        incident = get_incident_by_order(order.id)
        if incident:
            # Preservar o status do incidente se já estiver em analyzing, proposed, etc.
            incident.risk_score = risk_res.score
            incident.risk_level = risk_res.level
            incident.risk_signals = risk_res.signals
            incident.updated_at = new_time
            save_incident(incident)
            updated_count += 1
        elif risk_res.score > 0:
            # Criar novo incidente se risco superou limiar
            new_inc = Incident(
                id=f"INC-{order.id.replace('NEX-', '')}",
                order_id=order.id,
                risk_score=risk_res.score,
                risk_level=risk_res.level,
                risk_signals=risk_res.signals,
                status=IncidentStatus.DETECTED,
                created_at=new_time,
                updated_at=new_time
            )
            save_incident(new_inc)
            updated_count += 1

    return {
        "previous_time": current_time.isoformat(),
        "new_time": new_time.isoformat(),
        "minutes_advanced": minutes,
        "orders_updated": updated_count
    }
