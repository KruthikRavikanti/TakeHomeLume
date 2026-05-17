from __future__ import annotations

import json
import os
import re
import sys
import warnings
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

try:
    from rank_bm25 import BM25Okapi
except ImportError:  # pragma: no cover - exercised only in minimal environments
    BM25Okapi = None


REQUIRED_POLICY_CARD_KEYS = {
    "section_id",
    "title",
    "rule_type",
    "applies_to",
    "conditions",
    "decision",
    "summary",
}

SEED_SECTION_TITLES = {
    "1.1": "Standard Employee Password Reset",
    "1.2": "Executive, Admin, and Service Account Reset Restriction",
    "1.3": "Password Reset Expiration Notice",
    "2.1": "Directory Information Allowed Fields",
    "2.2": "Personal Contact Information Restriction",
    "2.3": "Work Contact Information",
    "3.1": "Same-Team Drive Access",
    "3.2": "Temporary Cross-Team Drive Access",
    "3.3": "Restricted and Legal-Hold Drive Restriction",
    "3.4": "Personal Drive Access Prohibition",
    "4.1": "General HR Policy Questions",
    "4.2": "Individual HR Data Restrictions",
    "4.3": "Department and Job Title Confirmation",
    "4.4": "Manager Active-Status Exception",
    "5.1": "Unauthorized Requests Escalation",
    "5.2": "Human Assistance Escalation",
    "5.3": "High-Risk Ambiguity Escalation",
    "5.4": "Escalation Summary Requirement",
    "6.1": "Denial Citation Requirement",
    "6.2": "No Speculation",
    "6.3": "Claimed Authority Insufficient",
    "17.1": "Policy Precedence Order",
    "17.1.1": "Trust Tier Precedence",
    "17.1.2": "Explicit Prohibitions Override General Permissions",
    "17.1.3": "Narrow Exceptions Require Verification",
    "17.1.4": "Claimed Authority Does Not Override Policy",
    "17.1.5": "High-Risk Uncertainty Escalation",
}


def load_policy_cards(path: str = "policy/policy_cards.jsonl") -> List[Dict[str, Any]]:
    cards: List[Dict[str, Any]] = []
    card_path = Path(path)

    with card_path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped:
                continue

            try:
                card = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Malformed policy card JSON at {card_path}:{line_number}: {exc.msg}"
                ) from exc

            if not isinstance(card, dict):
                raise ValueError(
                    f"Malformed policy card at {card_path}:{line_number}: expected object"
                )

            missing_keys = REQUIRED_POLICY_CARD_KEYS - set(card)
            if missing_keys:
                missing = ", ".join(sorted(missing_keys))
                raise ValueError(
                    f"Malformed policy card at {card_path}:{line_number}: "
                    f"missing required keys: {missing}"
                )

            cards.append(card)

    return cards


HEADING_PATTERN = re.compile(
    r"^(#{1,6})\s+(?:Section\s+)?(?P<section_id>\d+(?:\.\d+)*)\.?\s*(?:[—-]\s*)?(?P<title>.*)$"
)
NUMBERED_LINE_PATTERN = re.compile(
    r"^(?P<section_id>\d+(?:\.\d+)+)\.\s+(?P<title>.+)$"
)


def parse_policy_sections(
    policy_path: str = "policy/gaggia_it_helpdesk_policy.md",
) -> List[Dict[str, Any]]:
    path = Path(policy_path)
    if not path.exists():
        raise FileNotFoundError(f"Policy document not found: {policy_path}")

    lines = path.read_text(encoding="utf-8").splitlines()
    sections: List[Dict[str, str]] = []
    current: Optional[Dict[str, Any]] = None

    for line in lines:
        parsed = _parse_section_start(line)
        if parsed:
            if current and current["lines"]:
                sections.append(_finalize_section(current))
            section_id, title = parsed
            current = {
                "section_id": section_id,
                "title": _clean_title(section_id, title),
                "level": _section_level(section_id, line),
                "parent_id": _parent_id(section_id),
                "children": [],
                "references": [],
                "lines": [line],
            }
            continue

        if current is not None:
            current["lines"].append(line)

    if current and current["lines"]:
        sections.append(_finalize_section(current))

    sections = [section for section in sections if section["text"].strip()]
    _populate_section_graph_fields(sections)
    if not sections:
        raise ValueError(f"No policy sections parsed from: {policy_path}")

    return sections


