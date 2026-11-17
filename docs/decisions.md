# Registros de Decisões de Arquitetura (ADR) — Nex

Este documento registra as decisões técnicas, justificativas e trade-offs adotados no desenvolvimento do **Nex**.

---

## ADR 01: Separação entre Heurística Determinística e Agente Generativo
- **Status:** Aceito
- **Contexto:** Em operações de delivery, saber se um pedido está em risco exige regras objetivas, baratas, auditáveis e com latência próxima de zero. O LLM não deve "adivinhar" se o pedido está atrasado ou inventar uma probabilidade estatística sem modelo calibrado.
- **Decisão:** O score de risco (Índice de Atenção Operacional, 0–100) é calculado puramente por regras determinísticas no backend (Python/FastAPI). O Gemini atua como analista de contexto e sintetizador de recomendações, sem alterar pedidos ou scores diretamente.
- **Consequências:** Regras auditáveis, baixo custo de tokens, zero alucinação no cálculo de prioridade.

---

## ADR 02: Human-in-the-Loop Obrigatório para Ações de Impacto
- **Status:** Aceito
- **Contexto:** Ações em sistemas operacionais (como abertura de chamados, notificações a clientes ou reembolsos) não devem ser executadas autonomamente pelo LLM sem supervisão.
- **Decisão:** O agente propõe a ação (`CREATE_INTERNAL_TICKET`, `DRAFT_CUSTOMER_MESSAGE`, `NO_ACTION`). Apenas um operador humano pode aprovar ou rejeitar a ação na interface. A execução é realizada pelo n8n via webhook autenticado e idempotente somente após a aprovação persistida no banco.
- **Consequências:** Risco operacional minimizado, conformidade com boas práticas de governança de IA.

---

## ADR 03: Persistência Leve com SQLite no MVP
- **Status:** Aceito
- **Contexto:** Necessidade de setup ágil, reprodutibilidade em qualquer máquina sem dependência de containers de banco pesados (PostgreSQL/MySQL).
- **Decisão:** Uso de SQLite com SQLAlchemy/SQLModel ou queries diretas Pydantic + SQLite.
- **Consequências:** Zero overhead de infraestrutura no MVP local, fácil restauração do seed determinístico.

---

## ADR 04: Orquestração de Fluxos com n8n Community
- **Status:** Aceito
- **Contexto:** Demonstrar automação de processos real de ponta a ponta que possa ser inspecionada visualmente e exportada em JSON para o repositório.
- **Decisão:** Utilização do n8n (Community) orquestrando o fluxo de triagem (`WF01`) com Gemini Chat Model e ferramentas HTTP, e o fluxo de ação executada (`WF02`).
- **Consequências:** Fluxos portáveis, auditáveis e visualizáveis pelos avaliadores.

---

## ADR 05: Atribuição de Operador vs Autenticação Criptográfica no Ambiente Demonstrativo Local
- **Status:** Aceito
- **Contexto:** A especificação P0 foca em um ambiente demonstrativo local com dados sintéticos operado em `localhost`. A criação de um sistema completo de autenticação OAuth2/JWT com RBAC adicionaria complexidade fora do escopo do MVP, enquanto tratar headers arbitrários como autenticação real seria uma falha conceitual de segurança.
- **Decisão:** O cabeçalho `X-Operator-Id` é estritamente tratado como metadado de atribuição de perfil local demonstrativo (`OperatorProfileAttribution`) para enriquecimento da trilha de auditoria e testes de múltiplos operadores. Ele passa por validação estrita de formato (slug alfanumérico) e, na ausência, assume `operator:default`. Em uma transição para produção, este metadado será extraído de tokens de sessão validados criptograficamente (JWT).
- **Consequências:** Transparência sobre as fronteiras de segurança do MVP, sem falsa sensação de proteção criptográfica, mantendo a rastreabilidade na auditoria.

---

## ADR 06: Bloqueio Estrito de Credenciais Padrão Inseguras
- **Status:** Aceito
- **Contexto:** Chaves padrão de desenvolvimento (ex: `nex_internal_dev_secret_replace_in_prod`) frequentemente permanecem ativas por descuido em ambientes de demonstração ou testes, abrindo vetores de ataque conhecidos.
- **Decisão:** O sistema bloqueia em tempo de execução o uso de segredos fracos conhecidos para rotas internas `/api/internal/*`, exigindo uma chave com alta entropia no `.env` e eliminando valores de fallback hardcoded nos arquivos de workflow do n8n.
- **Consequências:** Conformidade com padrões de segurança e proibição de credenciais padrão em todos os ambientes.
