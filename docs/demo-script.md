# Roteiro de Demonstração em Vídeo (90 Segundos) — Nex

> **Objetivo:** Gravação rápida e objetiva para avaliação da trilha AI Builder do iFood.
> **Tempo Total:** 90 segundos (1 minuto e 30 segundos).

---

## Passo a Passo Cronometrado

### [00:00 - 00:15] Introdução & Problema Operacional
- **Ação:** Abra o painel integrado (`http://localhost:8000`) com `REQUIRE_N8N=true` e uma base de demonstração limpa.
- **Fala:** 
  > *"Olá! Este é o Nex, um copiloto de operações de delivery que desenvolvi para o processo seletivo de AI Builder do iFood. Em operações de alta escala, atrasos e gargalos de logística geram dezenas de ocorrências manuais. O Nex ataca esse problema combinando regras determinísticas transparentes com triagem supervisionada por IA."*

---

### [00:15 - 00:35] Identificação Determinística do Pedido em Risco
- **Ação:** Destacar o chip persistente de dados sintéticos e apontar para o pedido `NEX-1042`. Clicar para abrir o Drawer.
- **Fala:** 
  > *"Aqui temos 53 pedidos simulados gerados deterministicamente com seed fixa. Note que o score de atenção de 90 pontos do pedido NEX-1042 não é uma alucinação de LLM: ele é calculado no backend por regras explícitas — prazo prometido excedido há 5 minutos, entregador não atribuído após 35 minutos e restaurante sobrecarregado."*

---

### [00:35 - 01:00] Triagem do Agente Gemini & Tool Calling
- **Ação:** Clique em **Analisar com IA**. Mostre no histórico do WF01 as consultas ao contexto e à política, e volte ao painel para mostrar as evidências e a ação proposta.
- **Fala:** 
  > *"Ao clicar em 'Analisar com IA', o n8n aciona nosso agente Gemini com ferramentas de somente-leitura. O modelo consulta a telemetria do pedido e a base de políticas da empresa — neste caso a Diretriz de Atraso Operacional Severo (POL-DELAY-01). Ele extrai evidências auditadas e propõe a abertura de um ticket interno de alta prioridade, respeitando um schema JSON estrito."*

---

### [01:00 - 01:15] Aprovação e execução
- **Ação:** Aprove a proposta de abertura de chamado. Mostre a execução do WF02 e o chamado `TCK-1042` no painel, com prioridade e categoria.
- **Fala:** 
  > *"Quando o operador aprova a proposta, o WF02 confere a autorização e grava um único chamado fictício com a prioridade e a categoria aprovadas."*

---

### [01:15 - 01:30] Rodada de rejeição
- **Ação:** Após salvar o registro da aprovação, restaure a base de demo e analise o mesmo pedido. Na gravação, mostre o momento da rejeição, o estado `rejected` e o histórico sem uma nova execução do WF02.
- **Fala:** 
  > *"Repeti a triagem com o mesmo pedido sintético. Ao rejeitar a proposta, encerrei o incidente sem criar outro chamado."*

