"""Validate the full corpus into sidecar contracts; never rewrite source chunks.

python3 graph/build/contracts.py [--check]
Unknown publication/effective dates stay null; no API or database operations.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from common import DATA, ROOT, fingerprint

CONTRACT_VERSION = "pilot-contract-v1"


def iso_date(value):
    if value is None or value == "":
        return None
    if type(value) is date:
        parsed = value
    else:
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("expected an explicit ISO date YYYY-MM-DD, not a numeric timestamp")
        parsed = date.fromisoformat(value)
    if parsed.year > 2400:
        raise ValueError("expected Gregorian ISO date, not an unlabelled BE year")
    return parsed


class SourceNotes(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    title: str | None = None
    source_uri: str | None = None
    source_url: str | None = None
    topic_tags: list[str] | None = None
    content_type: str | None = None
    published_at: date | None = None
    effective_from: date | None = None
    effective_until: date | None = None
    ingested_at: date | None = None
    verification_status: Literal["PENDING", "UNVERIFIED", "VERIFIED"] | None = None
    document_status: Literal["UNKNOWN", "ACTIVE", "SUPERSEDED", "REVOKED", "EXPIRED"] | None = None
    supersedes: list[str] | None = None
    verified: bool | None = None

    @field_validator("published_at", "effective_from", "effective_until", "ingested_at", mode="before")
    @classmethod
    def explicit_dates(cls, value):
        return iso_date(value)


def read_source_notes(path) -> dict:
    notes = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if not isinstance(notes, dict):
        raise ValueError("source_notes must map source IDs to metadata objects")
    return {key: SourceNotes.model_validate(value).model_dump(mode="json", exclude_unset=True) for key, value in notes.items()}


class SourceDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_uri: str = Field(min_length=1)
    topic_tags: list[str] = Field(min_length=1)
    content_type: str = "application/json"


class DocumentVersion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str
    version_id: str
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    published_at: date | None = None
    effective_from: date | None = None
    effective_until: date | None = None
    ingested_at: date | None = None
    verification_status: Literal["PENDING", "UNVERIFIED", "VERIFIED"] = "PENDING"
    document_status: Literal["UNKNOWN", "ACTIVE", "SUPERSEDED", "REVOKED", "EXPIRED"] = "UNKNOWN"
    supersedes: list[str] = Field(default_factory=list)

    @field_validator("published_at", "effective_from", "effective_until", "ingested_at", mode="before")
    @classmethod
    def explicit_dates(cls, value):
        return iso_date(value)

    @model_validator(mode="after")
    def check_dates_and_identity(self):
        if self.version_id != f"{self.source_id}@{self.content_hash[:16]}":
            raise ValueError("version_id must bind source_id to its content hash")
        if self.effective_from and self.effective_until and self.effective_until < self.effective_from:
            raise ValueError("effective_until precedes effective_from")
        if self.version_id in self.supersedes or len(set(self.supersedes)) != len(self.supersedes):
            raise ValueError("supersedes must not duplicate or include itself")
        if any(value and value.year > 2400 for value in (self.published_at, self.effective_from, self.effective_until, self.ingested_at)):
            raise ValueError("contract dates use Gregorian ISO dates, not unlabelled BE years")
        return self


class Chunk(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    chunk_id: str
    legacy_chunk_id: str = Field(min_length=1)
    version_id: str
    content: str = Field(min_length=1)
    page: int | None = Field(default=None, ge=1)
    chunk_index: int = Field(ge=1)

    @model_validator(mode="after")
    def check_identity(self):
        if self.chunk_id != f"{self.version_id}#{self.chunk_index:04d}":
            raise ValueError("canonical chunk_id must bind version and original position")
        return self


class NumericRange(BaseModel):
    """BETWEEN uses two bounds; unknown endpoint inclusivity is explicitly null."""
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    operator: Literal["BETWEEN"] = "BETWEEN"
    lower: float | int
    upper: float | int
    lower_inclusive: bool | None = None
    upper_inclusive: bool | None = None

    @model_validator(mode="after")
    def check_order(self):
        if self.lower > self.upper:
            raise ValueError("range lower bound exceeds upper bound")
        if self.lower == self.upper and (self.lower_inclusive is False or self.upper_inclusive is False):
            raise ValueError("equal range bounds cannot have an excluded endpoint")
        return self


def adapt(path, document: dict, annotation: dict) -> tuple[dict, list[str]]:
    meta = {**document.get("metadata", {}), **annotation}
    source_id = document["doc_id"]
    content_hash = fingerprint([{k: c.get(k) for k in ("content", "page", "section")} for c in document["chunks"]])
    version_id = f"{source_id}@{content_hash[:16]}"
    relative = str(path.relative_to(ROOT))
    source = SourceDocument(source_id=source_id, title=meta.get("title") or source_id,
        source_uri=meta.get("source_uri") or meta.get("source_url") or relative,
        topic_tags=meta.get("topic_tags") or [path.parent.name], content_type=meta.get("content_type") or "application/json")
    # last_updated in this repository's chunk generator was a processing date, not a policy date.
    ingested_at = meta["ingested_at"] if meta.get("ingested_at") is not None else meta.get("last_updated")
    version = DocumentVersion(source_id=source_id, version_id=version_id, content_hash=content_hash,
        published_at=meta.get("published_at"), effective_from=meta.get("effective_from"),
        effective_until=meta.get("effective_until"), ingested_at=ingested_at,
        document_status=meta.get("document_status") or "UNKNOWN",
        verification_status=meta.get("verification_status") or ("VERIFIED" if meta.get("verified") is True else "UNVERIFIED" if meta.get("verified") is False else "PENDING"),
        supersedes=[] if meta.get("supersedes") is None else meta["supersedes"])
    chunks = [Chunk(chunk_id=f"{version_id}#{i:04d}", legacy_chunk_id=c["chunk_id"], version_id=version_id,
                    chunk_index=i, content=c["content"], page=c.get("page")) for i, c in enumerate(document["chunks"], 1)]
    missing = [key for key in ("published_at", "effective_from") if getattr(version, key) is None]
    if version.document_status == "UNKNOWN":
        missing.append("document_status")
    if version.verification_status != "VERIFIED":
        missing.append("owner_verification")
    if not any(str(meta.get(key) or "").startswith(("http://", "https://")) for key in ("source_uri", "source_url")):
        missing.append("official_source_url")
    record = {"source": source.model_dump(mode="json"), "version": version.model_dump(mode="json"),
        "chunks": [c.model_dump() for c in chunks], "source_path": relative,
        "ingested_at_origin": "ingested_at" if meta.get("ingested_at") else "legacy_last_updated_day" if meta.get("last_updated") else "unknown"}
    return record, missing


def build_contracts() -> dict:
    notes_path = DATA / "inputs/source_notes.json"
    notes = read_source_notes(notes_path)
    records, gaps, errors, source_ids, chunk_ids = [], [], [], set(), set()
    paths = sorted((ROOT / "data/chunks").rglob("*.json"))
    for path in paths:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
            source_id = document["doc_id"]
            if source_id in source_ids:
                raise ValueError("duplicate source_id")
            source_ids.add(source_id)
            ids = [c["chunk_id"] for c in document["chunks"]]
            if len(ids) != len(set(ids)) or set(ids) & chunk_ids:
                raise ValueError("duplicate legacy chunk_id")
            chunk_ids.update(ids)
            record, missing = adapt(path, document, notes.get(source_id, {}))
            records.append(record)
            gaps.append({"source_id": source_id, "source_path": str(path.relative_to(ROOT)), "missing": missing,
                         "missing_page_chunks": sum(c["page"] is None for c in record["chunks"])})
        except (ValueError, KeyError, TypeError) as error:
            reason = error.errors(include_input=False, include_url=False) if isinstance(error, ValidationError) else str(error)
            errors.append({"source_path": str(path.relative_to(ROOT)), "error": reason})
    if not set(notes) <= source_ids:
        raise ValueError("source_notes must reference existing source IDs")
    return {"contract_version": CONTRACT_VERSION, "status": "VALIDATED_SIDECAR_NOT_POLICY_APPROVAL",
        "counts": {"files": len(paths), "valid": len(records), "chunks": sum(len(r["chunks"]) for r in records), "errors": len(errors)},
        "records": records, "metadata_gaps": gaps, "errors": errors}


def render_report(result: dict) -> str:
    counts = result["counts"]
    missing = Counter(field for record in result["metadata_gaps"] for field in record["missing"])
    lines = ["# ผลตรวจ data contract ทั้งคลัง", "", "[กลับคู่มือสร้างกราฟ](../../README.md)", "",
        f"ตรวจ {counts['files']} ไฟล์ · ผ่านโครงสร้าง {counts['valid']} · {counts['chunks']} chunks · ข้อผิดพลาด {counts['errors']}", "",
        "นี่คือ sidecar ที่เพิ่มสัญญาข้อมูล ไม่เขียนทับ chunks และไม่รับรองว่านโยบายยัง ACTIVE.",
        "SourceDocument แยกจาก DocumentVersion และ Chunk; canonical chunk_id ผูก version+ลำดับ ส่วน legacy_chunk_id คง ID ที่ Vector RAG ใช้อยู่.",
        "ingested_at มีความละเอียดระดับวัน; legacy last_updated จาก chunk generator ถูกระบุ origin ไว้ ไม่ใช้เป็น published_at/effective_from.",
        "source_uri ใช้ URL ที่ระบุไว้ หรือ path ของ JSON ที่เตรียมแล้ว; content_type=application/json ไม่ได้อ้างว่าเป็นชนิดไฟล์ต้นฉบับ PDF.", "",
        "## Metadata ที่ยังไม่บันทึก — ไม่ใช่เงื่อนไขรอทีม Data", "",
        "ตัวเลขด้านล่างตรวจ metadata ที่บันทึกไว้เท่านั้น ไม่ได้บอกว่าข้อมูลไม่มีในเอกสาร และยังไม่ได้สกัดวันที่/สถานะจากเนื้อหาครบทั้งคลัง.",
        "ให้ดึงข้อมูลที่ระบุชัดจากเอกสารพร้อม chunk/page/quote; ไม่พบหรือขัดกันคง null/UNKNOWN และตรวจเฉพาะจุด โดยเดินหน้ากราฟทดลองได้.",
        "owner_verification เป็นชื่อรายการ audit เดิม หมายถึงยังไม่มีการรับรองที่บันทึกไว้ ไม่ใช่ field บังคับหรือเงื่อนไขหยุด pilot; ไม่เปลี่ยน VERIFIED เพียงเพราะสกัดจากเอกสาร.",
        "ไม่อนุมาน ACTIVE จากวันประกาศ และไม่ใช้ปีการศึกษา วัน ingest หรือชื่อไฟล์แทนวันประกาศ/วันมีผล.", "",
        "| Field / รายการ audit | เอกสารที่ยังไม่บันทึก |", "| --- | ---: |"]
    lines.extend(f"| {field} | {count} |" for field, count in sorted(missing.items()))
    lines.extend(["", "## แยกตามเอกสาร", "", "| เอกสาร | ยังไม่บันทึก / รายการ audit | Chunks ไม่ทราบหน้า |", "| --- | --- | ---: |"])
    lines.extend(f"| {r['source_id']} | {', '.join(r['missing']) or 'ไม่มี'} | {r['missing_page_chunks']} |" for r in result["metadata_gaps"])
    if result["errors"]:
        lines.extend(["", "## ข้อผิดพลาด", "", "```json", json.dumps(result["errors"], ensure_ascii=False, indent=2, default=str), "```"])
    lines.extend(["", "ผลละเอียด: [contracts.json](../results/contracts.json)", "",
        "ยังไม่ได้ทำ workflow upsert/supersede/delete ในฐานข้อมูล และไม่ต้องรอส่งรายงานให้ทีม Data ก่อนทดลองกราฟ การขาดวันที่ไม่ถูกเติมด้วยการเดา."])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Compare saved sidecar/review without writes")
    args = parser.parse_args()
    result = build_contracts()
    outputs = {"results/contracts.json": json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n",
               "review/contracts.md": render_report(result)}
    for relative, content in outputs.items():
        path = DATA / relative
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                parser.error(f"Contract output drift: {relative}; regenerate first")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    print(f"Contracts: {result['counts']}; no source/API/database writes")
    if result["errors"]:
        parser.exit(1, "Source contract errors; see review/contracts.md\n")


if __name__ == "__main__":
    main()
