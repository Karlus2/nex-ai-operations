import React, { useEffect, useState } from 'react';
import { ShieldCheck, User, Bot, Cpu, RefreshCw } from 'lucide-react';
import { AuditEvent } from '../types';
import { fetchAuditTrail } from '../api';
import { eventLabel } from '../labels';

export const AuditView: React.FC = () => {
  const [logs, setLogs] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);

  const loadLogs = async () => {
    try {
      setLoading(true);
      const data = await fetchAuditTrail(100);
      setLogs(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLogs();
  }, []);

  const getActorBadge = (actor: string) => {
    switch (actor.split(':', 1)[0]) {
      case 'operator':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-mono bg-nexCyan/15 text-nexCyan border border-nexCyan/30">
            <User className="w-3 h-3 mr-1" />
            OPERADOR
          </span>
        );
      case 'agent':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-mono bg-purple-500/15 text-purple-400 border border-purple-500/30">
            <Bot className="w-3 h-3 mr-1" />
            AGENTE GEMINI
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-mono bg-slate-500/15 text-slate-300 border border-slate-500/30">
            <Cpu className="w-3 h-3 mr-1" />
            SISTEMA
          </span>
        );
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-nexPrimary font-mono flex items-center space-x-2">
            <ShieldCheck className="w-4 h-4 text-nexCyan" />
            <span>Trilha de Auditoria & Execuções</span>
          </h2>
          <p className="text-xs text-nexSecondary mt-0.5">
            Histórico de decisões, análises e resultados registrados pelo Nex.
          </p>
        </div>

        <button
          onClick={loadLogs}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-nexSurfaceHover border border-nexBorder text-nexPrimary hover:bg-nexBorder transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Atualizar</span>
        </button>
      </div>

      {/* Audit Log Table */}
      <div className="bg-nexSurface border border-nexBorder rounded-xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-nexSurfaceHover/50 text-nexSecondary font-mono text-[11px] uppercase tracking-wider border-b border-nexBorder">
              <tr>
                <th className="py-3 px-4 font-medium">Data/Hora</th>
                <th className="py-3 px-4 font-medium">Incidente</th>
                <th className="py-3 px-4 font-medium">Ator</th>
                <th className="py-3 px-4 font-medium">Evento</th>
                <th className="py-3 px-4 font-medium">Correlation ID</th>
                <th className="py-3 px-4 font-medium">Dados técnicos</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-nexBorder/60 font-mono">
              {loading ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-nexSecondary font-sans">
                    Carregando eventos de auditoria...
                  </td>
                </tr>
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-nexSecondary font-sans">
                    Nenhum evento registrado ainda.
                  </td>
                </tr>
              ) : (
                logs.map((log) => (
                  <tr key={log.id} className="hover:bg-nexSurfaceHover/40 transition-colors">
                    <td className="py-2.5 px-4 text-nexSecondary text-[11px]">
                      {new Date(log.timestamp).toLocaleString('pt-BR')}
                    </td>
                    <td className="py-2.5 px-4 font-bold text-nexPrimary">{log.incident_id}</td>
                    <td className="py-2.5 px-4" title={log.actor}>{getActorBadge(log.actor)}</td>
                    <td className="py-2.5 px-4 text-nexPrimary text-[11px] font-sans font-medium">
                      {eventLabel(log.event_type)}
                    </td>
                    <td className="py-2.5 px-4 text-nexSecondary text-[10px]">
                      {log.correlation_id || '—'}
                    </td>
                    <td className="py-2.5 px-4 text-[10px] text-nexSecondary max-w-sm truncate">
                      {JSON.stringify(log.payload_redacted)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

