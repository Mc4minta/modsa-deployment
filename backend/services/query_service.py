"""Conservative rules and source-heading scope for an isolated pilot only.

Unknowns stay unknown; these annotations never establish ACTIVE/effective policy.
The caller supplies the complete, hash-checked source versions, not gold answers.
"""
from __future__ import annotations

from collections import defaultdict
import re

from langchain_core.documents import Document

from schemas.retrieval import QueryIntent

METHOD = "conservative-postfilter-no-refill-v1"
TERMS = {
    "scholarship": ("ทุน", "gpax", "gpa", "วิชาการดีเด่น", "ความสามารถพิเศษ"),
    "fees": ("ค่าใช้จ่าย", "ค่าเทอม", "ค่าหน่วยกิต", "ค่าบำรุง"),
    "academic_rules": ("ข้อบังคับ", "ระเบียบสอบ", "ระเบียบการสอบ", "ข้อวินัย", "ทุจริต"),
    "registration": ("ลงทะเบียน", "acis", "probation", "section", "คู่มือ", "ที่ปรึกษา"),
    "others": ("บัตรนักศึกษา", "อีเมล", "เบอร์", "ติดต่อ"),
}
NEGATION = r"(?:ไม่ใช่|ไม่เอา|ยกเว้น|นอกจาก|เว้น)\s*"
YEAR = r"25\d{2}"
THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
HEADER = re.compile(
    r"(?m)^[ \t]*(?:เรื่อง[^\n]{0,180}ประจำปีการศึกษา[ \t]*(?P<title_year>25\d{2})[^\n]*"
    r"|รอบที่[ \t]*(?P<round>\d{1,2})[ \t]*\([ \t]*ปีการศึกษา[ \t]*(?P<round_year>25\d{2})[ \t]*\))[ \t]*$"
)


def normalized(text: str) -> str:
    return text.lower().translate(THAI_DIGITS)


def parse_query_intent(question: str) -> QueryIntent:
    text = normalized(question)
    categories = {category for category, terms in TERMS.items() if any(term in text for term in terms)}
    if ("ปฏิทิน" in text or "ภาคการศึกษา" in text or re.search(r"ภาค\s*\d/25\d{2}", text)
            or (any(term in text for term in ("วันแรก", "วันสุดท้าย", "ช่วงไหน", "ช่วงใด", "วันไหน"))
                and any(term in text for term in ("ลงทะเบียน", "ชำระ", "คืนสภาพ")))):
        categories.add("academic_calendar")
    years = sorted({int(year) for year in re.findall(YEAR, text)}) if categories & {"scholarship", "academic_calendar"} else []
    rounds = sorted({int(value) for value in re.findall(r"รอบ(?:ที่)?\s*(\d{1,2})(?!\d)", text)}) if "scholarship" in categories else []
    ambiguities = []
    if 0 in rounds:
        rounds = []
        ambiguities.append("invalid_round")
    if re.search(NEGATION + r"(?:ปี(?:การศึกษา)?\s*)?" + YEAR, text):
        years = []
        ambiguities.append("negated_year")
    if re.search(NEGATION + r"รอบ", text):
        rounds = []
        ambiguities.append("negated_round")
    if (re.search(YEAR + r"\s*(?:ถึง|[-–—]|to)\s*(?:ปี(?:การศึกษา)?\s*)?" + YEAR, text)
            or re.search(r"ระหว่าง\s*ปี(?:การศึกษา)?\s*" + YEAR + r"\s*(?:กับ|และ)\s*(?:ปี(?:การศึกษา)?\s*)?" + YEAR, text)):
        years = []
        ambiguities.append("year_range")
    if re.search(r"(?:ก่อน|หลัง|ตั้งแต่|ไม่เกิน|อย่างน้อย)\s*(?:ปี(?:การศึกษา)?|พ\.ศ\.?)?\s*" + YEAR, text) or re.search(YEAR + r"\s*เป็นต้นไป", text):
        years = []
        ambiguities.append("year_comparison")
    if re.search(r"รอบ(?:ที่)?\s*\d+\s*(?:ถึง|[-–—]|to)\s*(?:รอบ(?:ที่)?\s*)?\d+", text):
        rounds = []
        ambiguities.append("round_range")
    if re.search(r"(?:ก่อน|หลัง|ตั้งแต่|ไม่เกิน|อย่างน้อย)\s*รอบ", text) or re.search(r"รอบ(?:ที่)?\s*\d+\s*(?:ขึ้นไป|เป็นต้นไป)", text):
        rounds = []
        ambiguities.append("round_comparison")
    domain_terms = "|".join(re.escape(term) for values in TERMS.values() for term in values)
    if re.search(NEGATION + r"(?:" + domain_terms + r")", text):
        categories, years, rounds = set(), [], []
        ambiguities.append("negated_category")
    if any(term in text for term in ("ปีนี้", "ปัจจุบัน", "ล่าสุด")):
        ambiguities.append("current_applicability_unknown")
    # shortcut: rules only; ambiguous operators disable that field, not the whole query.
    return QueryIntent(categories=sorted(categories), academic_years=years, rounds=rounds, ambiguities=ambiguities)


