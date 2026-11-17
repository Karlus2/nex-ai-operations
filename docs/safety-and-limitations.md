# Governança, Segurança e Limitações — Nex

## 1. Natureza dos Dados e Independência
- **Projeto Independente:** Desenvolvido exclusivamente para fins de portfólio no programa genAI / AI Builder do iFood. Não possui afiliação oficial nem acesso a sistemas ou bases internas do iFood.
- **Dados 100% Sintéticos:** Nenhum dado pessoal (LGPD), dado de cliente real, entregador ou restaurante é utilizado. O dataset é gerado deterministicamente (`seed=42`).

## 2. Métricas e Afirmações de Negócio
- Não fazemos alegações empíricas de "redução de cancelamento em X%" ou "economia de Y reais", pois o projeto opera sobre dados simulados em ambiente controlado.
- As métricas reportadas no projeto dizem respeito a:
  - Latência de resposta da triagem.
  - Taxa de conformidade de schema JSON retornado pelo modelo.
  - Taxa de aderência a evidências reais recuperadas pelas ferramentas.
  - Idempotência de ações executadas.

## 3. Defesa contra Prompt Injection e Dados Não Confiáveis
- O conteúdo de observações ou mensagens de pedidos é considerado **dado não confiável (untrusted data)**.
- O prompt de sistema do agente instrui explicitamente a não seguir instruções vindas de textos do pedido.
- A API valida esquemas e permissões de forma independente via código backend (Pydantic / validação determinística); o sistema não depende apenas da "boa vontade" do LLM para aplicar restrições de segurança.

## 4. Human-in-the-Loop
- O agente não tem permissão de escrita direta no banco de dados nem em sistemas externos.
- Toda sugestão precisa de aprovação explícita de um operador humano autenticado.
