"""Testes do módulo pós-venda (roadmap-leads C.3).

Cobrem a lógica de dados do pós-venda: o canal (WHATSAPP/EMAIL) e a etapa
`POST_SALE` da cadência reutilizada como lembrete pós-cliente pelo mesmo motor
(`run_due`/`send_step`).
"""
from src.db.models import FollowUpStep, PostSaleChannel


def test_post_sale_channel_valores():
    assert {c.value for c in PostSaleChannel} == {"WHATSAPP", "EMAIL"}


def test_follow_up_step_post_sale_existe():
    assert FollowUpStep.POST_SALE.value == "POST_SALE"


def test_post_sale_day_offset_reusa_cadencia():
    assert FollowUpStep.POST_SALE.day_offset == 14


def test_post_sale_label():
    assert FollowUpStep.POST_SALE.label == "Pós-venda"


def test_post_sale_nao_afeta_cadencia_presale():
    # O `schedule_cadence` só agenda as 4 etapas pré-venda — POST_SALE não
    # confunde a sequência dia 0/3/7/14.
    pre = [FollowUpStep.OPENING, FollowUpStep.FOLLOWUP_1,
           FollowUpStep.FOLLOWUP_2, FollowUpStep.CLOSING]
    assert FollowUpStep.POST_SALE not in pre