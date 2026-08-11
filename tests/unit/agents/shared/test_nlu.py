"""Unit tests for src.agents.shared.nlu — deterministic Spanish natural-language helpers
(PBI-05-01). Every case must be resolvable by rule alone, no LLM involved.
"""

from datetime import date

from src.agents.shared.nlu import (
    detect_negated_topic,
    resolve_commission_period,
    resolve_relative_date,
    strip_natural_prefix,
)

_REF = date(2026, 8, 8)  # a Saturday, deliberately arbitrary


def test_resolve_relative_date_ayer() -> None:
    assert resolve_relative_date("chocamos ayer en la tarde", reference=_REF) == "2026-08-07"


def test_resolve_relative_date_anoche() -> None:
    assert resolve_relative_date("se inundó anoche", reference=_REF) == "2026-08-07"


def test_resolve_relative_date_hoy() -> None:
    assert resolve_relative_date("fue hoy en la mañana", reference=_REF) == "2026-08-08"


def test_resolve_relative_date_anteayer() -> None:
    assert resolve_relative_date("fue anteayer", reference=_REF) == "2026-08-06"


def test_resolve_relative_date_returns_none_when_absent() -> None:
    assert resolve_relative_date("el vehículo puede circular", reference=_REF) is None


def test_resolve_relative_date_la_semana_pasada() -> None:
    """PBI-09-01 requirement 4."""
    assert resolve_relative_date("se inundó la semana pasada", reference=_REF) == "2026-08-01"


def test_resolve_relative_date_last_week() -> None:
    assert resolve_relative_date("it happened last week", reference=_REF) == "2026-08-01"


def test_resolve_commission_period_explicit_q_notation() -> None:
    assert resolve_commission_period("Q1 2026") == "2026-Q1"
    assert resolve_commission_period("2026-Q2") == "2026-Q2"


def test_resolve_commission_period_ordinal_with_year() -> None:
    assert resolve_commission_period("primer trimestre de 2026") == "2026-Q1"
    assert resolve_commission_period("segundo trimestre de 2026") == "2026-Q2"


def test_resolve_commission_period_ordinal_without_year_uses_reference_year() -> None:
    assert resolve_commission_period("segundo trimestre", reference=_REF) == "2026-Q2"


def test_resolve_commission_period_this_quarter() -> None:
    assert resolve_commission_period("este trimestre", reference=_REF) == "2026-Q3"


def test_resolve_commission_period_month_name_maps_to_quarter() -> None:
    assert resolve_commission_period("agosto 2026") == "2026-Q3"
    assert resolve_commission_period("enero de 2026") == "2026-Q1"


def test_resolve_commission_period_returns_none_when_absent() -> None:
    assert resolve_commission_period("quiero conocer mis comisiones") is None


def test_strip_natural_prefix_mi_nombre_es() -> None:
    assert strip_natural_prefix("mi nombre es Juan Pérez", ("mi nombre es", "soy", "me llamo")) == "Juan Pérez"


def test_strip_natural_prefix_soy() -> None:
    assert strip_natural_prefix("soy Juan Pérez", ("mi nombre es", "soy", "me llamo")) == "Juan Pérez"


def test_strip_natural_prefix_somos_for_broker() -> None:
    assert (
        strip_natural_prefix("somos Synthetic Brokerage One", ("somos", "soy", "mi correduría es"))
        == "Synthetic Brokerage One"
    )


def test_strip_natural_prefix_no_match_returns_trimmed_original() -> None:
    assert strip_natural_prefix("Juan Pérez", ("mi nombre es", "soy")) == "Juan Pérez"


def test_detect_negated_topic_returns_none_when_topic_not_mentioned() -> None:
    assert detect_negated_topic("el vehículo puede circular", ("lesionad", "herid")) is None


def test_detect_negated_topic_true_when_affirmed() -> None:
    assert detect_negated_topic("hubo un lesionado leve", ("lesionad", "herid")) is True


def test_detect_negated_topic_false_when_directly_negated() -> None:
    assert detect_negated_topic("no hubo lesionados", ("lesionad", "herid")) is False


def test_detect_negated_topic_false_for_the_ni_continuation_case() -> None:
    """The exact PBI-05-01 example: "no hubo lesionados ni terceros" must negate BOTH topics,
    even though "no" is not immediately adjacent to "terceros"."""
    message = "no hubo lesionados ni terceros involucrados"
    assert detect_negated_topic(message, ("lesionad", "herid")) is False
    assert detect_negated_topic(message, ("tercero",)) is False
