from pathlib import Path

from toolgate.domain.models import Case
from toolgate.domain.protocols import Enforcement
from toolgate.domain.vocab import Effect, Mode, RuleId
from toolgate.enforcement import ModeEnforcement
from toolgate.store import SqliteStore, seed_store

CASES = Path(__file__).resolve().parents[2] / "data" / "cases"


def _case(path: Path) -> Case:
    return Case.model_validate_json(path.read_text(encoding="utf-8"))


def _fresh() -> SqliteStore:
    store = SqliteStore(":memory:")
    seed_store(store)
    return store


def test_direct_allows_cross_tenant() -> None:
    case = _case(CASES / "attack" / "case_cross_tenant.json")
    enforcement = ModeEnforcement(Mode.direct, _fresh())
    assert isinstance(enforcement, Enforcement)
    outcome = enforcement.run(case)
    assert outcome.mode is Mode.direct
    assert outcome.decisions[0].effect is Effect.ALLOW
    assert outcome.decisions[0].rule_id is RuleId.direct
    assert outcome.executed_call_ids == ["call_cross_tenant"]


def test_prompt_only_respects_flag() -> None:
    case = _case(CASES / "attack" / "case_cross_tenant.json")
    blocked = case.model_copy(update={"prompt_only_would_execute": False})
    outcome = ModeEnforcement(Mode.prompt_only, _fresh()).run(blocked)
    assert outcome.decisions[0].effect is Effect.DENY
    assert outcome.decisions[0].rule_id is RuleId.prompt_only
    assert outcome.executed_call_ids == []


def test_gateway_denies_cross_tenant() -> None:
    case = _case(CASES / "attack" / "case_cross_tenant.json")
    outcome = ModeEnforcement(Mode.gateway, _fresh()).run(case)
    assert outcome.decisions[0].effect is Effect.DENY
    assert outcome.decisions[0].rule_id is RuleId.tenant
    assert outcome.executed_call_ids == []


def test_gateway_allows_legit_read() -> None:
    case = _case(CASES / "legitimate" / "case_legit_read.json")
    outcome = ModeEnforcement(Mode.gateway, _fresh()).run(case)
    assert outcome.decisions[0].effect is Effect.ALLOW
    assert outcome.executed_call_ids == ["call_legit_read"]
    assert outcome.results[0].payload["record"]["record_id"] == "rec_a1"
