import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Header } from './components/Header';
import { Sidebar, NavTab } from './components/Sidebar';
import { KpiCards } from './components/KpiCards';
import { OrderTable } from './components/OrderTable';
import { OrderDrawer } from './components/OrderDrawer';
import { AuditView } from './components/AuditView';
import { PoliciesView } from './components/PoliciesView';
import {
  fetchHealth, fetchSummary, fetchOrders,
  fetchOrderDetail, analyzeOrder, sendDecision,
  resetDemo, OrderDetailResponse
} from './api';
import { OrderListItem, SummaryKPIs } from './types';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<NavTab>('overview');
  const [apiStatus, setApiStatus] = useState<'online' | 'offline' | 'checking'>('checking');
  const [summary, setSummary] = useState<SummaryKPIs | null>(null);
  const [orders, setOrders] = useState<OrderListItem[]>([]);
  const [loadingOrders, setLoadingOrders] = useState(true);

  const [ordersError, setOrdersError] = useState(false);
  const mainRequest = useRef(0);

  // Filters
  const [statusFilter, setStatusFilter] = useState('');
  const [riskFilter, setRiskFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  // Drawer & Selection
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null);
  const [drawerData, setDrawerData] = useState<OrderDetailResponse | null>(null);
  const [drawerLoading, setDrawerLoading] = useState(false);

  // Async Actions state
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isDeciding, setIsDeciding] = useState(false);
  const [isResetting, setIsResetting] = useState(false);

  // Carregar dados principais
  const loadMainData = useCallback(async () => {
    const requestId = ++mainRequest.current;
    try {
      const [health, sum, ords] = await Promise.all([
        fetchHealth().catch(() => null),
        fetchSummary().catch(() => null),
        fetchOrders({
          status: statusFilter,
          risk: currentTab === 'incidents' && !riskFilter ? 'high' : riskFilter,
          search: searchQuery
        }).catch(() => null)
      ]);

      if (requestId !== mainRequest.current) return;
      setApiStatus(health?.status === 'healthy' ? 'online' : 'offline');
      if (sum) setSummary(sum);
      setOrdersError(ords === null);
      setOrders(ords ?? []);
    } catch (err) {
      console.error('Erro ao atualizar dados principais:', err);
      setApiStatus('offline');
    } finally {
      if (requestId === mainRequest.current) setLoadingOrders(false);
    }
  }, [statusFilter, riskFilter, searchQuery, currentTab]);

  useEffect(() => {
    loadMainData();
  }, [loadMainData]);

  // Polling automático leve a cada 3 segundos (atualiza tabela e drawer aberto)
  useEffect(() => {
    const timer = setInterval(() => {
      loadMainData();
      if (selectedOrderId) {
        fetchOrderDetail(selectedOrderId)
          .then((updated) => {
            setDrawerData(updated);
            if (updated.incident?.status !== 'analyzing') {
              setIsAnalyzing(false);
            }
          })
          .catch(() => null);
      }
    }, 3000);
    return () => clearInterval(timer);
  }, [loadMainData, selectedOrderId]);

  // Carregar detalhe quando um pedido for selecionado
  const handleSelectOrder = async (orderId: string) => {
    setSelectedOrderId(orderId);
    setDrawerLoading(true);
    try {
      const detail = await fetchOrderDetail(orderId);
      setDrawerData(detail);
    } catch (err) {
      console.error(err);
    } finally {
      setDrawerLoading(false);
    }
  };

  const handleCloseDrawer = () => {
    setSelectedOrderId(null);
    setDrawerData(null);
  };

  // Disparar análise com IA
  const handleAnalyze = async (orderId: string) => {
    setIsAnalyzing(true);
    try {
      await analyzeOrder(orderId);
      // Atualizar dados imediatos
      const updated = await fetchOrderDetail(orderId);
      setDrawerData(updated);
      loadMainData();

      // Polling rápido a cada 2s para observar término do job
      let attempts = 0;
      const pollJob = setInterval(async () => {
        attempts++;
        const curr = await fetchOrderDetail(orderId).catch(() => null);
        if (curr) {
          setDrawerData(curr);
          if (curr.incident?.status !== 'analyzing' || attempts >= 35) {
            clearInterval(pollJob);
            setIsAnalyzing(false);
            loadMainData();
          }
        }
      }, 2000);
    } catch (err: any) {
      alert(err.message || 'Erro ao iniciar análise com IA');
      setIsAnalyzing(false);
    }
  };

  // Processar Decisão Humana (Aprovar / Rejeitar)
  const handleDecision = async (incidentId: string, decision: 'approve' | 'reject') => {
    setIsDeciding(true);
    try {
      await sendDecision(incidentId, decision);
      if (selectedOrderId) {
        const updated = await fetchOrderDetail(selectedOrderId);
        setDrawerData(updated);
      }
      loadMainData();
    } catch (err: any) {
      alert(err.message || 'Erro ao processar decisão');
    } finally {
      setIsDeciding(false);
    }
  };

  // Reiniciar Demo
  const handleResetDemo = async () => {
    setIsResetting(true);
    try {
      await resetDemo();
      handleCloseDrawer();
      await loadMainData();
    } catch (err) {
      console.error(err);
      alert('Erro ao reiniciar banco de demonstração.');
    } finally {
      setIsResetting(false);
    }
  };

  return (
    <div className="min-h-screen bg-nexBg text-nexPrimary flex flex-col font-sans">
      {/* Top Header */}
      <Header
        apiStatus={apiStatus}
        onReset={handleResetDemo}
        isResetting={isResetting}
      />

      {/* Main Container */}
      <div className="flex-1 flex overflow-hidden">
        {/* Navigation Sidebar */}
        <Sidebar
          currentTab={currentTab}
          onTabChange={setCurrentTab}
          highRiskCount={summary?.high_risk_orders ?? 0}
          pendingApprovalsCount={summary?.pending_approvals ?? 0}
        />

        {/* Content View */}
        <main className="flex-1 min-w-0 overflow-y-auto p-6 max-w-7xl mx-auto w-full">
          {ordersError && (currentTab === 'overview' || currentTab === 'incidents') && (
            <p role="alert" className="mb-4 rounded-lg border border-nexRed/30 p-3 text-sm text-nexRed">
              Não foi possível carregar os pedidos. Verifique se o Nex está em execução.
            </p>
          )}
          {currentTab === 'overview' && (
            <>
              <KpiCards summary={summary} loading={loadingOrders} />
              {!ordersError && <OrderTable
                orders={orders}
                loading={loadingOrders}
                selectedOrderId={selectedOrderId}
                onSelectOrder={handleSelectOrder}
                statusFilter={statusFilter}
                onStatusFilterChange={setStatusFilter}
                riskFilter={riskFilter}
                onRiskFilterChange={setRiskFilter}
                searchQuery={searchQuery}
                onSearchQueryChange={setSearchQuery}
              />}
            </>
          )}

          {currentTab === 'incidents' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-base font-bold text-nexPrimary font-mono">
                    Incidentes & Ocorrências em Triagem
                  </h2>
                  <p className="text-xs text-nexSecondary mt-0.5">
                    Filtro rápido focado em pedidos com atenção crítica (Score ≥ 60) ou propostas pendentes de aprovação.
                  </p>
                </div>
              </div>
              {!ordersError && <OrderTable
                orders={orders}
                loading={loadingOrders}
                selectedOrderId={selectedOrderId}
                onSelectOrder={handleSelectOrder}
                statusFilter={statusFilter}
                onStatusFilterChange={setStatusFilter}
                riskFilter={riskFilter || 'high'}
                onRiskFilterChange={setRiskFilter}
                searchQuery={searchQuery}
                onSearchQueryChange={setSearchQuery}
              />}
            </div>
          )}

          {currentTab === 'audit' && <AuditView />}

          {currentTab === 'policies' && <PoliciesView />}
        </main>
      </div>

      {/* Order & Incident Details Drawer */}
      {selectedOrderId && (
        <OrderDrawer
          data={drawerData}
          loading={drawerLoading}
          onClose={handleCloseDrawer}
          onAnalyze={handleAnalyze}
          onDecision={handleDecision}
          isAnalyzing={isAnalyzing}
          isDeciding={isDeciding}
        />
      )}
    </div>
  );
};

