import React from 'react';
import { RotateCcw, Activity, ShieldCheck } from 'lucide-react';

interface HeaderProps {
  apiStatus: 'online' | 'offline' | 'checking';
  onReset: () => void;
  isResetting: boolean;
}

export const Header: React.FC<HeaderProps> = ({ apiStatus, onReset, isResetting }) => {
  return (
    <header className="h-16 border-b border-nexBorder bg-nexSurface/80 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-30">
      {/* Brand & Title */}
      <div className="flex items-center space-x-3">
        <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-nexCyan/20 to-nexCyan/5 border border-nexCyan/40 flex items-center justify-center text-nexCyan shadow-lg shadow-nexCyan/10">
          <Activity className="w-5 h-5" />
        </div>
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-lg font-bold tracking-tight text-nexPrimary font-mono">Nex</h1>
            <span className="text-xs px-2 py-0.5 rounded-full bg-nexCyan/10 text-nexCyan border border-nexCyan/30 font-medium">
              v1.0 MVP
            </span>
          </div>
          <p className="text-xs text-nexSecondary hidden sm:block">
            Copiloto de Triagem & Operações de Delivery
          </p>
        </div>
      </div>

      {/* Persistence Demo Chip (Exigência da Especificação) */}
      <div className="hidden md:flex items-center space-x-2 px-3 py-1 rounded-full bg-nexSurfaceHover border border-nexBorder text-xs text-nexSecondary">
        <ShieldCheck className="w-3.5 h-3.5 text-nexCyan" />
        <span>AMBIENTE DEMONSTRATIVO · DADOS SINTÉTICOS</span>
      </div>

      {/* Right Controls: Health Status & Reset Button */}
      <div className="flex items-center space-x-4">
        {/* Status Indicator */}
        <div className="flex items-center space-x-2 text-xs">
          <span
            className={`w-2 h-2 rounded-full ${
              apiStatus === 'online'
                ? 'bg-nexGreen animate-pulse shadow-sm shadow-nexGreen'
                : apiStatus === 'offline'
                ? 'bg-nexRed'
                : 'bg-nexYellow'
            }`}
          />
          <span className="text-nexSecondary hidden sm:inline">
            {apiStatus === 'online' ? 'API Online' : apiStatus === 'offline' ? 'API Offline' : 'Conectando...'}
          </span>
        </div>

        {/* Reset Demo Button */}
        <button
          onClick={onReset}
          disabled={isResetting}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-nexSurfaceHover hover:bg-nexBorder border border-nexBorder text-nexPrimary hover:text-white transition-all disabled:opacity-50"
          title="Restaura a base para os 53 pedidos e o caso NEX-1042"
        >
          <RotateCcw className={`w-3.5 h-3.5 text-nexSecondary ${isResetting ? 'animate-spin' : ''}`} />
          <span>{isResetting ? 'Restaurando...' : 'Reiniciar Demo'}</span>
        </button>
      </div>
    </header>
  );
};

