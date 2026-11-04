"""Source-anchored evidence for expansion; no LLM, file or database operations."""
from __future__ import annotations

import copy
from html.parser import HTMLParser
import json
import re

VERSION = "source-spans-v1"


def numeric_view(content: str) -> tuple[str, bool]:
    """Render numeric evidence without treating HTML attributes/tags as quantities/operators."""
    class Renderer(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.parts = []
            self.tables = 0
            self.ambiguous = False
            self.hidden = 0

        def handle_starttag(self, tag, attrs):
            if tag in {"script","style"}:
                self.hidden += 1
            if tag == "table":
                self.tables += 1
                self.ambiguous |= self.tables > 1
                self.parts.append("\n")
            elif tag == "tr":
                self.parts.append("\n|")
            elif tag in {"td","th"}:
                # shortcut: merged cells need reviewed column mapping, never guess it.
                self.ambiguous |= any(k in {"rowspan","colspan"} and v != "1" for k,v in attrs)
            elif tag == "br":
                self.parts.append(" ")
            elif tag in {"p","div","li","ul","ol"}:
                self.parts.append(" " if self.tables else "\n")

        def handle_endtag(self, tag):
            if tag in {"script","style"}:
                self.hidden = max(0,self.hidden-1)
            elif tag in {"td","th"}:
                self.parts.append("|")
            elif tag in {"tr","table","p","div","li","ul","ol"}:
                self.parts.append(" " if self.tables and tag not in {"tr","table"} else "\n")
                if tag == "table":
                    self.tables = max(0,self.tables-1)

        def handle_data(self, data):
            if not self.hidden:
                self.parts.append(" ".join(data.split()) if self.tables else data)

    parser = Renderer()
    parser.feed(content)
    parser.close()
    # Preserve table-row boundaries; inline whitespace is not a column boundary.
    lines = [layout_view(line)[0] for line in "".join(parser.parts).splitlines()]
    return "\n".join(line for line in lines if line),parser.ambiguous or bool(parser.tables)


def layout_view(text: str) -> tuple[str, list[tuple[int, int]]]:
    """Normalize only whitespace/HTML line breaks, retaining original character offsets."""
    chars, offsets = [], []
    for token in re.finditer(r"<br\s*/?>|\s+|.", text, flags=re.I | re.S):
        value = token.group()
        if value.isspace() or re.fullmatch(r"<br\s*/?>", value, flags=re.I):
            if chars and chars[-1] != " ":
                chars.append(" ")
                offsets.append((token.start(), token.end()))
        else:
            chars.append(value)
            offsets.append((token.start(), token.end()))
    if chars and chars[-1] == " ":
        chars.pop()
        offsets.pop()
    return "".join(chars), offsets


def source_match(wanted: str, source: str, *, thai_spacing: bool = False) -> str | None:
    if not wanted:
        return None
    if wanted in source:
        return wanted
    view, offsets = layout_view(source)
    needle, _ = layout_view(wanted)
    if thai_spacing:
        def compact(text, positions):
            keep = [i for i,c in enumerate(text) if not (
                c==" " and 0<i<len(text)-1 and "\u0e00"<=text[i-1]<= "\u0e7f" and "\u0e00"<=text[i+1]<= "\u0e7f")]
            return "".join(text[i] for i in keep),[positions[i] for i in keep]
        view, offsets = compact(view,offsets)
        needle, _ = compact(needle,list(range(len(needle))))
    position = view.find(needle) if needle else -1
    if position < 0:
        return None
    start = offsets[position][0]
    end = offsets[position + len(needle) - 1][1]
    return source[start:end]


def segments(content: str) -> list[tuple[int, int, str]]:
    """Keep Markdown table rows separate and ordinary paragraphs intact."""
    result, start, end = [], None, 0
    def flush():
        nonlocal start
        if start is not None:
            raw = content[start:end]
            left = len(raw) - len(raw.lstrip())
            right = len(raw.rstrip())
            if right > left:
                result.append((start + left, start + right, raw[left:right]))
        start = None
    offset = 0
    for line in content.splitlines(keepends=True):
        table_row = line.lstrip().startswith("|")
        if not line.strip() or table_row:
            flush()
        if line.strip():
            if start is None:
                start = offset
            end = offset + len(line)
        if table_row:
            flush()
        offset += len(line)
    flush()
    return result


def catalog(primary: dict, contexts: list[dict]) -> list[dict]:
    spans = []
    for i, chunk in enumerate([primary, *contexts]):
        for n, (start, end, quote) in enumerate(segments(chunk["content"])):
            spans.append({"span_id":f"c{i}s{n}", "chunk_id":chunk["chunk_id"],
                          "role":"PRIMARY" if i == 0 else "CONTEXT",
                          "start":start,"end":end,"quote":quote,"text":layout_view(quote)[0]})
    return spans


def anchor_payload(payload: dict, primary: dict, contexts: list[dict]) -> dict:
    spans = catalog(primary, contexts)
    if not spans:
        raise ValueError("No source evidence spans")
    wire = copy.deepcopy(payload)
    wire["messages"][0]["content"] += (
        "\nSOURCE-SPAN WIRE CONTRACT overrides the quote/raw_text output instructions above: "
        "evidence items contain ONLY span_id selected from source_spans; never output chunk_id or quote. "
        "Each Fact uses raw_span_id instead of raw_text, selecting a PRIMARY span also listed in its evidence. "
        "Code will restore the ENTIRE original paragraph/table row, including conditions and exceptions. "
        "Keep Entity.name and value_text verbatim substrings of the selected span text. "
        "Do not manufacture an entity from a heading if it adds no useful subject identity. "
        "Selecting a span does not prove your interpretation: preserve program, column, date and audience scope."
    )
    user = json.loads(wire["messages"][1]["content"])
    user.pop("source_chunks",None)
    # The output contract already declares semantic types; storage metadata is not LLM work.
    user.pop("graph_schema",None)
    user["source_spans"] = [{k:s[k] for k in ("span_id","chunk_id","role","text")} for s in spans]
    wire["messages"][1]["content"] = json.dumps(user,ensure_ascii=False)
    definitions = wire["response_format"]["json_schema"]["schema"]["$defs"]
    definitions["Evidence"] = {"type":"object","properties":{"span_id":{"type":"string","enum":[s["span_id"] for s in spans]}},
                               "required":["span_id"],"additionalProperties":False}
    fact = definitions["Fact"]
    fact["properties"].pop("raw_text")
    fact["properties"]["raw_span_id"] = {"type":"string","enum":[s["span_id"] for s in spans if s["role"]=="PRIMARY"]}
    fact["required"] = ["raw_span_id" if key=="raw_text" else key for key in fact["required"]]
    return wire


def materialize(wire: dict, primary: dict, contexts: list[dict]) -> dict:
    """Resolve only allowed source IDs; never invent quotes or repair semantic values."""
    if not isinstance(wire,dict):
        raise ValueError("Extraction must be an object")
    result = copy.deepcopy(wire)
    spans = {s["span_id"]:s for s in catalog(primary,contexts)}
    for kind in ("entities","offerings","facts","has_tracks"):
        items = result.get(kind,[])
        if not isinstance(items,list):
            raise ValueError("Extraction collections must be lists")
        for item in items:
            if not isinstance(item,dict):
                raise ValueError("Extraction entries must be objects")
            evidence = item.get("evidence",[])
            if not isinstance(evidence,list) or not evidence or any(
                not isinstance(e,dict) or set(e)!={"span_id"} or not isinstance(e["span_id"],str) or e["span_id"] not in spans
                for e in evidence):
                raise ValueError("Invalid source evidence selection")
            selected = [spans[e["span_id"]] for e in evidence]
            if kind == "facts":
                raw_id = item.pop("raw_span_id",None)
                if "raw_text" in item or not isinstance(raw_id,str) or raw_id not in spans or spans[raw_id]["role"]!="PRIMARY" or raw_id not in {s["span_id"] for s in selected}:
                    raise ValueError("Fact must select PRIMARY evidence")
                item["raw_text"] = spans[raw_id]["quote"]
            item["evidence"] = [{"chunk_id":s["chunk_id"],"quote":s["quote"]} for s in selected]
            for field in ("name","value_text"):
                if isinstance(item.get(field),str):
                    match = next((m for s in selected if (m:=source_match(item[field],s["quote"],thai_spacing=field=="name")) is not None),None)
                    if match is not None:
                        item[field] = match
    return result


def exception_errors(content: str, raw_text: str) -> list[str]:
    """Require complete exception content, but not surrounding closing punctuation."""
    raw = layout_view(raw_text)[0]
    for _, _, paragraph in segments(content):
        if raw_text not in paragraph:
            continue
        text = layout_view(paragraph)[0]
        for marker in ("ยกเว้น","unless"):
            match = re.search(re.escape(marker),text,flags=re.I)
            if match:
                clause = text[match.start():].strip(" |()（）[]{}.,;:")
                if clause.lower() not in raw.lower():
                    return ["truncated_source_exception"]
    return []
