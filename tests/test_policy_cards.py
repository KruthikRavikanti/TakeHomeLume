from pathlib import Path

from src.policy.retriever import REQUIRED_POLICY_CARD_KEYS, load_policy_cards


POLICY_CARDS_PATH = Path("policy/policy_cards.jsonl")


def test_policy_cards_file_exists():
    assert POLICY_CARDS_PATH.exists()


def test_load_policy_cards_loads_successfully():
    cards = load_policy_cards()

    assert cards


def test_every_card_has_required_keys():
    cards = load_policy_cards()

    for card in cards:
        assert REQUIRED_POLICY_CARD_KEYS <= set(card)


def test_team_red_restriction_card_exists():
    cards = load_policy_cards()

    assert any(
        card["section_id"] == "7.2"
        and card["conditions"].get("trust_tier") == "red"
        and card["decision"] == "deny"
        for card in cards
    )


def test_personal_drive_denial_card_exists():
    cards = load_policy_cards()

    assert any(
        card["section_id"] == "3.4"
        and card["conditions"].get("drive_type") == "personal"
        and card["decision"] == "deny"
        for card in cards
    )


def test_restricted_or_legal_hold_drive_escalation_card_exists():
    cards = load_policy_cards()

    assert any(
        card["section_id"] == "3.3"
        and set(card["conditions"].get("drive_type", [])) == {"restricted", "legal_hold"}
        and card["decision"] == "escalate"
        for card in cards
    )


def test_salary_or_compensation_denial_card_exists():
    cards = load_policy_cards()

    assert any(
        card["section_id"] == "4.2"
        and card["decision"] == "deny"
        and "salary" in card.get("required_filters", [])
        for card in cards
    )


def test_manager_active_status_exception_card_exists():
    cards = load_policy_cards()

    assert any(
        card["section_id"] == "4.4"
        and card["rule_type"] == "allow_exception"
        and card["conditions"].get("manager_in_reporting_chain") is True
        and card["required_filters"] == ["employment_status_active_only"]
        for card in cards
    )


def test_claimed_authority_insufficient_card_exists():
    cards = load_policy_cards()

    assert any(
        card["section_id"] == "6.3"
        and card["conditions"].get("verified_in_requester_context") is False
        for card in cards
    )


def test_policy_conflict_precedence_card_exists():
    cards = load_policy_cards()

    assert any(card["rule_type"] == "precedence" for card in cards)


def test_seed_section_ids_are_represented():
    cards = load_policy_cards()
    represented_ids = {card["section_id"] for card in cards}
    seed_ids = {
        "1.1",
        "1.2",
        "1.3",
        "2.1",
        "2.2",
        "2.3",
        "3.1",
        "3.2",
        "3.3",
        "3.4",
        "4.1",
        "4.2",
        "4.3",
        "4.4",
        "5.1",
        "5.2",
        "5.3",
        "5.4",
        "6.1",
        "6.2",
        "6.3",
    }

    assert seed_ids <= represented_ids
