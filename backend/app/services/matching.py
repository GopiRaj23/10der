"""Relevance scoring engine.

Score (0-100) =
    40  keyword expression matches tender title
    30  keyword expression matches description
    10  keyword expression matches organisation/department
    10  tender state equals the user's preferred state
    10  user's industry sector appears in the tender text

A keyword supports boolean expressions ("drone AND surveillance NOT toy",
parentheses and quoted phrases allowed) plus a synonym list that is treated
as an OR-alternative for the whole expression.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

WEIGHT_TITLE = 40.0
WEIGHT_DESCRIPTION = 30.0
WEIGHT_ORGANISATION = 10.0
WEIGHT_STATE = 10.0
WEIGHT_INDUSTRY = 10.0

_TOKEN_RE = re.compile(r'"[^"]+"|\(|\)|\S+')


# --- Boolean expression parser ----------------------------------------------
# Grammar:  expr := and_expr (OR and_expr)*
#           and_expr := not_term (AND not_term)*   (bare adjacency == AND)
#           not_term := NOT not_term | "(" expr ")" | TERM

@dataclass
class _Node:
    kind: str                      # "term" | "and" | "or" | "not"
    term: str | None = None
    children: list["_Node"] | None = None


class _Parser:
    def __init__(self, tokens: list[str]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> str | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def next(self) -> str | None:
        tok = self.peek()
        self.pos += 1
        return tok

    def parse(self) -> _Node | None:
        node = self.expr()
        return node

    def expr(self) -> _Node | None:
        left = self.and_expr()
        children = [left] if left else []
        while self.peek() and self.peek().upper() == "OR":
            self.next()
            right = self.and_expr()
            if right:
                children.append(right)
        if not children:
            return None
        return children[0] if len(children) == 1 else _Node("or", children=children)

    def and_expr(self) -> _Node | None:
        children = []
        while True:
            tok = self.peek()
            if tok is None or tok.upper() == "OR" or tok == ")":
                break
            if tok.upper() == "AND":
                self.next()
                continue
            node = self.not_term()
            if node:
                children.append(node)
        if not children:
            return None
        return children[0] if len(children) == 1 else _Node("and", children=children)

    def not_term(self) -> _Node | None:
        tok = self.peek()
        if tok is None:
            return None
        if tok.upper() == "NOT":
            self.next()
            inner = self.not_term()
            return _Node("not", children=[inner]) if inner else None
        if tok == "(":
            self.next()
            inner = self.expr()
            if self.peek() == ")":
                self.next()
            return inner
        self.next()
        return _Node("term", term=tok.strip('"'))


def parse_expression(text: str) -> _Node | None:
    tokens = _TOKEN_RE.findall(text or "")
    if not tokens:
        return None
    return _Parser(tokens).parse()


def _term_in(term: str, haystack: str) -> bool:
    """Word-boundary, case-insensitive containment."""
    if not term:
        return False
    pattern = r"(?<!\w)" + re.escape(term.lower()) + r"(?!\w)"
    return re.search(pattern, haystack) is not None


def _eval(node: _Node | None, haystack: str) -> bool:
    if node is None:
        return False
    if node.kind == "term":
        return _term_in(node.term, haystack)
    if node.kind == "not":
        return not _eval(node.children[0], haystack)
    if node.kind == "and":
        return all(_eval(c, haystack) for c in node.children)
    if node.kind == "or":
        return any(_eval(c, haystack) for c in node.children)
    return False


def expression_matches(keyword_text: str, synonyms: list[str], text: str) -> bool:
    """True if the boolean expression OR any synonym matches `text`."""
    haystack = (text or "").lower()
    if not haystack:
        return False
    node = parse_expression(keyword_text)
    if _eval(node, haystack):
        return True
    return any(_term_in(s, haystack) for s in (synonyms or []))


def score_tender(
    *,
    keyword_text: str,
    synonyms: list[str],
    title: str | None,
    description: str | None,
    organisation: str | None,
    department: str | None,
    tender_state: str | None,
    user_state: str | None,
    user_industry: str | None,
) -> tuple[float, dict]:
    """Return (score 0-100, match-details dict)."""
    details: dict = {"matched_fields": []}
    score = 0.0

    if expression_matches(keyword_text, synonyms, title or ""):
        score += WEIGHT_TITLE
        details["matched_fields"].append("title")
    if expression_matches(keyword_text, synonyms, description or ""):
        score += WEIGHT_DESCRIPTION
        details["matched_fields"].append("description")
    org_blob = f"{organisation or ''} {department or ''}"
    if expression_matches(keyword_text, synonyms, org_blob):
        score += WEIGHT_ORGANISATION
        details["matched_fields"].append("organisation")

    if user_state and tender_state and user_state.strip().lower() == tender_state.strip().lower():
        score += WEIGHT_STATE
        details["matched_fields"].append("state")

    if user_industry:
        blob = f"{title or ''} {description or ''} {organisation or ''}".lower()
        industry_terms = [t for t in re.split(r"[,/&]| and ", user_industry.lower()) if t.strip()]
        if any(_term_in(t.strip(), blob) for t in industry_terms):
            score += WEIGHT_INDUSTRY
            details["matched_fields"].append("industry")

    details["keyword"] = keyword_text
    return round(score, 1), details


def score_band(score: float) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"
