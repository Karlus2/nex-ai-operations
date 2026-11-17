import React from 'react';
import { LayoutDashboard, AlertTriangle, FileText, BookOpen } from 'lucide-react';

export type NavTab = 'overview' | 'incidents' | 'audit' | 'policies';

interface SidebarProps {
  currentTab: NavTab;
  onTabChange: (tab: NavTab) => void;
  highRiskCount: number;
  pendingApprovalsCount: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onTabChange,
  highRiskCount,
  pendingApprovalsCount
}) => {
  const navItems = [
    {
      id: 'overview' as NavTab,
      label: 'Visão Geral',
      icon: LayoutDashboard,
      badge: highRiskCount > 0 ? highRiskCount : undefined,
      badgeColor: 'bg-nexRed/20 text-nexRed border border-nexRed/40'
    },
    {
      id: 'incidents' as NavTab,
      label: 'Incidentes',
      icon: AlertTriangle,
      badge: pendingApprovalsCount > 0 ? pendingApprovalsCount : undefined,
      badgeColor: 'bg-nexYellow/20 text-nexYellow border border-nexYellow/40'
    },
    {
      id: 'audit' as NavTab,
      label: 'Auditoria & Logs',
      icon: FileText
    },
    {
      id: 'policies' as NavTab,
      label: 'Políticas operacionais',
      icon: BookOpen
    }
  ];

  return (
    <aside className="w-64 border-r border-nexBorder bg-nexSurface/40 flex flex-col justify-between p-4 shrink-0">
      <div className="space-y-1">
        <p className="px-3 py-2 text-[10px] font-semibold text-nexSecondary tracking-wider uppercase font-mono">
          Navegação Operacional
        </p>

        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id)}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                isActive
                  ? 'bg-nexCyan/10 text-nexCyan border border-nexCyan/30 shadow-sm'
                  : 'text-nexSecondary hover:text-nexPrimary hover:bg-nexSurfaceHover'
              }`}
            >
              <div className="flex items-center space-x-3">
                <Icon className={`w-4 h-4 ${isActive ? 'text-nexCyan' : 'text-nexSecondary'}`} />
                <span>{item.label}</span>
              </div>
              {item.badge !== undefined && (
                <span className={`text-[10px] px-2 py-0.5 rounded-full font-mono font-semibold ${item.badgeColor}`}>
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </aside>
  );
};

