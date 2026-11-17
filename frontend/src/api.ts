import {
  OrderListItem, OrderDetail, OrderEvent, Incident,
  MockTicket, AuditEvent, Policy, SummaryKPIs
} from './types';

const API_BASE = '/api';

export async function fetchHealth(): Promise<{ status: string; service: string; database: string }> {
  const res = await fetch('/health');
  if (!res.ok) throw new Error(`Healthcheck falhou: ${res.status}`);
  return res.json();
}

export async function fetchSummary(): Promise<SummaryKPIs> {
  const res = await fetch(`${API_BASE}/summary`);
  if (!res.ok) throw new Error('Falha ao carregar KPIs do resumo.');
  return res.json();
}

export async function fetchOrders(filters?: {
  status?: string;
  risk?: string;
  search?: string;
}): Promise<OrderListItem[]> {
  const params = new URLSearchParams();
  if (filters?.status) params.append('status', filters.status);
  if (filters?.risk) params.append('risk', filters.risk);
  if (filters?.search) params.append('search', filters.search);

  const res = await fetch(`${API_BASE}/orders?${params.toString()}`);
  if (!res.ok) throw new Error('Falha ao buscar pedidos.');
  return res.json();
}

export interface OrderDetailResponse {
  order: OrderDetail;
  events: OrderEvent[];
  calculated_risk: {
    score: number;
    level: string;
    signals: string[];
  };
  incident: Incident | null;
  mock_ticket: MockTicket | null;
}

export async function fetchOrderDetail(orderId: string): Promise<OrderDetailResponse> {
  const res = await fetch(`${API_BASE}/orders/${orderId}`);
  if (!res.ok) throw new Error(`Falha ao buscar detalhes do pedido ${orderId}`);
  return res.json();
}

export async function analyzeOrder(orderId: string): Promise<{
  status: string;
  incident_id: string;
  job_id: string;
  correlation_id: string;
}> {
  const res = await fetch(`${API_BASE}/orders/${orderId}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: 'Erro desconhecido' }));
    throw new Error(errorData.detail || 'Falha ao acionar análise com IA');
  }
  return res.json();
}

export async function sendDecision(
  incidentId: string,
  decision: 'approve' | 'reject',
  reason?: string
): Promise<{ status: string; incident_id: string }> {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/decision`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ decision, reason })
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: 'Erro desconhecido' }));
    throw new Error(errorData.detail || `Falha ao processar decisão (${decision})`);
  }
  return res.json();
}

export async function fetchAuditTrail(limit: number = 50): Promise<AuditEvent[]> {
  const res = await fetch(`${API_BASE}/audit?limit=${limit}`);
  if (!res.ok) throw new Error('Falha ao carregar trilha de auditoria.');
  return res.json();
}

export async function fetchPolicies(): Promise<Policy[]> {
  const res = await fetch(`${API_BASE}/policies`);
  if (!res.ok) throw new Error('Falha ao carregar políticas operacionais.');
  return res.json();
}

export async function resetDemo(): Promise<any> {
  const res = await fetch(`${API_BASE}/demo/reset`, { method: 'POST' });
  if (!res.ok) throw new Error('Falha ao reiniciar o ambiente de demonstração.');
  return res.json();
}

