import React, { useEffect, useState } from 'react';
import { Policy } from '../types';
import { fetchPolicies } from '../api';
import { actionLabels, categoryLabel, operatorText } from '../labels';

export const PoliciesView: React.FC = () => {
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetchPolicies()
      .then(setPolicies)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  return (
    <section className="space-y-6 max-w-5xl">
      <header className="space-y-2">
        <h2 className="text-xl font-semibold text-nexPrimary">Políticas operacionais</h2>
        <p className="text-sm text-nexSecondary leading-relaxed">
          Diretrizes fictícias que orientam a análise e as recomendações do agente.
        </p>
      </header>

      {loading ? (
        <p role="status" className="py-8 text-sm text-nexSecondary">Carregando políticas...</p>
      ) : error ? (
        <p role="alert" className="p-4 rounded-lg border border-nexRed/30 text-sm text-nexRed">
          Não foi possível carregar as políticas. Confira a conexão com o Nex e atualize a página.
        </p>
      ) : policies.length === 0 ? (
        <p className="py-8 text-sm text-nexSecondary">Nenhuma política disponível.</p>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {policies.map((policy) => (
            <article key={policy.code} className="min-w-0 flex flex-col rounded-xl border border-nexBorder bg-nexSurface overflow-hidden">
              <div className="p-5 space-y-4 flex-1">
                <p className="text-xs text-nexCyan font-medium">{categoryLabel(policy.category)}</p>
                <div className="space-y-2">
                  <h3 className="text-base font-semibold leading-snug text-nexPrimary">{policy.title}</h3>
                  <p className="text-sm leading-relaxed text-nexSecondary">{operatorText(policy.summary)}</p>
                </div>
                <details className="text-sm text-nexSecondary">
                  <summary className="cursor-pointer text-nexPrimary focus-visible:outline focus-visible:outline-2 focus-visible:outline-nexCyan">
                    Consultar diretriz completa
                  </summary>
                  <p className="pt-3 leading-relaxed break-words">{operatorText(policy.content)}</p>
                </details>
              </div>
              <footer className="p-5 border-t border-nexBorder space-y-3">
                <div className="space-y-1">
                  <p className="text-xs text-nexSecondary">Ação recomendada</p>
                  <p className="text-sm font-medium text-nexPrimary">{actionLabels[policy.recommended_action]}</p>
                </div>
                <p className="text-xs text-nexSecondary font-mono break-words">{policy.code} · {policy.version}</p>
              </footer>
            </article>
          ))}
        </div>
      )}
    </section>
  );
};
