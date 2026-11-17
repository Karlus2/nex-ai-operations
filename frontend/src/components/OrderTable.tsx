import React from 'react';
import { Search, ChevronRight, AlertCircle, CheckCircle, Clock, Bike, ShieldAlert } from 'lucide-react';
import { OrderListItem, OrderStatus, RiskLevel } from '../types';
import { orderStatusLabels, riskLabels } from '../labels';

interface OrderTableProps {
  orders: OrderListItem[];
  loading: boolean;
  selectedOrderId: string | null;
  onSelectOrder: (orderId: string) => void;
  statusFilter: string;
  onStatusFilterChange: (status: string) => void;
  riskFilter: string;
  onRiskFilterChange: (risk: string) => void;
  searchQuery: string;
  onSearchQueryChange: (query: string) => void;
}

export const OrderTable: React.FC<OrderTableProps> = ({
  orders,
  loading,
  selectedOrderId,
  onSelectOrder,
  statusFilter,
  onStatusFilterChange,
  riskFilter,
  onRiskFilterChange,
  searchQuery,
  onSearchQueryChange
}) => {
  const getStatusBadge = (status: OrderStatus) => {
    switch (status) {
      case 'preparing':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-md text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/30">
            <Clock className="w-3 h-3 mr-1" />
            {orderStatusLabels[status]}
          </span>
        );
      case 'ready':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-md text-xs font-medium bg-blue-500/10 text-blue-400 border border-blue-500/30">
            <CheckCircle className="w-3 h-3 mr-1" />
            {orderStatusLabels[status]}
          </span>
        );
      case 'picked_up':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-md text-xs font-medium bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
            <Bike className="w-3 h-3 mr-1" />
            {orderStatusLabels[status]}
          </span>
        );
      case 'delivered':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-md text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
            {orderStatusLabels[status]}
          </span>
        );
      case 'cancelled':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-md text-xs font-medium bg-red-500/10 text-red-400 border border-red-500/30">
            {orderStatusLabels[status]}
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-md text-xs font-medium bg-slate-500/10 text-slate-300 border border-slate-500/30">
            {orderStatusLabels[status]}
          </span>
        );
    }
  };

  const getRiskBadge = (score: number, level: RiskLevel) => {
    let colorClass = 'bg-nexGreen/10 text-nexGreen border-nexGreen/30';
    let barColor = 'bg-nexGreen';
    if (level === 'high') {
      colorClass = 'bg-nexRed/15 text-nexRed border-nexRed/40 font-semibold';
      barColor = 'bg-nexRed';
    } else if (level === 'medium') {
      colorClass = 'bg-nexYellow/15 text-nexYellow border-nexYellow/40';
      barColor = 'bg-nexYellow';
    }

    return (
      <div className="flex flex-col space-y-1 w-28">
        <div className="flex items-center justify-between text-xs">
          <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono border ${colorClass}`}>
            {riskLabels[level]}
          </span>
          <span className="font-mono font-bold text-nexPrimary text-xs">{score}/100</span>
        </div>
        <div className="w-full bg-nexBorder/50 h-1.5 rounded-full overflow-hidden">
          <div
            className={`h-full ${barColor} transition-all duration-300`}
            style={{ width: `${Math.min(100, score)}%` }}
          />
        </div>
      </div>
    );
  };

  const formatTime = (isoString: string) => {
    try {
      const dt = new Date(isoString);
      return dt.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="bg-nexSurface border border-nexBorder rounded-xl overflow-hidden shadow-sm flex flex-col">
      {/* Controls: Search & Filters */}
      <div className="p-4 border-b border-nexBorder flex flex-col md:flex-row gap-3 items-stretch md:items-center justify-between bg-nexSurface/60">
        {/* Search */}
        <div className="relative flex-1 max-w-sm">
          <Search className="w-4 h-4 text-nexSecondary absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            aria-label="Buscar pedido ou restaurante"
            placeholder="Buscar pedido ou restaurante"
            value={searchQuery}
            onChange={(e) => onSearchQueryChange(e.target.value)}
            className="w-full bg-nexBg border border-nexBorder rounded-lg pl-9 pr-3 py-1.5 text-xs text-nexPrimary placeholder:text-nexSecondary/60 focus:outline-none focus:border-nexCyan/60 transition-colors"
          />
        </div>

        {/* Filter Pills */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {/* Risk Filters */}
          <div className="flex rounded-lg border border-nexBorder p-0.5 bg-nexBg">
            {(['all', 'high', 'medium', 'low'] as const).map((r) => (
              <button
                key={r}
                onClick={() => onRiskFilterChange(r === 'all' ? '' : r)}
                aria-pressed={(riskFilter === '' && r === 'all') || riskFilter === r}
                className={`px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
                  (riskFilter === '' && r === 'all') || riskFilter === r
                    ? 'bg-nexSurfaceHover text-nexCyan font-semibold shadow-xs'
                    : 'text-nexSecondary hover:text-nexPrimary'
                }`}
              >
                {r === 'all' ? 'Todos os riscos' : riskLabels[r]}
              </button>
            ))}
          </div>

          {/* Status Dropdown */}
          <select
            aria-label="Filtrar por estado do pedido"
            value={statusFilter}
            onChange={(e) => onStatusFilterChange(e.target.value)}
            className="bg-nexBg border border-nexBorder rounded-lg px-2.5 py-1.5 text-xs text-nexSecondary focus:text-nexPrimary focus:outline-none focus:border-nexCyan/60"
          >
            <option value="">Todos os estados</option>
            {Object.entries(orderStatusLabels).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Table Content */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-nexSurfaceHover/50 text-nexSecondary font-mono text-[11px] uppercase tracking-wider border-b border-nexBorder">
            <tr>
              <th className="py-3 px-4 font-medium">Pedido</th>
              <th className="py-3 px-4 font-medium">Restaurante</th>
              <th className="py-3 px-4 font-medium">Status</th>
              <th className="py-3 px-4 font-medium">Prazo</th>
              <th className="py-3 px-4 font-medium">Entregador</th>
              <th className="py-3 px-4 font-medium">Índice de Atenção</th>
              <th className="py-3 px-4 font-medium">Motivos de atenção</th>
              <th className="py-3 px-4 font-medium text-right">Ação</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-nexBorder/60">
            {loading ? (
              <tr>
                <td colSpan={8} className="py-12 text-center text-nexSecondary">
                  <div className="flex flex-col items-center justify-center space-y-2">
                    <div className="w-6 h-6 border-2 border-nexCyan border-t-transparent rounded-full animate-spin" />
                    <span>Carregando dados operacionais...</span>
                  </div>
                </td>
              </tr>
            ) : orders.length === 0 ? (
              <tr>
                <td colSpan={8} className="py-12 text-center text-nexSecondary">
                  <div className="flex flex-col items-center justify-center space-y-2">
                    <ShieldAlert className="w-8 h-8 text-nexSecondary/60" />
                    <p className="font-medium text-nexPrimary">Nenhum pedido encontrado com estes filtros.</p>
                    <p className="text-xs">Tente ajustar a busca ou o nível de risco selecionado.</p>
                  </div>
                </td>
              </tr>
            ) : (
              orders.map((order) => {
                const isSelected = selectedOrderId === order.id;
                const isDemoTarget = order.id === 'NEX-1042';
                const score = order.incident?.risk_score ?? 0;
                const level = order.incident?.risk_level ?? 'low';
                const signals = order.incident?.risk_signals ?? [];

                return (
                  <tr
                    key={order.id}
                    onClick={() => onSelectOrder(order.id)}
                    className={`cursor-pointer transition-colors ${
                      isSelected
                        ? 'bg-nexCyan/10 border-l-2 border-l-nexCyan'
                        : isDemoTarget
                        ? 'bg-nexRed/5 hover:bg-nexRed/10 border-l-2 border-l-nexRed'
                        : 'hover:bg-nexSurfaceHover/60'
                    }`}
                  >
                    {/* ID */}
                    <td className="py-3 px-4 font-mono font-semibold text-nexPrimary">
                      <div className="flex items-center space-x-1.5">
                        <span>{order.id}</span>
                        {isDemoTarget && (
                          <span className="px-1.5 py-0.5 rounded text-[9px] bg-nexRed/20 text-nexRed border border-nexRed/40 font-mono">
                            DEMO
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Restaurant */}
                    <td className="py-3 px-4 text-nexPrimary font-medium truncate max-w-[180px]" title={order.restaurant_name}>
                      {order.restaurant_name}
                    </td>

                    {/* Status */}
                    <td className="py-3 px-4">
                      {getStatusBadge(order.status)}
                    </td>

                    {/* Promised ETA */}
                    <td className="py-3 px-4 font-mono text-nexSecondary" title={new Date(order.promised_at).toLocaleString('pt-BR')}>
                      {formatTime(order.promised_at)}
                    </td>

                    {/* Courier */}
                    <td className="py-3 px-4">
                      {order.courier_assigned ? (
                        <span className="inline-flex items-center text-nexGreen space-x-1">
                          <Bike className="w-3.5 h-3.5" />
                          <span>Alocado</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center text-nexRed space-x-1">
                          <AlertCircle className="w-3.5 h-3.5" />
                          <span>Pendente</span>
                        </span>
                      )}
                    </td>

                    {/* Attention / Risk Index */}
                    <td className="py-3 px-4">
                      {getRiskBadge(score, level)}
                    </td>

                    {/* Signals Summary */}
                    <td className="py-3 px-4 text-nexSecondary max-w-xs truncate" title={signals.join(' | ')}>
                      {signals.length > 0 ? (
                        <div className="flex items-center space-x-1.5">
                          <span className="w-1.5 h-1.5 rounded-full bg-nexYellow shrink-0" />
                          <span className="truncate">{signals[0]}</span>
                          {signals.length > 1 && (
                            <span className="text-[10px] text-nexSecondary/70 font-mono">
                              +{signals.length - 1}
                            </span>
                          )}
                        </div>
                      ) : (
                        <span className="text-nexSecondary/50">—</span>
                      )}
                    </td>

                    {/* Action */}
                    <td className="py-3 px-4 text-right">
                      <button
                        aria-label={`Ver pedido ${order.id}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectOrder(order.id);
                        }}
                        className="inline-flex items-center space-x-1 px-2.5 py-1 rounded text-xs font-medium bg-nexSurfaceHover hover:bg-nexBorder text-nexPrimary hover:text-nexCyan transition-colors"
                      >
                        <span>Ver pedido</span>
                        <ChevronRight className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Footer Count */}
      <div className="p-3 border-t border-nexBorder text-xs text-nexSecondary flex items-center justify-between bg-nexSurface/40">
        <span>{orders.length} {orders.length === 1 ? 'pedido encontrado' : 'pedidos encontrados'}</span>

      </div>
    </div>
  );
};

