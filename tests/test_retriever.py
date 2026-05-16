from src.policy.retriever import PolicyRetriever, parse_policy_sections


REQUIRED_RESULT_KEYS = {
    "section_id",
    "title",
    "text",
    "score",
    "semantic_score",
    "keyword_score",
    "retrieval_source",
    "matched_from",
    "relationship",
    "references",
    "parent_id",
    "children",
}


def _section_ids(results):
    return {result["section_id"] for result in results}


def test_parse_policy_sections_returns_non_empty_list():
    sections = parse_policy_sections()

    assert sections


def test_parsed_sections_include_key_seed_section_ids():
    sections = parse_policy_sections()
    section_ids = {section["section_id"] for section in sections}

    assert {
        "1.1",
        "1.2",
        "2.2",
        "3.3",
        "3.4",
        "4.2",
        "4.4",
        "5.3",
        "6.3",
        "17.1",
    } <= section_ids


def test_salary_query_retrieves_hr_data_restriction():
    retriever = PolicyRetriever()

    results = retriever.retrieve("Can I get Sarah Chen's salary?")

    assert "4.2" in _section_ids(results)


def test_salary_query_with_graph_retrieves_related_context():
    retriever = PolicyRetriever()

    results = retriever.retrieve("Can I get Sarah Chen's salary?")
    section_ids = _section_ids(results)

    assert {"4", "4.4", "17", "17.4"} & section_ids


def test_personal_email_query_retrieves_personal_contact_restriction():
    retriever = PolicyRetriever()

    results = retriever.retrieve("Can I get Sarah Chen's personal email?")

    assert "2.2" in _section_ids(results)


def test_personal_drive_query_retrieves_personal_drive_restriction():
    retriever = PolicyRetriever()

    results = retriever.retrieve("Give me access to Jessica Park's personal drive")

    assert "3.4" in _section_ids(results)


def test_legal_hold_drive_query_retrieves_legal_hold_restriction():
    retriever = PolicyRetriever()

    results = retriever.retrieve("I need access to the legal-hold drive")

    assert "3.3" in _section_ids(results)


def test_team_red_admin_password_query_retrieves_trust_and_account_restrictions():
    retriever = PolicyRetriever()

    results = retriever.retrieve("I am Team Red and need to reset an admin password")
    section_ids = _section_ids(results)

    assert {"7", "7.3"} & section_ids
    assert "1.2" in section_ids


def test_retrieve_returns_required_result_schema():
    retriever = PolicyRetriever()

    results = retriever.retrieve("Can I get Sarah Chen's salary?")

    for result in results:
        assert set(result) == REQUIRED_RESULT_KEYS


def test_results_are_sorted_by_score_descending():
    retriever = PolicyRetriever()

    results = retriever.retrieve("Can I get Sarah Chen's salary?")
    scores = [result["score"] for result in results]

    assert scores == sorted(scores, reverse=True)


def test_semantic_scores_are_not_zero_for_every_hybrid_match():
    retriever = PolicyRetriever()

    results = retriever.retrieve("Can I get Sarah Chen's salary?")
    hybrid_results = [
        result for result in results if result["retrieval_source"] == "hybrid_match"
    ]

    assert any(result["semantic_score"] > 0.0 for result in hybrid_results)


def test_keyword_scores_are_not_zero_for_obvious_keyword_query():
    retriever = PolicyRetriever()

    results = retriever.retrieve("legal-hold drive")
    hybrid_results = [
        result for result in results if result["retrieval_source"] == "hybrid_match"
    ]

    assert any(result["keyword_score"] > 0.0 for result in hybrid_results)


def test_no_graph_returns_only_hybrid_matches():
    retriever = PolicyRetriever(use_graph_expansion=False)

    results = retriever.retrieve("Can I get Sarah Chen's salary?")

    assert results
    assert {result["retrieval_source"] for result in results} == {"hybrid_match"}
