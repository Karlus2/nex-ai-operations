from datetime import datetime, timezone
from typing import Tuple, List, Optional
from backend.app.models import Order, OrderStatus, RiskLevel

class RiskEngineResult:
    def __init__(self, score: int, level: RiskLevel, signals: List[str]):
        self.score = score
        self.level = level
        self.signals = signals

    def to_dict(self):
        return {
            "score": self.score,
            "level": self.level.value,
            "signals": self.signals
        }

def _ensure_tz(dt: datetime) -> datetime:
    """Garante que datetimes sejam comparados com timezone compatível."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

def evaluate_order_risk(order: Order, evaluation_time: Optional[datetime] = None) -> RiskEngineResult:
    """
    Calcula o Índice de Atenção Operacional (0 a 100) de um pedido de forma determinística.
    
    Regras transparentes (sem IA no score):
    - Pedidos concluídos ('delivered') ou cancelados ('cancelled') têm score 0 e nenhum risco ativo.
    - +45: Horário prometido já passou e pedido não concluído.
    - +25: Faltam 10 min ou menos para o prazo e o pedido ainda está em preparo ('preparing').
    - +20: Entregador não atribuído após pelo menos 15 minutos da criação do pedido.
    - +15: Nenhuma atualização de status há pelo menos 15 minutos.
    - +10: Restaurante com fila de 5 pedidos ou mais (backlog >= 5).
    
    Limites:
    - Score limitado a [0, 100].
    - Nível: High (>= 60), Medium (>= 30), Low (< 30).
    """
    # Pedidos finalizados recebem score zero
    if order.status in (OrderStatus.DELIVERED, OrderStatus.CANCELLED):
        return RiskEngineResult(score=0, level=RiskLevel.LOW, signals=[])

    if evaluation_time is None:
        ref_time = datetime.now(timezone.utc)
    else:
        ref_time = _ensure_tz(evaluation_time)

    created_at = _ensure_tz(order.created_at)
    promised_at = _ensure_tz(order.promised_at)
    last_status_update_at = _ensure_tz(order.last_status_update_at)

    score = 0
    signals: List[str] = []

    # 1. Horário prometido já passou (+45)
    if ref_time > promised_at:
        score += 45
        diff_minutes = int((ref_time - promised_at).total_seconds() / 60)
        signals.append(f"Horário prometido excedido há {diff_minutes} min")

    # 2. Faltam 10 min ou menos para o prazo e o pedido ainda está em preparo (+25)
    # (Apenas aplicável se o prazo ainda não expirou completamente)
    time_to_promise = (promised_at - ref_time).total_seconds() / 60
    if 0 <= time_to_promise <= 10 and order.status == OrderStatus.PREPARING:
        score += 25
        signals.append(f"Prazo encerra em {int(time_to_promise)} min e pedido ainda em preparo")

    # 3. Entregador não atribuído após >= 15 min da criação (+20)
    minutes_since_creation = (ref_time - created_at).total_seconds() / 60
    if not order.courier_assigned and minutes_since_creation >= 15:
        score += 20
        signals.append(f"Sem entregador alocado após {int(minutes_since_creation)} min da criação")

    # 4. Nenhuma atualização de status há >= 15 min (+15)
    minutes_since_last_update = (ref_time - last_status_update_at).total_seconds() / 60
    if minutes_since_last_update >= 15:
        score += 15
        signals.append(f"Sem atualização de status há {int(minutes_since_last_update)} min")

    # 5. Restaurante com backlog elevado (+10)
    if order.restaurant_backlog >= 5:
        score += 10
        signals.append(f"Restaurante com backlog elevado ({order.restaurant_backlog} pedidos na fila)")

    # Limitar o score ao intervalo [0, 100]
    final_score = max(0, min(100, score))

    # Determinar classificação
    if final_score >= 60:
        level = RiskLevel.HIGH
    elif final_score >= 30:
        level = RiskLevel.MEDIUM
    else:
        level = RiskLevel.LOW

    return RiskEngineResult(score=final_score, level=level, signals=signals)
