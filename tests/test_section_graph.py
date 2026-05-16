from src.policy.retriever import (
    PolicySectionGraph,
    extract_section_references,
    parse_policy_sections,
)


def _sections_by_id():
    sections = parse_policy_sections()
    return sections, {section["section_id"]: section for section in sections}


def test_parent_of_4_2_is_4():
    sections, _ = _sections_by_id()
    graph = PolicySectionGraph(sections)

    parent = graph.get_parent("4.2")

    assert parent is not None
    assert parent["section_id"] == "4"


def test_children_of_4_include_core_hr_subsections():
    sections, _ = _sections_by_id()
    graph = PolicySectionGraph(sections)

    children = graph.get_children("4", max_children=10)
    child_ids = {child["section_id"] for child in children}

    assert {"4.1", "4.2", "4.3", "4.4"} <= child_ids


def test_extract_section_references_detects_single_and_multiple_refs():
    text = (
        "Department and job title are directory information per Section 2.1 "
        "and Section 4.3. Section 4.2 restricts employment status, but "
        "Section 4.4 creates a narrow exception."
    )

    assert extract_section_references(text) == ["2.1", "4.3", "4.2", "4.4"]


def test_extract_section_references_detects_sections_list():
    text = "pursuant to Sections 4.2, 4.4, and 17.3."

    assert extract_section_references(text) == ["4.2", "4.4", "17.3"]


def test_sections_referring_to_4_4_include_reference():
    _, sections_by_id = _sections_by_id()

    assert "4.4" in sections_by_id["17.4.2"]["references"]


def test_graph_expansion_adds_parent_child_and_reference_sections():
    sections, sections_by_id = _sections_by_id()
    graph = PolicySectionGraph(sections)
    initial_ref = {
        **sections_by_id["17.4.2"],
        "score": 0.8,
        "semantic_score": 0.7,
        "keyword_score": 0.9,
        "retrieval_source": "hybrid_match",
        "matched_from": None,
        "relationship": "self",
    }
    initial_parent = {
        **sections_by_id["4"],
        "score": 0.7,
        "semantic_score": 0.6,
        "keyword_score": 0.8,
        "retrieval_source": "hybrid_match",
        "matched_from": None,
        "relationship": "self",
    }

    expanded = graph.expand([initial_ref, initial_parent], max_expanded=12)
    by_id = {section["section_id"]: section for section in expanded}

    assert "17.4" in by_id
    assert by_id["17.4"]["relationship"] == "parent"
    assert "4.1" in by_id
    assert by_id["4.1"]["relationship"] == "child"
    assert "4.4" in by_id
    assert by_id["4.4"]["relationship"] == "reference"