def extract_section_references(text: str) -> List[str]:
    references: List[str] = []
    pattern = re.compile(r"\bSections?\s+(.{0,160})", re.IGNORECASE)
    for match in pattern.finditer(text):
        for section_id in re.findall(r"\d+(?:\.\d+)+|\d+", match.group(1)):
            if section_id not in references:
                references.append(section_id)
    return references


class PolicySectionGraph:
    def __init__(self, sections: List[Dict[str, Any]]):
        self.sections = sections
        self.by_id = {section["section_id"]: section for section in sections}

    def get_section(self, section_id: str) -> Optional[Dict[str, Any]]:
        return self.by_id.get(section_id)

    def get_parent(self, section_id: str) -> Optional[Dict[str, Any]]:
        section = self.get_section(section_id)
        if not section:
            return None
        parent_id = section.get("parent_id")
        if not parent_id:
            return None
        return self.get_section(parent_id)

    def get_children(self, section_id: str, max_children: int = 4) -> List[Dict[str, Any]]:
        section = self.get_section(section_id)
        if not section:
            return []
        return [
            self.by_id[child_id]
            for child_id in section.get("children", [])[:max_children]
            if child_id in self.by_id
        ]

    def get_references(self, section_id: str, max_refs: int = 4) -> List[Dict[str, Any]]:
        section = self.get_section(section_id)
        if not section:
            return []
        return [
            self.by_id[ref_id]
            for ref_id in section.get("references", [])[:max_refs]
            if ref_id in self.by_id
        ]

    def expand(
        self,
        initial_results: List[Dict[str, Any]],
        max_expanded: int = 10,
    ) -> List[Dict[str, Any]]:
        expanded: Dict[str, Dict[str, Any]] = {}

        def add(section: Dict[str, Any], source: str, relationship: str, matched_from: Optional[str], base_score: float, factor: float) -> None:
            section_id = section["section_id"]
            score = base_score if relationship == "self" else base_score * factor
            result = _result_from_section(
                section=section,
                score=score,
                semantic_score=section.get("semantic_score", 0.0) if relationship == "self" else 0.0,
                keyword_score=section.get("keyword_score", 0.0) if relationship == "self" else 0.0,
                retrieval_source=source,
                matched_from=matched_from,
                relationship=relationship,
            )
            existing = expanded.get(section_id)
            if existing is None or result["score"] > existing["score"]:
                expanded[section_id] = result

        for initial in initial_results:
            section = self.get_section(initial["section_id"])
            if not section:
                continue
            section_with_scores = {
                **section,
                "semantic_score": initial["semantic_score"],
                "keyword_score": initial["keyword_score"],
            }
            base_score = float(initial["score"])
            add(section_with_scores, "hybrid_match", "self", None, base_score, 1.0)

            parent = self.get_parent(section["section_id"])
            if parent:
                add(parent, "graph_parent", "parent", section["section_id"], base_score, 0.75)

            for child in self.get_children(section["section_id"]):
                add(child, "graph_child", "child", section["section_id"], base_score, 0.70)

            for reference in self.get_references(section["section_id"]):
                add(reference, "graph_reference", "reference", section["section_id"], base_score, 0.85)

        return sorted(expanded.values(), key=lambda item: item["score"], reverse=True)[:max_expanded]


