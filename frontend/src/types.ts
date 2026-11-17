export type OrderStatus = 'created' | 'preparing' | 'ready' | 'picked_up' | 'delivered' | 'cancelled';
export type RiskLevel = 'low' | 'medium' | 'high';
export type IncidentStatus = 'detected' | 'analyzing' | 'proposed' | 'approved' | 'rejected' | 'executing' | 'executed' | 'failed';
export type ActionType = 'CREATE_INTERNAL_TICKET' | 'DRAFT_CUSTOMER_MESSAGE' | 'NO_ACTION';

export interface OrderItem {
  name: string;
  quantity: number;
  unit_price: number;
}

export interface OrderIncidentSummary {
  id: string;
  risk_score: number;
  risk_level: RiskLevel;
  risk_signals: string[];
  status: IncidentStatus | null;
}

export interface OrderListItem {
  id: string;
  restaurant_name: string;
  created_at: string;
  promised_at: string;
  status: OrderStatus;
  courier_assigned: boolean;
  last_status_update_at: string;
  restaurant_backlog: number;
  estimated_prep_minutes_remaining: number;
  distance_km: number;
  customer_notes?: string | null;
  incident?: OrderIncidentSummary | null;
}

export interface OrderDetail extends OrderListItem {
  items: OrderItem[];
}

export interface OrderEvent {
  id: string;
  order_id: string;
  timestamp: string;
  event_type: string;
  details: Record<string, any>;
}

export interface AgentEvidence {
  source: string;
  field: string;
  finding: string;
}

export interface AgentResult {
  incident_id: string;
  summary: string;
  evidence: AgentEvidence[];
  hypotheses: string[];
  recommended_action: ActionType;
  priority: string;
  action_arguments: Record<string, any>;
  operator_message: string;
  requires_human_approval: boolean;
  model_used?: string | null;
  execution_source?: string; // "n8n_workflow" ou "local_agent_fallback"
  latency_ms?: number | null;
}

export interface Incident {
  id: string;
  order_id: string;
  risk_score: number;
  risk_level: RiskLevel;
  risk_signals: string[];
  status: IncidentStatus;
  analysis_job_id?: string | null;
  agent_result?: AgentResult | null;
  created_at: string;
  updated_at: string;
  approved_at?: string | null;
  executed_at?: string | null;
  error_message?: string | null;
}

export interface MockTicket {
  id: string;
  incident_id: string;
  priority: string;
  category: string;
  description: string;
  created_at: string;
  created_by_workflow_id: string;
}

export interface AuditEvent {
  id: string;
  incident_id: string;
  timestamp: string;
  actor: string;
  event_type: string;
  payload_redacted: Record<string, any>;
  correlation_id?: string | null;
}

export interface Policy {
  code: string;
  title: string;
  version: string;
  category: string;
  summary: string;
  recommended_action: ActionType;
  content: string;
}

export interface SummaryKPIs {
  active_orders: number;
  high_risk_orders: number;
  pending_approvals: number;
  executed_actions: number;
}

