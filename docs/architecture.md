# Arquitetura e Engenharia de Software — Nex

## 1. Visão Geral da Arquitetura

O **Nex** adota uma arquitetura em camadas orientada a eventos para garantir rastreabilidade, separação clara de responsabilidades e supervisão humana estrita.

```mermaid
flowchart TD
    subgraph Frontend["Camada de Apresentação (React + TypeScript)"]
        UI[Dashboard do Operador]
        KPI[Cards de KPIs]
        Table[Tabela de Pedidos & Filtros]
        Drawer[Drawer de Incidente & Análise]
    end

    subgraph Backend["Camada de Negócio & Persistência (FastAPI)"]
        Engine[Motor de Risco Determinístico]
        API_Public[Rotas Públicas do Operador]
        API_Internal[Rotas Internas Autenticadas]
        DB[(SQLite - WAL Mode)]
        Repo[Camada de Repositórios & Idempotência]
    end

    subgraph Automation["Camada de Orquestração & IA"]
        N8N_WF01[n8n WF01 - Triagem Operacional]
        N8N_WF02[n8n WF02 - Execução de Ação]
        Gemini[Google Gemini via Structured Output]
    end

    UI --> API_Public
    API_Public --> Engine
    API_Public --> Repo
    Repo --> DB

    API_Public -->|Trigger Assíncrono| N8N_WF01
    N8N_WF01 -->|GET /context| API_Internal
    N8N_WF01 -->|Tool: get_operations_policy| API_Internal
    N8N_WF01 --> Gemini
    N8N_WF01 -->|POST /analyses/result| API_Internal

    Drawer -->|Aprovação do Operador| API_Public
    API_Public -->|Trigger de Execução| N8N_WF02
    N8N_WF02 -->|GET /authorization| API_Internal
    N8N_WF02 -->|POST /mock-tickets| API_Internal
```

---

## 2. Princípios de Separação de Responsabilidades

| Componente | Responsabilidade | O que NÃO faz |
|---|---|---|
| **Motor de Risco** | Calcula o Índice de Atenção Operacional (0–100) por regras determinísticas auditáveis. | Não usa LLM, não chuta probabilidades de cancelamento. |
| **Agente Gemini** | Analisa fatos, correlaciona eventos com políticas operacionais homologadas e propõe ações. | Não altera scores, não executa ações sem aprovação, não tem ferramentas de escrita direta. |
| **n8n** | Orquestra webhooks, repetições, chamadas de ferramentas e fluxo de execução. | Não armazena estado de domínio definitivo; tudo é persistido e auditado na API. |
| **Operador Humano** | Avalia o resumo, evidências e hipóteses da IA antes de autorizar qualquer abertura de ticket. | Não precisa alternar entre múltiplos sistemas para realizar a triagem. |

---

## 3. Fluxo de Vida de um Incidente

```mermaid
stateDiagram-v2
    [*] --> detected: Motor de Risco detecta anomalia
    detected --> analyzing: Operador clica em "Analisar com IA"
    analyzing --> proposed: Agente Gemini devolve recomendação validada
    analyzing --> failed: Timeout, erro de rede ou validação inválida
    
    proposed --> rejected: Operador rejeita recomendação
    proposed --> approved: Operador aprova ação recomendada
    
    approved --> executing: Workflow 02 acionado
    executing --> executed: Ticket fictício criado com idempotência
    executing --> failed: Falha na criação do ticket
    
    rejected --> [*]
    executed --> [*]
```

---

## 4. Garantias de Idempotência e Segurança
- **Chave de Serviço:** Endpoints internos sob `/api/internal/*` exigem o cabeçalho `X-Internal-Key`.
- **Idempotência de Tickets:** Ao receber uma solicitação de criação de ticket para um mesmo `incident_id`, a API retorna o registro já existente sem duplicidade.
- **Defesa contra Injeção de Prompt:** O texto inserido por clientes em pedidos é tratado rigorosamente como dado não confiável, sendo isolado no prompt do modelo e validado no backend.

