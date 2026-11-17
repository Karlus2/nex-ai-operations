import React, { useState } from 'react';
import {
  X, Sparkles, Check, Ban, AlertTriangle, Clock,
  Bike, Store, Shield, CheckCircle2, Ticket
} from 'lucide-react';
import { OrderDetailResponse } from '../api';
import { actionLabels, categoryLabel, eventLabel, incidentStatusLabels, orderStatusLabels, operatorText, priorityLabel } from '../labels';

interface OrderDrawerProps {
  data: OrderDetailResponse | null;
  loading: boolean;
  onClose: () => void;
  onAnalyze: (orderId: string) => Promise<void>;
  onDecision: (incidentId: string, decision: 'approve' | 'reject') => Promise<void>;
  isAnalyzing: boolean;
  isDeciding: boolean;
}

export const OrderDrawer: React.FC<OrderDrawerProps> = ({
  data,
  loading,
  onClose,
  onAnalyze,
  onDecision,
  isAnalyzing,
  isDeciding
}) => {
  const [rejectReason, setRejectReason] = useState('');
  const [showRejectModal, setShowRejectModal] = useState(false);

  if (!data && !loading) return null;

  const order = data?.order;
  const incident = data?.incident;
  const events = data?.events || [];
  const risk = data?.calculated_risk;
  const ticket = data?.mock_ticket;

  const score = incident?.risk_score ?? risk?.score ?? 0;
  const signals = incident?.risk_signals ?? risk?.signals ?? [];
  const status = incident?.status;
  const actionFailed = status === 'failed' && Boolean(incident?.approved_at);
  const actionPending = status === 'approved' || status === 'executing';
  const analysisSource = incident?.agent_result?.execution_source;
  const ticketSource = ticket?.created_by_workflow_id;

  const formatDateTime = (iso: string) => {
    try {
      const dt = new Date(iso);
      return dt.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    } catch {
      return iso;
    }
  };

  return (
    <div className="fixed inset-y-0 right-0 w-full sm:w-[480px] lg:w-[540px] bg-nexSurface border-l border-nexBorder shadow-2xl z-40 flex flex-col transition-all">
      {/* Header */}
      <div className="p-4 border-b border-nexBorder flex items-center justify-between bg-nexSurfaceHover/50">
        <div>
          <div className="flex items-center space-x-2">
            <span className="font-mono font-bold text-base text-nexPrimary">{order?.id}</span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-nexCyan/10 text-nexCyan border border-nexCyan/30">
              {order && orderStatusLabels[order.status]}
            </span>
          </div>
          <p className="text-xs text-nexSecondary mt-0.5">{order?.restaurant_name}</p>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 rounded-lg text-nexSecondary hover:text-nexPrimary hover:bg-nexBorder transition-colors"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Scrollable Body */}
      <div className="flex-1 overflow-y-auto p-5 space-y-6">
        {loading ? (
          <div className="py-20 flex flex-col items-center justify-center space-y-3 text-nexSecondary text-xs">
            <div className="w-6 h-6 border-2 border-nexCyan border-t-transparent rounded-full animate-spin" />
            <span>Carregando detalhes do pedido e histórico...</span>
          </div>
        ) : (
          <>
            {/* Attention Index & Deterministic Rules */}
            <div className="p-4 rounded-xl bg-nexBg border border-nexBorder space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-nexSecondary uppercase tracking-wider font-mono">
                  Índice de Atenção Operacional
                </span>
                <span
                  className={`text-xs px-2 py-0.5 rounded font-mono font-bold ${
                    score >= 60
                      ? 'bg-nexRed/20 text-nexRed border border-nexRed/40'
                      : score >= 30
                      ? 'bg-nexYellow/20 text-nexYellow border border-nexYellow/40'
                      : 'bg-nexGreen/20 text-nexGreen border border-nexGreen/40'
                  }`}
                >
                  {score}/100 · {score >= 60 ? 'ALTO RISCO' : score >= 30 ? 'MÉDIO' : 'BAIXO'}
                </span>
              </div>

              {/* Signals list */}
              {signals.length > 0 ? (
                <div className="space-y-1.5 pt-1">
                  <p className="text-[11px] text-nexSecondary/80">Sinais detectados por lógica determinística:</p>
                  <ul className="space-y-1">
                    {signals.map((sig, idx) => (
                      <li key={idx} className="flex items-start space-x-2 text-xs text-nexPrimary/90">
                        <AlertTriangle className="w-3.5 h-3.5 text-nexYellow shrink-0 mt-0.5" />
                        <span>{sig}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : (
                <p className="text-xs text-nexGreen flex items-center space-x-1.5">
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Pedido dentro da janela normal de operação.</span>
                </p>
              )}
            </div>

            {/* Operational Context Summary Grid */}
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="p-3 rounded-lg bg-nexSurfaceHover border border-nexBorder space-y-1">
                <div className="flex items-center space-x-1.5 text-nexSecondary">
                  <Clock className="w-3.5 h-3.5" />
                  <span>Horário Prometido</span>
                </div>
                <p className="font-mono font-semibold text-nexPrimary">
                  {order ? formatDateTime(order.promised_at) : '—'}
                </p>
              </div>

              <div className="p-3 rounded-lg bg-nexSurfaceHover border border-nexBorder space-y-1">
                <div className="flex items-center space-x-1.5 text-nexSecondary">
                  <Bike className="w-3.5 h-3.5" />
                  <span>Entregador</span>
                </div>
                <p className="font-semibold text-nexPrimary">
                  {order?.courier_assigned ? (
                    <span className="text-nexGreen">Alocado</span>
                  ) : (
                    <span className="text-nexRed">Não alocado</span>
                  )}
                </p>
              </div>

              <div className="p-3 rounded-lg bg-nexSurfaceHover border border-nexBorder space-y-1">
                <div className="flex items-center space-x-1.5 text-nexSecondary">
                  <Store className="w-3.5 h-3.5" />
                  <span>Fila no Restaurante</span>
                </div>
                <p className="font-mono font-semibold text-nexPrimary">
                  {order?.restaurant_backlog} pedidos na fila
                </p>
              </div>

              <div className="p-3 rounded-lg bg-nexSurfaceHover border border-nexBorder space-y-1">
                <div className="flex items-center space-x-1.5 text-nexSecondary">
                  <Shield className="w-3.5 h-3.5" />
                  <span>Distância</span>
                </div>
                <p className="font-mono font-semibold text-nexPrimary">
                  {order?.distance_km} km até cliente
                </p>
              </div>
            </div>

            {/* Customer Notes (Untrusted Data Warning) */}
            {order?.customer_notes && (
              <div className="p-3 rounded-lg bg-nexSurfaceHover/50 border border-nexBorder space-y-1 text-xs">
                <span className="text-[10px] text-nexSecondary uppercase tracking-wider font-mono">
                  Observação do Cliente (Dado Não Confiável)
                </span>
                <p className="text-nexPrimary italic bg-nexBg/60 p-2 rounded border border-nexBorder/50 font-mono text-[11px]">
                  "{order.customer_notes}"
                </p>
              </div>
            )}

            {/* Timeline of Order Events */}
            <div className="space-y-3">
              <span className="text-xs font-semibold text-nexSecondary uppercase tracking-wider font-mono">
                Linha do Tempo de Eventos
              </span>
              <div className="space-y-3 relative before:absolute before:inset-0 before:left-2 before:w-0.5 before:bg-nexBorder">
                {events.map((ev) => (
                  <div key={ev.id} className="relative flex items-start space-x-3 text-xs pl-6">
                    <span className="absolute left-1 top-1.5 w-2.5 h-2.5 rounded-full bg-nexCyan ring-4 ring-nexSurface" />
                    <div className="flex-1 bg-nexBg p-2.5 rounded-lg border border-nexBorder">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-nexPrimary">
                          {eventLabel(ev.event_type)}
                        </span>
                        <span className="font-mono text-[10px] text-nexSecondary">
                          {formatDateTime(ev.timestamp)}
                        </span>
                      </div>
                      {Object.keys(ev.details).length > 0 && (
                        <details className="text-[11px] text-nexSecondary mt-1">
                          <summary className="cursor-pointer">Detalhes técnicos</summary>
                          <pre className="mt-1 whitespace-pre-wrap break-all">{JSON.stringify(ev.details, null, 2)}</pre>
                        </details>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* AI Agent Section */}
            <div className="p-4 rounded-xl border border-nexCyan/30 bg-gradient-to-b from-nexCyan/5 to-transparent space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Sparkles className="w-4 h-4 text-nexCyan" />
                  <span className="text-xs font-bold text-nexPrimary uppercase tracking-wider font-mono">
                    Triagem com Agente Gemini
                  </span>
                </div>
                {status && (
                  <span
                    className={`text-[10px] px-2 py-0.5 rounded-full font-mono font-semibold uppercase ${
                      status === 'proposed'
                        ? 'bg-nexYellow/20 text-nexYellow border border-nexYellow/40'
                        : status === 'approved' || status === 'executed'
                        ? 'bg-nexGreen/20 text-nexGreen border border-nexGreen/40'
                        : status === 'failed'
                        ? 'bg-nexRed/20 text-nexRed border border-nexRed/40'
                        : 'bg-nexCyan/20 text-nexCyan border border-nexCyan/40 animate-pulse'
                    }`}
                  >
                    {incidentStatusLabels[status]}
                  </span>
                )}
              </div>

              {/* State 1: Ready to Analyze (or Re-analyze) */}
              {(!status || status === 'detected' || (status === 'failed' && !actionFailed)) && (
                <div className="space-y-3">
                  <p className="text-xs text-nexSecondary leading-relaxed">
                    Inicie a triagem para consultar o pedido, conferir políticas e receber uma recomendação.
                  </p>
                  {status === 'failed' && incident?.error_message && (
                    <div className="p-2.5 rounded-lg bg-nexRed/10 border border-nexRed/30 text-xs text-nexRed">
                      {incident.error_message}
                    </div>
                  )}
                  <button
                    onClick={() => order && onAnalyze(order.id)}
                    disabled={isAnalyzing}
                    className="w-full py-2.5 px-4 rounded-lg bg-nexCyan hover:bg-nexCyan/90 text-nexBg font-semibold text-xs flex items-center justify-center space-x-2 transition-all shadow-md shadow-nexCyan/20 disabled:opacity-50"
                  >
                    <Sparkles className={`w-4 h-4 ${isAnalyzing ? 'animate-spin' : ''}`} />
                    <span>{isAnalyzing ? 'Iniciando triagem...' : 'Analisar com IA'}</span>
                  </button>
                </div>
              )}

              {/* State 2: Analyzing active */}
              {status === 'analyzing' && (
                <div role="status" className="py-6 flex flex-col items-center justify-center space-y-2 text-center">
                  <div className="w-7 h-7 border-2 border-nexCyan border-t-transparent rounded-full animate-spin" />
                  <p className="text-xs font-semibold text-nexPrimary">Triagem pendente</p>
                  <p className="text-[11px] text-nexSecondary max-w-xs">
                    {incident?.error_message || 'Aguardando confirmação ou resultado da triagem.'}
                  </p>
                </div>
              )}

              {analysisSource && status !== 'analyzing' && (
                <p className="text-[11px] text-nexSecondary">
                  Triagem via {analysisSource === 'n8n_workflow' ? 'n8n (WF01)' :
                    analysisSource === 'local_agent_fallback' ? 'Gemini direto (fallback local)' : analysisSource}
                </p>
              )}

              {/* State 3: Proposal Received -> Human Supervisor Decisions */}
              {status === 'proposed' && incident?.agent_result && (
                <div className="space-y-4 pt-1">
                  {/* Summary */}
                  <div className="p-3 rounded-lg bg-nexBg border border-nexBorder space-y-1.5">
                    <span className="text-[10px] text-nexSecondary uppercase tracking-wider font-mono">
                      Resumo da Investigação
                    </span>
                    <p className="text-xs text-nexPrimary leading-relaxed">
                      {operatorText(incident.agent_result.summary)}
                    </p>
                  </div>

                  {/* Evidence Table */}
                  {incident.agent_result.evidence.length > 0 && (
                    <div className="space-y-1.5">
                      <span className="text-[10px] text-nexSecondary uppercase tracking-wider font-mono">
                        Evidências da triagem
                      </span>
                      <div className="space-y-1">
                        {incident.agent_result.evidence.map((ev, i) => (
                          <div key={i} className="p-2 rounded bg-nexBg/80 border border-nexBorder/60 text-xs">
                            <span className="text-nexSecondary">{operatorText(ev.finding)}</span>
                            <details className="mt-1 text-[11px] text-nexSecondary">
                              <summary className="cursor-pointer">Fonte da evidência</summary>
                              <code className="text-nexCyan">{ev.source}.{ev.field}</code>
                            </details>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Recommendation Tag */}
                  <div className="p-3 rounded-lg bg-nexYellow/10 border border-nexYellow/30 flex items-center justify-between text-xs">
                    <div>
                      <span className="text-[10px] text-nexYellow font-mono uppercase tracking-wider block">
                        Ação Proposta pelo Agente
                      </span>
                      <span className="font-mono font-bold text-nexPrimary">
                        {actionLabels[incident.agent_result.recommended_action]}
                      </span>
                    </div>
                    <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-nexYellow/20 text-nexYellow">
                      Prioridade: {priorityLabel(incident.agent_result.priority)}
                    </span>
                  </div>

                  {/* Operator Approval / Rejection Controls */}
                  <div className="space-y-2 pt-2 border-t border-nexBorder/60">
                    <p className="text-[11px] text-nexSecondary font-medium">
                      Supervisão Humana Obrigatória:
                    </p>
                    <div className="grid grid-cols-2 gap-3">
                      <button
                        onClick={() => onDecision(incident.id, 'approve')}
                        disabled={isDeciding}
                        className="py-2 px-3 rounded-lg bg-nexGreen hover:bg-nexGreen/90 text-nexBg font-semibold text-xs flex items-center justify-center space-x-1.5 transition-all shadow-sm shadow-nexGreen/20 disabled:opacity-50"
                      >
                        <Check className="w-4 h-4" />
                        <span>Aprovar Ação</span>
                      </button>

                      <button
                        onClick={() => setShowRejectModal(true)}
                        disabled={isDeciding}
                        className="py-2 px-3 rounded-lg bg-nexSurfaceHover hover:bg-nexRed/20 text-nexRed border border-nexRed/40 font-semibold text-xs flex items-center justify-center space-x-1.5 transition-all disabled:opacity-50"
                      >
                        <Ban className="w-4 h-4" />
                        <span>Rejeitar</span>
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* State 4: Approved / Executed -> Proof & Nature of Action */}
              {actionFailed && (
                <div role="alert" className="p-3 rounded-lg bg-nexRed/10 border border-nexRed/30 text-xs text-nexRed">
                  {incident?.error_message || 'Falha ao executar a ação aprovada.'}
                </div>
              )}
              {actionPending && (
                <p role="status" className="text-xs text-nexYellow">
                  {incident?.error_message || 'Ação aprovada. Aguardando confirmação da execução.'}
                </p>
              )}
              {(status === 'executed' || ticket) && (
                <div className="p-4 rounded-xl bg-nexGreen/10 border border-nexGreen/30 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2 text-nexGreen">
                      <CheckCircle2 className="w-5 h-5" />
                      <span className="font-semibold text-xs">Supervisão Humana Concluída</span>
                    </div>

                    {/* Action Nature Badge (Fix Prioridade 8) */}
                    <span className={`text-[10px] font-mono px-2 py-0.5 rounded font-semibold ${
                      ticket
                        ? 'bg-nexGreen/20 text-nexGreen border border-nexGreen/40'
                        : 'bg-nexCyan/20 text-nexCyan border border-nexCyan/40'
                    }`}>
                      {ticket
                        ? 'Chamado fictício registrado'
                        : 'Ação Simulada (Sem impacto externo)'}
                    </span>
                  </div>
                  
                  {ticket ? (
                    <>
                      <p className="text-xs text-nexSecondary leading-relaxed">
                        O chamado fictício aprovado pelo operador foi registrado no banco local.
                      </p>
                      <div className="p-3 rounded-lg bg-nexBg border border-nexBorder space-y-1.5 text-xs">
                        <div className="flex items-center justify-between font-mono">
                          <span className="text-nexCyan font-bold flex items-center space-x-1">
                            <Ticket className="w-3.5 h-3.5 mr-1" />
                            {ticket.id}
                          </span>
                          <span className="text-nexSecondary text-[11px]">{categoryLabel(ticket.category)} · {priorityLabel(ticket.priority)}</span>
                        </div>
                        <p className="text-nexPrimary text-[11px]">{operatorText(ticket.description)}</p>
                        <span className="text-[10px] text-nexSecondary font-mono block">
                          Chamado criado via {ticketSource === 'WF02_n8n_executor' ? 'n8n (WF02)' :
                            ticketSource === 'WF02_LocalRunner' ? 'executor local (fallback)' : ticketSource}
                        </span>
                      </div>
                    </>
                  ) : (
                    <div className="p-3 rounded-lg bg-nexBg border border-nexBorder space-y-1.5 text-xs">
                      <span className="text-[10px] text-nexCyan uppercase font-mono font-semibold block">
                        {incident?.agent_result?.recommended_action === 'DRAFT_CUSTOMER_MESSAGE'
                          ? 'Comunicação com Cliente Registrada (Simulação)'
                          : 'Ocorrência Encerrada sem Ação Externa (Simulação)'}
                      </span>
                      <span className="text-[11px] text-nexSecondary">Registrado pelo Nex em modo simulado.</span>
                      <p className="text-xs text-nexSecondary leading-relaxed">
                        {incident?.agent_result?.recommended_action === 'DRAFT_CUSTOMER_MESSAGE'
                          ? `A mensagem informativa foi aprovada pelo operador e persistida na trilha de auditoria para o ambiente demonstrativo (sem disparo real de SMS/WhatsApp por restrição de segurança): "${operatorText(incident.agent_result.operator_message)}".`
                          : 'O operador confirmou o encerramento do incidente sem abertura de chamado interno.'}
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* State 5: Rejected */}
              {status === 'rejected' && (
                <div className="p-3 rounded-lg bg-nexRed/10 border border-nexRed/30 text-xs text-nexRed space-y-1">
                  <div className="flex items-center space-x-1.5 font-semibold">
                    <Ban className="w-4 h-4" />
                    <span>Ação Rejeitada pelo Operador</span>
                  </div>
                  <p className="text-[11px] text-nexSecondary">
                    Nenhuma alteração foi executada. O incidente foi encerrado sem abertura de ticket.
                  </p>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {/* Rejection Modal */}
      {showRejectModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-nexSurface border border-nexBorder rounded-xl max-w-sm w-full p-5 space-y-4 shadow-2xl">
            <h3 className="font-bold text-sm text-nexPrimary">Justificativa da Rejeição</h3>
            <p className="text-xs text-nexSecondary">
              Informe o motivo pelo qual você está rejeitando a recomendação do agente Gemini:
            </p>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Ex: Contatei o restaurante diretamente por telefone e o pedido já saiu."
              className="w-full h-24 bg-nexBg border border-nexBorder rounded-lg p-2.5 text-xs text-nexPrimary placeholder:text-nexSecondary/60 focus:outline-none focus:border-nexCyan/60"
            />
            <div className="flex justify-end space-x-2">
              <button
                onClick={() => setShowRejectModal(false)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium text-nexSecondary hover:text-nexPrimary hover:bg-nexSurfaceHover"
              >
                Cancelar
              </button>
              <button
                onClick={() => {
                  if (incident) {
                    onDecision(incident.id, 'reject');
                    setShowRejectModal(false);
                  }
                }}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-nexRed hover:bg-nexRed/90 text-white"
              >
                Confirmar Rejeição
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
