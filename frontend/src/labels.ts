import type { ActionType, IncidentStatus, OrderStatus, RiskLevel } from './types';

export const orderStatusLabels: Record<OrderStatus, string> = {
  created: 'Criado',
  preparing: 'Em preparo',
  ready: 'Pronto para coleta',
  picked_up: 'Em rota',
  delivered: 'Entregue',
  cancelled: 'Cancelado',
};

export const riskLabels: Record<RiskLevel, string> = {
  low: 'Baixo',
  medium: 'Médio',
  high: 'Alto',
};

export const incidentStatusLabels: Record<IncidentStatus, string> = {
  detected: 'Detectado',
  analyzing: 'Em triagem',
  proposed: 'Aguardando decisão',
  approved: 'Aprovado',
  rejected: 'Rejeitado',
  executing: 'Em execução',
  executed: 'Concluído',
  failed: 'Falha',
};

export const actionLabels: Record<ActionType, string> = {
  CREATE_INTERNAL_TICKET: 'Abrir chamado interno',
  DRAFT_CUSTOMER_MESSAGE: 'Preparar mensagem ao cliente',
  NO_ACTION: 'Encerrar sem ação',
};

const categories: Record<string, string> = {
  logistics_dispatch: 'Logística e despacho',
  restaurant_operations: 'Operação do restaurante',
  customer_support: 'Atendimento ao cliente',
  standard_flow: 'Operação normal',
  late_delivery: 'Atraso na entrega',
  restaurant_backlog: 'Fila do restaurante',
};

const events: Record<string, string> = {
  order_created: 'Pedido criado',
  restaurant_confirmed: 'Pedido confirmado pelo restaurante',
  kitchen_in_progress: 'Preparo iniciado',
  sla_breach_detected: 'Prazo de entrega excedido',
  risk_evaluated: 'Risco avaliado',
  analysis_requested: 'Triagem solicitada',
  triage_dispatched_to_n8n: 'Triagem recebida pelo n8n',
  analysis_confirmation_pending: 'Confirmação da triagem pendente',
  analysis_completed: 'Triagem concluída',
  analysis_failed: 'Falha na triagem',
  late_callback_ignored: 'Retorno tardio descartado',
  recommendation_approved: 'Abertura de chamado autorizada',
  recommendation_rejected: 'Recomendação rejeitada',
  action_confirmation_pending: 'Confirmação da ação pendente',
  action_executed: 'Ação concluída',
  action_failed: 'Falha na execução da ação',
  ticket_created: 'Chamado criado',
  ticket_created_local_runner: 'Chamado criado pelo executor local',
  unauthorized_ticket_creation_attempt: 'Tentativa de abrir chamado sem autorização',
  no_action_resolved: 'Incidente encerrado sem ação',
  customer_message_dispatched: 'Mensagem ao cliente registrada em simulação',
};

export function categoryLabel(value: string): string {
  return Object.prototype.hasOwnProperty.call(categories, value) ? categories[value] : value.replace(/_/g, ' ');
}

export function eventLabel(value: string): string {
  return Object.prototype.hasOwnProperty.call(events, value) ? events[value] : value.replace(/_/g, ' ');
}

export function priorityLabel(value: string): string {
  const normalized = value.toLowerCase();
  const labels: Record<string, string> = { low: 'Baixa', medium: 'Média', high: 'Alta', critical: 'Crítica' };
  return Object.prototype.hasOwnProperty.call(labels, normalized) ? labels[normalized] : value;
}


const narrativeLabels: Record<string, string> = {
  ...actionLabels, ...orderStatusLabels, ...riskLabels,
  courier_assigned: 'entregador alocado',
  true: 'sim', false: 'não',
};

export function operatorText(text: string): string {
  return text
    .replace(/\b(não há entregador alocado|nenhum entregador (?:foi )?alocado)\s*\((?:false|não)\)/gi, '$1')
    .replace(/\b(?:CREATE_INTERNAL_TICKET|DRAFT_CUSTOMER_MESSAGE|NO_ACTION|created|preparing|ready|picked_up|delivered|cancelled|high|medium|low|courier_assigned|true|false)\b/g,
      token => narrativeLabels[token])
    .replace(/\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})\b/g, value => {
      const parsed = new Date(value);
      if (Number.isNaN(parsed.getTime())) return value;
      return new Intl.DateTimeFormat('pt-BR', {
        dateStyle: 'short', timeStyle: 'short', timeZone: 'America/Sao_Paulo',
      }).format(parsed) + ' (horário de Brasília)';
    });
}