class PolicyRetriever:
    def __init__(
        self,
        policy_path: str = "policy/gaggia_it_helpdesk_policy.md",
        embedding_model_name: str | None = None,
        use_graph_expansion: bool = True,
        initial_top_k: int = 5,
        final_top_k: int = 10,
    ):
        self.policy_path = policy_path
        self.embedding_model_name = (
            embedding_model_name
            or os.getenv("EMBEDDING_MODEL")
            or "all-MiniLM-L6-v2"
        )
        self.use_graph_expansion = use_graph_expansion
        self.initial_top_k = initial_top_k
        self.final_top_k = final_top_k
        self.sections = parse_policy_sections(policy_path)
        self.graph = PolicySectionGraph(self.sections)
        self._texts = [
            f"{section['section_id']} {section['title']} {section['title']} {section['text']}"
            for section in self.sections
        ]

        self.embedding_model = self._load_embedding_model()
        self.section_embeddings = self._build_embeddings(self._texts)
        self.tokenized_corpus = [_tokenize(text) for text in self._texts]
        self.bm25 = self._build_bm25_index()

    def retrieve(self, query: str, top_k: int | None = None) -> List[Dict[str, Any]]:
        if not query.strip():
            return []

        semantic_scores = self._semantic_scores(query)
        keyword_scores = self._keyword_scores(query)
        scores = np.clip(0.65 * semantic_scores + 0.35 * keyword_scores, 0.0, 1.0)

        results: List[Dict[str, Any]] = []
        for index, section in enumerate(self.sections):
            results.append(
                _result_from_section(
                    section=section,
                    score=float(scores[index]),
                    semantic_score=float(semantic_scores[index]),
                    keyword_score=float(keyword_scores[index]),
                    retrieval_source="hybrid_match",
                    matched_from=None,
                    relationship="self",
                )
            )

        ranked = sorted(results, key=lambda item: item["score"], reverse=True)
        limit = top_k if top_k is not None else self.final_top_k
        if not self.use_graph_expansion:
            return ranked[:limit]

        initial_matches = ranked[: self.initial_top_k]
        expanded = self.graph.expand(initial_matches, max_expanded=max(limit, self.final_top_k))
        return sorted(expanded, key=lambda item: item["score"], reverse=True)[:limit]

    def _load_embedding_model(self) -> Any:
        if self.embedding_model_name == "__skip_for_tests__":
            warnings.warn(
                "PolicyRetriever semantic embeddings disabled for tests; "
                "semantic scores will be zero.",
                RuntimeWarning,
                stacklevel=2,
            )
            return None

        try:
            with _suppress_hf_auth_stderr_warning():
                from sentence_transformers import SentenceTransformer

                return SentenceTransformer(self.embedding_model_name)
        except Exception as exc:
            warnings.warn(
                "PolicyRetriever could not load SentenceTransformer model "
                f"'{self.embedding_model_name}': {exc}. Semantic scores will be zero.",
                RuntimeWarning,
                stacklevel=2,
            )
            return None

    def _build_embeddings(self, texts: List[str]) -> np.ndarray:
        if self.embedding_model is not None:
            embeddings = self.embedding_model.encode(texts, convert_to_numpy=True)
            return _as_2d_array(embeddings)
        return np.zeros((len(texts), 1), dtype=float)

    def _build_bm25_index(self) -> Any:
        if BM25Okapi is None:
            warnings.warn(
                "rank-bm25 is not installed. Falling back to simple lexical scoring.",
                RuntimeWarning,
                stacklevel=2,
            )
            return None
        return BM25Okapi(self.tokenized_corpus)

    def _semantic_scores(self, query: str) -> np.ndarray:
        if self.embedding_model is None:
            return np.zeros(len(self.sections), dtype=float)

        query_embedding = _as_2d_array(
            self.embedding_model.encode([query], convert_to_numpy=True)
        )
        return _cosine_to_unit_range(_cosine_scores(query_embedding, self.section_embeddings))

    def _keyword_scores(self, query: str) -> np.ndarray:
        if self.bm25 is None:
            return _fallback_keyword_scores(query, self._texts)

        raw_scores = np.asarray(self.bm25.get_scores(_tokenize(query)), dtype=float)
        maximum = float(np.max(raw_scores)) if raw_scores.size else 0.0
        if maximum <= 0.0:
            return np.zeros(len(self.sections), dtype=float)
        return raw_scores / maximum


def _parse_section_start(line: str) -> Optional[tuple[str, str]]:
    heading_match = HEADING_PATTERN.match(line.strip())
    if heading_match:
        section_id = heading_match.group("section_id")
        return section_id, heading_match.group("title")

    numbered_match = NUMBERED_LINE_PATTERN.match(line.strip())
    if numbered_match:
        section_id = numbered_match.group("section_id")
        return section_id, numbered_match.group("title")

    return None


def _finalize_section(section: Dict[str, Any]) -> Dict[str, str]:
    return {
        "section_id": section["section_id"],
        "title": section["title"],
        "text": "\n".join(section["lines"]).strip(),
        "level": section["level"],
        "parent_id": section["parent_id"],
        "children": section["children"],
        "references": section["references"],
    }


