from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class OrderStatus(str, Enum):
    CREATED = "created"
    PREPARING = "preparing"
    READY = "ready"
    PICKED_UP = "picked_up"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class IncidentStatus(str, Enum):
    DETECTED = "detected"
    ANALYZING = "analyzing"
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    EXECUTED = "executed"
    FAILED = "failed"

class ActionType(str, Enum):
    CREATE_INTERNAL_TICKET = "CREATE_INTERNAL_TICKET"
    DRAFT_CUSTOMER_MESSAGE = "DRAFT_CUSTOMER_MESSAGE"
    NO_ACTION = "NO_ACTION"

class OrderItem(BaseModel):
    name: str
    quantity: int
    unit_price: float

class OrderEvent(BaseModel):
    id: str
    order_id: str
    timestamp: datetime
    event_type: str
    details: Dict[str, Any] = Field(default_factory=dict)

class Order(BaseModel):
    id: str
    restaurant_name: str
    created_at: datetime
    promised_at: datetime
    status: OrderStatus
    courier_assigned: bool
    last_status_update_at: datetime
    restaurant_backlog: int
    estimated_prep_minutes_remaining: int
    distance_km: float
    items: List[OrderItem] = Field(default_factory=list)
    customer_notes: Optional[str] = None

class AgentEvidence(BaseModel):
    source: str
    field: str
    finding: str

class AgentResult(BaseModel):
    incident_id: str
    summary: str
    evidence: List[AgentEvidence] = Field(default_factory=list)
    hypotheses: List[str] = Field(default_factory=list)
    recommended_action: ActionType
    priority: str = "medium"
    action_arguments: Dict[str, Any] = Field(default_factory=dict)
    operator_message: str
    requires_human_approval: bool = True
    model_used: Optional[str] = None
    execution_source: str = "n8n_workflow"  # "n8n_workflow" ou "local_agent_fallback"
    latency_ms: Optional[int] = None

class Incident(BaseModel):
    id: str
    order_id: str
    risk_score: int = Field(ge=0, le=100)
    risk_level: RiskLevel
    risk_signals: List[str] = Field(default_factory=list)
    status: IncidentStatus = IncidentStatus.DETECTED
    analysis_job_id: Optional[str] = None
    agent_result: Optional[AgentResult] = None
    created_at: datetime
    updated_at: datetime
    approved_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    error_message: Optional[str] = None

class AuditEvent(BaseModel):
    id: str
    incident_id: str
    timestamp: datetime
    actor: str  # "system", "agent", "operator"
    event_type: str
    payload_redacted: Dict[str, Any] = Field(default_factory=dict)
    correlation_id: Optional[str] = None

class MockTicket(BaseModel):
    id: str
    incident_id: str
    priority: str
    category: str
    description: str
    created_at: datetime
    created_by_workflow_id: str

class Policy(BaseModel):
    code: str
    title: str
    version: str
    category: str
    summary: str
    recommended_action: ActionType
    content: str