def source_key(doc: Document) -> tuple[str, str, str]:
    return tuple(value if isinstance(value, str) else "" for value in
                 (doc.metadata.get(key) for key in ("source_id", "version_id", "content_hash")))


class PilotScopeFilter:
    def __init__(self, documents: list[Document]):
        groups = defaultdict(list)
        for doc in documents:
            key = source_key(doc)
            if all(isinstance(value, str) and value for value in key):
                groups[key].append(doc)
        self.scopes = {}
        self.originals = {}
        for key, docs in groups.items():
            years, rounds, evidence = set(), set(), []
            leading_years, leading_rounds = set(), set()
            for doc in docs:
                chunk_id = doc.metadata.get("chunk_id")
                if not isinstance(chunk_id, str) or not chunk_id:
                    raise ValueError("Scope evidence requires source chunk identity")
                identity = (*key, chunk_id)
                if identity in self.originals:
                    raise ValueError("Duplicate chunk in scope source corpus")
                self.originals[identity] = doc.page_content
                category = doc.metadata.get("category")
                if not isinstance(category, str) or category not in {"scholarship", "academic_calendar"}:
                    continue
                body = doc.page_content.split("\n", 1)[1] if doc.page_content.startswith("[") and "\n" in doc.page_content else doc.page_content
                for match in HEADER.finditer(body.translate(THAI_DIGITS)):
                    year = int(match["title_year"] or match["round_year"])
                    admission_round = int(match["round"]) if match["round"] else None
                    years.add(year)
                    if admission_round is not None:
                        rounds.add(admission_round)
                    leading = type(doc.metadata.get("source_index")) is int and doc.metadata["source_index"] == 0 and match.start() < 600
                    if leading:
                        leading_years.add(year)
                        if admission_round is not None:
                            leading_rounds.add(admission_round)
                    # Digit-only normalization preserves offsets and the original evidence text.
                    evidence.append({"chunk_id": chunk_id, "quote": body[match.start():match.end()],
                                     "leading_header": leading, "academic_year": year, "round": admission_round})
            year = next(iter(years)) if len(years) == len(leading_years) == 1 else None
            admission_round = next(iter(rounds)) if year is not None and len(rounds) == len(leading_rounds) == 1 else None
            self.scopes[key] = {"source_id": key[0], "version_id": key[1], "content_hash": key[2],
                "academic_year": year, "round": admission_round, "evidence": evidence,
                "scope_kind": "experimental_document_heading_not_policy_status"}

    def describe(self) -> list[dict]:
        return [self.scopes[key] for key in sorted(self.scopes)]

    def apply(self, documents: list[Document], intent: QueryIntent) -> tuple[list[Document], list[dict]]:
        kept, decisions = [], []
        for doc in documents:
            reasons, unknown = [], []
            category = doc.metadata.get("category")
            if intent.categories:
                if not isinstance(category, str) or category not in {*TERMS, "academic_calendar"}:
                    unknown.append("category")
                elif category not in intent.categories:
                    reasons.append("category_mismatch")
            key = source_key(doc)
            scope = self.scopes.get(key)
            chunk_id = doc.metadata.get("chunk_id")
            if not isinstance(chunk_id, str) or self.originals.get((*key, chunk_id)) != doc.page_content:
                scope = None
            for field, requested in (("academic_year", intent.academic_years), ("round", intent.rounds)):
                if not requested:
                    continue
                value = scope.get(field) if scope else None
                if value is None:
                    unknown.append(field)
                elif value not in requested:
                    reasons.append(field + "_mismatch")
            keep = not reasons
            decisions.append({"chunk_id": doc.metadata.get("chunk_id"), "version_id": doc.metadata.get("version_id"),
                "decision": "keep" if keep else "reject", "reasons": reasons, "unknown_fields": unknown})
            if keep:
                kept.append(doc)
        return kept, decisions