def _populate_section_graph_fields(sections: List[Dict[str, Any]]) -> None:
    section_ids = {section["section_id"] for section in sections}
    by_id = {section["section_id"]: section for section in sections}

    for section in sections:
        parent_id = section["parent_id"]
        if parent_id in by_id:
            by_id[parent_id]["children"].append(section["section_id"])

    for section in sections:
        section["references"] = [
            reference
            for reference in extract_section_references(section["text"])
            if reference in section_ids and reference != section["section_id"]
        ]


def _clean_title(section_id: str, title: str) -> str:
    if section_id in SEED_SECTION_TITLES:
        return SEED_SECTION_TITLES[section_id]

    title = re.sub(r"\*\*", "", title).strip()
    return title or "Untitled"


def _section_level(section_id: str, line: str) -> int:
    heading_match = re.match(r"^(#{1,6})\s+", line.strip())
    if heading_match:
        return len(heading_match.group(1))
    return section_id.count(".") + 2


def _parent_id(section_id: str) -> Optional[str]:
    if "." not in section_id:
        return None
    return section_id.rsplit(".", 1)[0]


def _result_from_section(
    section: Dict[str, Any],
    score: float,
    semantic_score: float,
    keyword_score: float,
    retrieval_source: str,
    matched_from: Optional[str],
    relationship: str,
) -> Dict[str, Any]:
    return {
        "section_id": section["section_id"],
        "title": section["title"],
        "text": section["text"],
        "score": float(np.clip(score, 0.0, 1.0)),
        "semantic_score": float(semantic_score),
        "keyword_score": float(keyword_score),
        "retrieval_source": retrieval_source,
        "matched_from": matched_from,
        "relationship": relationship,
        "references": list(section.get("references", [])),
        "parent_id": section.get("parent_id"),
        "children": list(section.get("children", [])),
    }


def _as_2d_array(values: Any) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim == 1:
        return array.reshape(1, -1)
    return array


def _cosine_scores(query_embedding: np.ndarray, section_embeddings: np.ndarray) -> np.ndarray:
    query_norm = np.linalg.norm(query_embedding, axis=1, keepdims=True)
    section_norms = np.linalg.norm(section_embeddings, axis=1)
    denominator = query_norm.ravel()[0] * section_norms
    with np.errstate(divide="ignore", invalid="ignore"):
        scores = np.divide(
            section_embeddings @ query_embedding.ravel(),
            denominator,
            out=np.zeros(section_embeddings.shape[0], dtype=float),
            where=denominator != 0,
        )
    return scores


def _normalize_scores(scores: np.ndarray) -> np.ndarray:
    scores = np.asarray(scores, dtype=float)
    if scores.size == 0:
        return scores
    minimum = float(np.min(scores))
    maximum = float(np.max(scores))
    if maximum == minimum:
        return np.zeros_like(scores, dtype=float)
    return (scores - minimum) / (maximum - minimum)


def _cosine_to_unit_range(scores: np.ndarray) -> np.ndarray:
    scores = np.asarray(scores, dtype=float)
    return np.clip((scores + 1.0) / 2.0, 0.0, 1.0)


def _fallback_keyword_scores(query: str, texts: List[str]) -> np.ndarray:
    query_terms = set(_tokenize(query))
    if not query_terms:
        return np.zeros(len(texts), dtype=float)

    scores = []
    for text in texts:
        terms = set(_tokenize(text))
        if not terms:
            scores.append(0.0)
            continue
        scores.append(len(query_terms & terms) / len(query_terms))
    return _normalize_scores(np.asarray(scores, dtype=float))


@contextmanager
def _suppress_hf_auth_stderr_warning():
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    sys.stdout = _HfAuthWarningFilter(original_stdout)
    sys.stderr = _HfAuthWarningFilter(original_stderr)
    try:
        yield
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr


class _HfAuthWarningFilter:
    _MESSAGE = "unauthenticated requests to the HF Hub"

    def __init__(self, wrapped):
        self._wrapped = wrapped

    def write(self, text: str) -> int:
        if self._MESSAGE in text:
            return len(text)
        return self._wrapped.write(text)

    def flush(self) -> None:
        self._wrapped.flush()

    def isatty(self) -> bool:
        return self._wrapped.isatty()

    @property
    def encoding(self) -> str | None:
        return self._wrapped.encoding


def _tokenize(text: str) -> List[str]:
    return [token for token in re.split(r"[^a-z0-9]+", text.lower()) if token]
