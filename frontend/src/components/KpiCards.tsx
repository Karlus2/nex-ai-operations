import React from 'react';
import { Package, AlertCircle, Clock, CheckCircle2 } from 'lucide-react';
import { SummaryKPIs } from '../types';

interface KpiCardsProps {
  summary: SummaryKPIs | null;
  loading: boolean;
}

export const KpiCards: React.FC<KpiCardsProps> = ({ summary, loading }) => {
  const cards = [
    {
      title: 'Pedidos ativos',
      value: summary?.active_orders ?? 0,
      icon: Package,
      color: 'text-nexCyan',
      bgColor: 'bg-nexCyan/10 border-nexCyan/30',
      description: 'Criados, em preparo, prontos ou em rota'
    },
    {
      title: 'Pedidos em risco alto',
      value: summary?.high_risk_orders ?? 0,
      icon: AlertCircle,
      color: 'text-nexRed',
      bgColor: 'bg-nexRed/10 border-nexRed/30',
      description: 'Índice de atenção a partir de 60'
    },
    {
      title: 'Aguardando decisão',
      value: summary?.pending_approvals ?? 0,
      icon: Clock,
      color: 'text-nexYellow',
      bgColor: 'bg-nexYellow/10 border-nexYellow/30',
      description: 'Recomendações para revisar'
    },
    {
      title: 'Chamados criados',
      value: summary?.executed_actions ?? 0,
      icon: CheckCircle2,
      color: 'text-nexGreen',
      bgColor: 'bg-nexGreen/10 border-nexGreen/30',
      description: 'Chamados fictícios registrados'
    }
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      {cards.map((card, index) => {
        const Icon = card.icon;
        return (
          <div
            key={index}
            className="p-4 rounded-xl bg-nexSurface border border-nexBorder flex flex-col justify-between hover:border-nexBorder/80 transition-all shadow-sm"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-nexSecondary">{card.title}</span>
              <div className={`p-2 rounded-lg border ${card.bgColor} ${card.color}`}>
                <Icon className="w-4 h-4" />
              </div>
            </div>
            <div className="mt-3">
              <span className="text-2xl font-bold font-mono text-nexPrimary">
                {loading ? '—' : card.value}
              </span>
              <p className="text-[11px] text-nexSecondary/80 mt-0.5">{card.description}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
};

