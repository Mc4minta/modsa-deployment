"""Build new document graphs using the frozen schema, independently of pilot QAs."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import tempfile
import time
import urllib.error
import urllib.request
from uuid import uuid4

from common import DATA, ROOT, BASE_URL as MIMO_BASE_URL, api_key, fingerprint, ssl_context
from contracts import adapt
from extract import MODEL as MIMO_MODEL, PROMPT_VERSION, payload_for, stage as legacy_stage, export_graph
from source_evidence import VERSION as EVIDENCE_VERSION, anchor_payload, catalog, materialize
from load_graph import CONSTRAINT, connection_settings, make_plan, merge_run, other_content, assert_run, batch_verification
from prepare import check_schema

OUTPUT = ROOT / "graph/expansions"
BASE_URL = "https://openrouter.ai/api/v1"
MODEL = "meta/muse-spark-1.3-contributor"
MAX_OUTPUT_TOKENS = 6000
REASONING_EFFORT = "minimal"
VALIDATOR_PROFILE = "source-layout-v4"
REPAIR_VERSION = "bounded-source-only-v1"
REPAIR_PROMPT_VERSION = "typed-scope-v2"
MIMO_FOCUS = ("Extract the important facts, rules, procedures, fees, dates and exceptions explicitly stated "
         "in PRIMARY. Preserve document/section/program/year/audience scope. Do not assume this is "
         "a scholarship document. If no supported semantic facts exist, return empty lists and explain "
         "the limitation in unresolved. Do not infer current policy or resolve ambiguous eligibility.")
FOCUS_VERSION = "general-facts-v2"
FOCUS = ("Extract useful explicit relationships and facts from PRIMARY, whether numeric or non-numeric: "
         "contact channels, addresses, official service links, service purposes and responsibilities, "
         "policy applicability, audiences and exclusions, as well as rules, procedures, fees and dates. "
         "Preserve document/program/year/audience scope and conditions. No numeric value is required "
         "for a valid fact. Do not infer current policy, eligibility or unstated relationships. "
         "Return no facts only when PRIMARY truly lacks a supported relationship (e.g. a contents page "
         "or navigation labels); explain ambiguity, unsupported types or missing information in unresolved.")


def stage(primary, contexts, record, schema):
    return legacy_stage(primary,contexts,record,schema,source_layout=True)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def reported_usage(value):
    """Keep numeric provider counters only, never estimate missing/billable tokens."""
    if not isinstance(value, dict):
        return {}
    usage = {k:value[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens")
             if type(value.get(k)) is int and value[k] >= 0}
    details = value.get("completion_tokens_details",{})
    reasoning = details.get("reasoning_tokens") if isinstance(details,dict) else None
    reasoning = value.get("reasoning_tokens",reasoning)
    if type(reasoning) is int and 0 <= reasoning <= usage.get("completion_tokens",-1):
        usage.update(reasoning_tokens=reasoning,visible_tokens=usage["completion_tokens"]-reasoning)
    return usage


def start_metrics(batch, mode, missing, max_calls, prepare_seconds):
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")+"-"+uuid4().hex[:12]
    folder = OUTPUT/"batches"/batch["batch_id"]/"offline"/run_id
    metrics = {"format":"modsa-offline-v1", "run_id":run_id,"batch_id":batch["batch_id"],
        "mode":mode,"status":"RUNNING","started_at":utc_now(),"model":MODEL,"base_url":BASE_URL,
        "evidence_version":EVIDENCE_VERSION,
        "validator_profile":VALIDATOR_PROFILE,
        "focus_version":FOCUS_VERSION,
        "documents":len(batch["documents"]),"chunks":sum(len(d["jobs"]) for d in batch["documents"]),
        "missing_at_start":missing,"cache_hits_at_start":sum(len(d["jobs"]) for d in batch["documents"])-missing,
        "max_calls":max_calls,"generation_settings":{"max_tokens":MAX_OUTPUT_TOKENS,"reasoning_effort":REASONING_EFFORT},
        "machine":{"system":platform.system(),"architecture":platform.machine(),
        "python":platform.python_version(),"cpu_count":os.cpu_count()},
        "phase_seconds":{"prepare_and_cache_check":prepare_seconds},"_folder":folder,"_attempts":{}}
    save(folder/"stats.json",{k:v for k,v in metrics.items() if not k.startswith("_")})
    return metrics


def request_event(metrics, event):
    if metrics is None:
        return
    event = {**event,"at":utc_now()}
    # Flush the intent before calling the provider, and the outcome before cache publication.
    with (metrics["_folder"]/"requests.jsonl").open("a",encoding="utf-8") as stream:
        stream.write(json.dumps(event,ensure_ascii=False)+"\n")
        stream.flush()
        os.fsync(stream.fileno())
    metrics["_attempts"][event["attempt_id"]] = event


def finish_metrics(metrics, started):
    attempts = list(metrics["_attempts"].values())
    finished = [r for r in attempts if r["event"] == "finished"]
    http = [r for r in finished if r.get("api_attempted") is True]
    uncertain = sum(r["event"] != "finished" or r.get("api_attempted") is None
                    or r.get("dispatch_unknown") is True for r in attempts)
    counters = ("prompt_tokens","completion_tokens","total_tokens")
    complete_usage = sum(all(k in r.get("usage",{}) for k in counters) for r in http)
    result = {k:v for k,v in metrics.items() if not k.startswith("_")}
    result.update(finished_at=utc_now(),process_seconds=time.perf_counter()-started,
        task_attempts=len(attempts),confirmed_http_attempts=len(http),
        http_dispatch_unknown=uncertain,successful_tasks=sum(r.get("success") is True for r in finished),
        failed_tasks=sum(r.get("success") is False for r in finished),
        usage_complete=complete_usage == len(http) and uncertain == 0,
        http_attempts_with_complete_usage=complete_usage,
        http_attempts_with_missing_usage=len(http)-complete_usage,
        reported_tokens={k:sum(r.get("usage",{}).get(k,0) for r in http) for k in counters},
        failures=[{k:r.get(k) for k in ("attempt_id","chunk_id","request_hash","error","transport_error_type","http_status","rejected_reasons")}
                  for r in finished if r.get("success") is False])
    result["completed_chunks_this_run"] = len({r.get("chunk_id") for r in finished if r.get("success") is True})
    detailed = [r for r in http if "reasoning_tokens" in r.get("usage",{})]
    result["reasoning_usage"] = {"reported_reasoning_tokens":sum(r["usage"]["reasoning_tokens"] for r in detailed),
        "reported_visible_tokens":sum(r["usage"]["visible_tokens"] for r in detailed),
        "http_attempts_with_details":len(detailed),"http_attempts_without_details":len(http)-len(detailed)}
    result["ready_chunks_after_run"] = result["cache_hits_at_start"]+result["completed_chunks_this_run"]
    if result["status"] == "RUNNING":
        result["status"] = "INTERRUPTED"
    result["by_attempt_kind"] = {kind:{"attempts":sum(r.get("attempt_kind","initial")==kind for r in attempts),
        "reported_tokens":{k:sum(r.get("usage",{}).get(k,0) for r in http if r.get("attempt_kind","initial")==kind)
                           for k in counters}} for kind in ("initial","repair")}
    folder = metrics["_folder"]
    save(folder/"stats.json",result)
    lines = ["# Offline run", "", f"Status: {result['status']} · mode: {result['mode']}", "",
        f"Documents/chunks: {result['documents']}/{result['chunks']}",
        f"Cache hits at start: {result['cache_hits_at_start']} (not new API work)",
        f"Process seconds: {result['process_seconds']:.3f}",
        f"Confirmed HTTP attempts: {len(http)}; uncertain dispatch: {uncertain}",
        f"Successful/failed tasks: {result['successful_tasks']}/{result['failed_tasks']}",
        f"Provider-reported tokens only: {result['reported_tokens']}",
        f"Token accounting complete: {result['usage_complete']}; requests missing usage: {len(http)-complete_usage}", "",
        "Missing usage is UNKNOWN, not zero tokens or zero cost. Intent-only records may have reached the provider.",
        "No pricing/GPU-seconds estimates. Process time includes measurement I/O, excludes earlier runs and idle time between resumes.",
        "Each invocation has a separate folder; add all attempts across invocations when accounting for retries.",
        "See stats.json for phase timing and failures; requests.jsonl for durable per-attempt events.", ""]
    (folder/"README.md").write_text("\n".join(lines),encoding="utf-8")
    print(f"OFFLINE STATS: {folder.relative_to(ROOT)}/stats.json",flush=True)


def request_payload(primary, contexts, schema, repair=None):
    payload = payload_for({**primary, "focus": FOCUS}, contexts, schema)
    payload["model"] = MODEL
    payload["max_tokens"] = MAX_OUTPUT_TOKENS
    payload["reasoning"] = {"effort":REASONING_EFFORT}
    payload["provider"] = {"allow_fallbacks":False,"require_parameters":True}
    payload["messages"][0]["content"] += (
        "\nScalar numeric facts MUST set value_text=null when value_number is non-null, and supply an operator. "
        "Keep the original wording in raw_text and the unit in unit, not in value_text. "
        "Text facts MUST set value_number=null. Do not invent numeric values or operators to satisfy this contract."
        "\nNon-numeric facts are first-class facts, not unsupported content. An explicit office contact, "
        "service URL/purpose, responsibility, document audience or exclusion can be a Fact about an "
        "office/system/procedure/policy/student_group Entity using the existing types. Use kind=fact "
        "for descriptive assertions and kind=rule for obligations/restrictions. Contact identifiers "
        "(phone/email/address/URL) are exact value_text strings, not arithmetic quantities: "
        "value_number/operator/unit=null. Do not reject supported descriptive facts because degree, "
        "round, fee or numeric eligibility is absent. Contents-page titles/page numbers alone do not "
        "establish service features, eligibility or policy. Never invent facts just to avoid an empty result."
    )
    payload = anchor_payload(payload,primary,contexts)
    if repair is not None:
        payload["messages"][0]["content"] += (
            "\nREPAIR CONTRACT: An ordinary fee, tuition, confirmation charge or degree program is NOT a scholarship. "
            "Use fee/program/program_track entities; create an Offering only for a real scholarship. "
            "A scholarship identity needs explicit scholarship/fellowship/grant evidence. "
            "Offering degree must be a verbatim university study-level phrase in selected evidence, "
            "not an entry qualification. Academic year requires an explicit academic-year label; "
            "publication/update dates and filename years are NOT academic years. A semester is NOT a round. "
            "Do not invent an Offering just to attach a fact: facts can refer directly to entities. "
            "For scalar operators leave all four range fields null. BETWEEN alone uses range fields. "
            "If the same number has ambiguous bounds in different clauses, preserve the supported rule "
            "as exact value_text with numeric fields null, rather than guessing. Numeric values must "
            "appear as digits in PRIMARY; preserve written-out numbers as exact text. "
            "Attach required table headers to evidence. Keep nonnumeric facts and all applicable exceptions."
        )
        fact_schema = payload["response_format"]["json_schema"]["schema"]["$defs"]["Fact"]
        fact_schema["anyOf"] = [
            {"properties":{"operator":{"const":"BETWEEN"},"value_number":{"type":"null"},
                           "value_text":{"type":"null"},"value_lower":{"type":"number"},
                           "value_upper":{"type":"number"}},"required":["value_lower","value_upper"]},
            {"properties":{"operator":{"enum":[None,"EQ","LTE","GTE","LT","GT","NE"]},
                           **{k:{"type":"null"} for k in ("value_lower","value_upper","lower_inclusive","upper_inclusive")}}}
        ]
        assistant = {"role":"assistant","content":repair.get("raw_response") or json.dumps(repair.get("extraction",{}),ensure_ascii=False)}
        if repair.get("reasoning_details"):
            assistant["reasoning_details"] = copy.deepcopy(repair["reasoning_details"])
        payload["messages"].extend([
            assistant,
            {"role":"user","content":json.dumps({"task":
                "Correct this extraction ONCE using only the same PRIMARY/CONTEXT and schema. "
                "Do not invent quotes, facts, refs or values. Keep every supported fact possible. "
                "For scalar numeric facts use value_number and set value_text=null; text facts use value_number=null. "
                "Use only supplied span_id values; each raw_span_id must select PRIMARY evidence. "
                "For rules select the complete applicable exception span. "
                "Unsupported or ambiguous information must be explicitly described in unresolved, not silently removed. "
                "Do not return an empty extraction just to pass validation. No policy approval. Return complete JSON only.",
                "validation_errors":repair.get("validation",{}).get("rejected") or [{"reason":repair.get("error","invalid response")}],
                "repair_version":REPAIR_VERSION,"repair_prompt_version":REPAIR_PROMPT_VERSION},ensure_ascii=False)}])
    return payload


def cache_key(primary, contexts, schema, source):
    return fingerprint({"payload":request_payload(primary, contexts, schema), "source":source,
                        "prompt_version":PROMPT_VERSION, "expansion_version":"generic-v1", "base_url":BASE_URL,
                        "evidence_version":EVIDENCE_VERSION})


def mimo_cache_key(primary, contexts, schema, source):
    # Match the historical request exactly; never relabel it as an OpenRouter response.
    payload = payload_for({**primary,"focus":MIMO_FOCUS},contexts,schema)
    return fingerprint({"payload":payload,"source":source,
                        "prompt_version":PROMPT_VERSION,"expansion_version":"generic-v1"})


def expansion_schema(base):
    """Add metadata properties without rewriting the historical frozen pilot."""
    check_schema(base)
    schema = copy.deepcopy(base)
    schema["schema_version"] += "+source-metadata-v1"
    additions = {"SourceDocument": {"source_uri":"STRING", "topic_tags":"STRING_LIST", "content_type":"STRING"},
                 "DocumentVersion": {"effective_until":"DATE", "ingested_at":"DATE", "supersedes":"STRING_LIST"}}
    for node in schema["node_types"]:
        existing = {p["name"]:p["type"] for p in node["properties"]}
        for name, kind in additions.get(node["label"], {}).items():
            if name in existing and existing[name] != kind:
                raise ValueError("Incompatible expansion metadata property")
            if name not in existing:
                node["properties"].append({"name":name,"type":kind})
    schema["fingerprint"] = fingerprint({k:v for k,v in schema.items() if k != "fingerprint"})
    check_schema(schema)
    return schema


def prepare(input_path, reuse_mimo_cache=False):
    """A file/directory is a selection of whole document versions, not pilot IDs."""
    base = (ROOT / "data/chunks").resolve()
    path = Path(input_path).resolve()
    if not path.is_relative_to(base) or not path.exists():
        raise ValueError("--input must be an existing JSON file/directory under data/chunks")
    paths = sorted(path.rglob("*.json")) if path.is_dir() else [path]
    if not paths:
        raise ValueError("No chunk JSON files selected")
    schema = expansion_schema(read(DATA / "inputs/schema.json"))
    documents, source_ids, chunk_ids = [], set(), set()
    for file in paths:
        if file.suffix != ".json" or not file.resolve().is_relative_to(base):
            raise ValueError("Unsupported file or symlink outside data/chunks")
        record, _ = adapt(file, read(file), {})
        source_id = record["source"]["source_id"]
        if source_id in source_ids or not record["chunks"]:
            raise ValueError("Duplicate source_id or document without chunks")
        source_ids.add(source_id)
        source = {**record["source"], **record["version"], "source_path":record["source_path"]}
        chunks = []
        for index, chunk in enumerate(record["chunks"]):
            cid = chunk["legacy_chunk_id"]
            if cid in chunk_ids:
                raise ValueError("Duplicate chunk_id in selected input")
            chunk_ids.add(cid)
            # The reused validator calls this field pilot_id; here it is a generated job ID, not a pilot selection.
            chunks.append({"pilot_id":fingerprint([source["version_id"],cid]), "chunk_id":cid,
                "source_id":source_id,"version_id":source["version_id"],"source_index":index,
                "category":file.parent.name,"page":chunk["page"],"content":chunk["content"],"role":"primary"})
        jobs = []
        for index, primary in enumerate(chunks):
            # shortcut: first chunk + immediate neighbours; section-aware context needs separate evaluation.
            indices = sorted({0, index-1, index+1} - {index, -1, len(chunks)})
            context = [chunks[i] for i in indices]
            key = cache_key(primary, context, schema, source)
            job = {"primary":primary,"contexts":context,"key":key,"schema":schema}
            if reuse_mimo_cache and not (OUTPUT/"cache"/(key+".json")).exists():
                legacy = {**job,"key":mimo_cache_key(primary,context,schema,source)}
                record = cached(legacy)
                if record is not None and not record.get("error") and record.get("model") == MIMO_MODEL:
                    if not stage(primary,context,record,schema)["rejected"]:
                        job = {**legacy,"reuse_only":True}
            jobs.append(job)
        documents.append({"source":source,"jobs":jobs})
    batch_id = fingerprint({"schema":schema,"documents":[
        {"source":d["source"],"requests":[j["key"] for j in d["jobs"]]} for d in documents]})
    return {"batch_id":batch_id,"schema":schema,"documents":documents}


def cached(job):
    path = OUTPUT/"cache"/(job["key"]+".json")
    if not path.exists():
        if job.get("reuse_only"):
            raise ValueError("Reused MiMo cache disappeared; refusing to send a new request under its identity")
        return None
    record = read(path)
    raw_hash = fingerprint(record)
    if record.get("request_hash") != job["key"]:
        raise ValueError(f"Cache identity mismatch for {job['key']}; refusing API fallback")
    if record.get("validator_profile") != VALIDATOR_PROFILE and record.get("error") in (None,"validation_failed") and isinstance(record.get("extraction"),dict):
        original_hash = fingerprint(record)
        record = copy.deepcopy(record)
        record.pop("error",None)
        validation = stage(job["primary"],job["contexts"],record,job["schema"])
        record.update(validation=validation,validator_profile=VALIDATOR_PROFILE,
                      revalidation={"source_record_hash":original_hash,"profile":VALIDATOR_PROFILE},
                      coverage_status="CANDIDATES_UNREVIEWED" if validation["facts"] else "EMPTY_NEEDS_REVIEW")
        if validation["rejected"]:
            record["error"] = "validation_failed"
    review_path = OUTPUT/"reviews"/(job["key"]+".json")
    if review_path.exists():
        record = apply_source_review(job,record,raw_hash,read(review_path))
    if job.get("reuse_only") and (record.get("error") or record.get("model") != MIMO_MODEL):
        raise ValueError("Reused MiMo cache changed; refusing API fallback")
    return record


def apply_source_review(job, record, raw_hash, review):
    """Apply explicit source-backed curation to a copy, never overwrite model responses."""
    if (review.get("format") != "modsa-source-review-v1" or review.get("request_hash") != job["key"]
            or review.get("base_record_hash") != raw_hash or review.get("policy_status") != "PENDING"
            or review.get("reviewer") != "codex-source-review"):
        raise ValueError("Source review identity/status mismatch; review the current response again")
    if record.get("error") not in (None,"validation_failed") or not isinstance(record.get("extraction"),dict):
        raise ValueError("Source review requires an existing extraction, not an API failure")
    result = copy.deepcopy(record)
    facts = {f["ref"]:f for f in result["extraction"]["facts"]}
    edits = review.get("edits")
    if not isinstance(edits,list) or not edits or len(edits)>len(facts):
        raise ValueError("Source review needs explicit fact edits")
    seen, deferred = set(), []
    numeric_fields = {"value_number","operator","value_text","value_lower","value_upper",
                      "lower_inclusive","upper_inclusive"}
    for edit in edits:
        ref = edit.get("ref")
        fact = facts.get(ref)
        if ref in seen or fact is None or edit.get("before_hash") != fingerprint(fact) or not edit.get("reason"):
            raise ValueError("Source review target changed, duplicated or missing its rationale")
        seen.add(ref)
        if edit.get("action") == "source_scalar":
            changes = edit.get("changes",{})
            quantity = fact.get("value_number")
            if quantity is None and fact.get("operator")=="BETWEEN" and fact.get("value_lower")==fact.get("value_upper"):
                quantity = fact.get("value_lower")
            if (set(changes) != numeric_fields or changes["operator"] not in {"LTE","GTE","LT","GT","NE"}
                    or type(quantity) not in (int,float) or changes["value_number"] != quantity
                    or any(changes[k] is not None for k in numeric_fields-{"value_number","operator"})):
                raise ValueError("Scalar review may only restore an evidence-validated numeric representation")
            fact.update(changes)
        elif edit.get("action") == "source_text":
            if "changes" in edit:
                raise ValueError("Text review restores the source, never accepts replacement prose")
            fact.update({k:None for k in numeric_fields})
            fact.update(value_text=fact["raw_text"],unit=None,
                        predicate="ข้อความข้อกำหนดตามหลักฐานต้นฉบับ — ยังไม่ยืนยันการตีความเชิงตัวเลข")
            deferred.append(ref)
        else:
            raise ValueError("Unsupported source review action; records cannot be deleted")
        result["extraction"]["unresolved"].append(f"AI source review (PENDING), {ref}: {edit['reason']}")
    result.pop("error",None)
    validation = stage(job["primary"],job["contexts"],result,job["schema"])
    result.update(validation=validation,validator_profile=VALIDATOR_PROFILE,
        source_review={"review_hash":fingerprint(review),"base_record_hash":raw_hash,
                       "reviewer":review["reviewer"],"policy_status":"PENDING","deferred_numeric_facts":deferred,
                       "edits":edits},
        coverage_status="SOURCE_TEXT_NEEDS_REVIEW" if deferred else "CANDIDATES_UNREVIEWED")
    if validation["rejected"]:
        result["error"] = "validation_failed"
    return result


def call(primary, contexts, schema, repair=None):
    """One HTTP request, no model repair/provider fallback or automatic retry."""
    record = {"model":MODEL,"base_url":BASE_URL,"focus_version":FOCUS_VERSION,"api_attempted":False,"usage":{}}
    started = None
    try:
        key = api_key("OPENROUTER_API_KEY")
        request = urllib.request.Request(BASE_URL+"/chat/completions",
            data=json.dumps(request_payload(primary, contexts, schema, repair)).encode(),
            headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"})
        context = ssl_context()
        started = time.perf_counter()
        record["api_attempted"] = True
        with urllib.request.urlopen(request,context=context,timeout=150) as response:
            record["http_status"] = response.status
            body = json.load(response)
        if isinstance(body.get("id"),str):
            record["generation_id"] = body["id"]
        cost = body.get("usage",{}).get("cost") if isinstance(body.get("usage"),dict) else None
        if type(cost) in (int,float) and 0 <= cost < float("inf"):
            record["provider_cost_usd"] = cost
        record["usage"] = reported_usage(body.get("usage"))
        choice = body["choices"][0]
        record["finish_reason"] = choice.get("finish_reason")
        record["raw_response"] = choice["message"].get("content") or ""
        if choice["message"].get("reasoning_details"):
            record["reasoning_details"] = choice["message"]["reasoning_details"]
        if choice.get("finish_reason") != "stop":
            record["error"] = "incomplete_generation"
        else:
            record["anchored_extraction"] = json.loads(record["raw_response"])
            try:
                record["extraction"] = materialize(record["anchored_extraction"],primary,contexts)
            except ValueError:
                record.update(error="validation_failed",validation={"rejected":[
                    {"kind":"response","reason":"invalid_evidence_selection"}]})
            record["evidence_version"] = EVIDENCE_VERSION
            record["source_spans"] = [{k:s[k] for k in ("span_id","chunk_id","start","end")}
                                      for s in catalog(primary,contexts)]
    except urllib.error.HTTPError as error:
        record.update(error="HTTPError",http_status=error.code)
    except urllib.error.URLError as error:
        record.update(error="URLError",transport_error_type=type(error.reason).__name__)
    except Exception as error:
        record["error"] = type(error).__name__
    finally:
        record["http_seconds"] = time.perf_counter()-started if started is not None else None
    return record


def repairable(record):
    return bool(record and record.get("raw_response")) and record.get("error") in {
        "validation_failed","JSONDecodeError","incomplete_generation"}


def repair_marker(job):
    path = OUTPUT/"cache/repairs"/(job["key"]+".json")
    if path.exists():
        marker = read(path)
        if marker.get("request_hash") != job["key"] or marker.get("repair_version") != REPAIR_VERSION:
            raise ValueError("Repair reservation identity mismatch; refusing new request")
        return marker
    return None


def initial_marker(job):
    path = OUTPUT/"cache/initial"/(job["key"]+".json")
    if not path.exists():
        return None
    marker = read(path)
    if marker.get("request_hash") != job["key"]:
        raise ValueError("Initial reservation identity mismatch")
    return marker


def dispatch_unknown(record):
    """A transport/read failure is not proof that the provider did no work."""
    if not record or not record.get("error") or record.get("api_attempted") is False:
        return False
    if record.get("dispatch_unknown") is True:
        return True
    if record.get("raw_response") or isinstance(record.get("extraction"), dict) or record.get("finish_reason"):
        return False
    status = record.get("http_status")
    return status is None or status >= 500 or 200 <= status < 300


def extraction_plan(batch, repair_once=False):
    pending = []
    unresolved = []
    ceiling = 0
    for document in batch["documents"]:
        for job in document["jobs"]:
            record = cached(job)
            if record is not None and not record.get("error"):
                continue
            initial = initial_marker(job)
            if dispatch_unknown(record) or (initial is not None and initial.get("status") in {"RESERVED", "UNKNOWN"}):
                unresolved.append(job["primary"]["chunk_id"])
                continue
            if repair_marker(job) is not None:
                unresolved.append(job["primary"]["chunk_id"])
                continue
            pending.append((job,record))
            ceiling += 1 if repair_once and repairable(record) else 2 if repair_once else 1
    return pending, unresolved, ceiling


def archive_record(job, record):
    path = OUTPUT/"cache/attempts"/job["key"]/(fingerprint(record)+".json")
    if not path.exists():
        save(path,record)
    return str(path.relative_to(OUTPUT))


def extract_attempt(job, schema, metrics, repair=None):
    if job.get("reuse_only"):
        raise ValueError("Historical MiMo cache is read-only; no new API request allowed")
    attempt_id = uuid4().hex
    kind = "repair" if repair is not None else "initial"
    attempt_hash = fingerprint({"payload":request_payload(job["primary"],job["contexts"],schema,repair),
        "repair_version":REPAIR_VERSION}) if repair is not None else job["key"]
    identity = {"attempt_id":attempt_id,"chunk_id":job["primary"]["chunk_id"],"request_hash":job["key"],
                "attempt_kind":kind,"attempt_request_hash":attempt_hash}
    marker_path = OUTPUT/"cache/repairs"/(job["key"]+".json")
    initial_path = OUTPUT/"cache/initial"/(job["key"]+".json")
    initial = initial_marker(job)
    if dispatch_unknown(cached(job)) or (initial is not None and initial.get("status") in {"RESERVED", "UNKNOWN"}):
        raise ValueError("Initial request outcome unknown; audit before any resend or repair")
    if repair is not None:
        if repair_marker(job) is not None:
            raise ValueError("Repair already consumed/reserved; no automatic retry")
        original = archive_record(job,repair)
        cache_path = OUTPUT/"cache"/(job["key"]+".json")
        source_archive = archive_record(job,read(cache_path)) if cache_path.exists() else original
        # Reserve before HTTP: an interrupted repair must not be sent twice after resume.
        save(marker_path,{**identity,"status":"RESERVED","repair_version":REPAIR_VERSION,
                          "repair_prompt_version":REPAIR_PROMPT_VERSION,"initial_archive":original,
                          "source_cache_archive":source_archive})
    else:
        save(initial_path,{**identity,"status":"RESERVED"})
    request_event(metrics,{**identity,"event":"started"})
    started = time.perf_counter()
    record = {"api_attempted":None,"usage":{}}
    try:
        record = call(job["primary"],job["contexts"],schema,repair) if repair is not None else call(job["primary"],job["contexts"],schema)
        if not record.get("error"):
            validation = stage(job["primary"],job["contexts"],record,schema)
            if repair is not None and not validation["facts"] and not validation["unresolved"]:
                validation["rejected"].append({"kind":"response","reason":"empty_repair_without_explanation"})
            record["validation"] = validation
            record["coverage_status"] = "CANDIDATES_UNREVIEWED" if validation["facts"] else "EMPTY_NEEDS_REVIEW"
            if validation["rejected"]:
                record["error"] = "validation_failed"
    except urllib.error.HTTPError as error:
        record.update(error="HTTPError",http_status=error.code,api_attempted=True)
    except Exception as error:
        record["error"] = type(error).__name__
    record.update(identity,validator_profile=VALIDATOR_PROFILE)
    record["dispatch_unknown"] = dispatch_unknown(record)
    if repair is not None:
        record.update(repair_version=REPAIR_VERSION,repair_prompt_version=REPAIR_PROMPT_VERSION,
                      initial_archive=original,source_cache_archive=source_archive)
    rejected = record.get("validation",{}).get("rejected",[])
    request_event(metrics,{**identity,"event":"finished","success":not bool(record.get("error")),
        "api_attempted":record.get("api_attempted"),"usage":reported_usage(record.get("usage")),
        "http_seconds":record.get("http_seconds"),"elapsed_seconds":time.perf_counter()-started,
        "http_status":record.get("http_status"),"error":record.get("error"),
        "transport_error_type":record.get("transport_error_type"),
        "dispatch_unknown":record["dispatch_unknown"],
        "rejected_reasons":sorted({reason for r in rejected for reason in r.get("reasons",[r.get("reason","unknown")])})})
    archive = archive_record(job,record)
    save(OUTPUT/"cache"/(job["key"]+".json"),record)
    status = "UNKNOWN" if record["dispatch_unknown"] else "FINISHED"
    if repair is not None:
        save(marker_path,{**read(marker_path),"status":status,"result_archive":archive,"success":not bool(record.get("error"))})
    else:
        save(initial_path,{**identity,"status":status,"result_archive":archive,
                           "success":not bool(record.get("error"))})
    return record


def extract_missing(batch, max_calls, metrics=None, repair_once=False):
    pending, unresolved, ceiling = extraction_plan(batch,repair_once)
    if max_calls < ceiling:
        raise ValueError(f"Need {ceiling} requests{' including reserved repair budget' if repair_once else ''}; --max-calls budget is {max_calls}. Select fewer documents or raise the explicit budget")
    if unresolved and not repair_once:
        raise ValueError("Some jobs exhausted repair; refusing to regenerate initial responses")
    calls = 0
    for index,(job,record) in enumerate(pending,1):
        if not (repair_once and repairable(record)):
            calls += 1
            record = extract_attempt(job,batch["schema"],metrics)
        if record.get("error") and repair_once and repairable(record):
            calls += 1
            record = extract_attempt(job,batch["schema"],metrics,repair=record)
        if record.get("error"):
            if repair_once and repairable(record):
                unresolved.append(job["primary"]["chunk_id"])
            else:
                raise ValueError(f"Extraction stopped; inspect cache {job['key']}; successful caches preserved")
        if metrics is not None:
            metrics["unresolved_chunks"] = list(unresolved)
        print(f"EXTRACT jobs {index}/{len(pending)}; new calls {calls}; needs review {len(unresolved)}",flush=True)
    if unresolved:
        report = {"status":"NEEDS_REVIEW_NOT_EXPORTED","batch_id":batch["batch_id"],"chunk_ids":unresolved}
        save(OUTPUT/"batches"/batch["batch_id"]/"needs_review.json",report)
        if metrics is not None:
            metrics["unresolved_chunks"] = unresolved
        raise ValueError(f"{len(unresolved)} chunks still need review after bounded repair; no graph export or DB writes")
    return calls


def package(batch):
    documents = []
    for document in batch["documents"]:
        staged, jobs, extractions = {}, [], []
        for job in document["jobs"]:
            record = cached(job)
            if record is None or record.get("error"):
                raise ValueError(f"Missing/failed extraction for {job['primary']['chunk_id']} (cache {job['key']}); use --check then explicitly budget --extract")
            result = stage(job["primary"],job["contexts"],record,batch["schema"])
            if result["rejected"]:
                raise ValueError(f"Evidence validation failed for {job['primary']['chunk_id']} (cache {job['key']}); no export published")
            staged[job["primary"]["pilot_id"]] = result
            jobs.append((job["primary"],job["contexts"]))
            extractions.append({"chunk_id":job["primary"]["chunk_id"],"request_hash":job["key"],
                "response_hash":record.get("source_review",{}).get("base_record_hash",
                    record.get("revalidation",{}).get("source_record_hash",fingerprint(record))),"model":record.get("model",MODEL),
                "focus_version":record.get("focus_version","historical-generic-v1"),
                "base_url":record.get("base_url",MIMO_BASE_URL if job.get("reuse_only") else BASE_URL),
                "evidence_version":record.get("evidence_version","legacy-quotes"),"validator_profile":VALIDATOR_PROFILE,
                "revalidation":record.get("revalidation"),
                **({"source_review":record["source_review"],"derived_record_hash":fingerprint(record)} if record.get("source_review") else {}),
                "coverage_status":("SOURCE_TEXT_NEEDS_REVIEW" if record.get("source_review",{}).get("deferred_numeric_facts")
                    else "CANDIDATES_UNREVIEWED" if result["facts"] else "EMPTY_NEEDS_REVIEW")})
        bundle = {"snapshot_hash":fingerprint({"source":document["source"],"keys":[j["key"] for j in document["jobs"]]}),
                  "schema":batch["schema"],"sources":[document["source"]]}
        graph = export_graph(bundle,jobs,staged)
        plan = document_plan(graph,batch["schema"])
        documents.append({"source":document["source"],"graph":graph,"run_id":plan["run_id"],
            "extractions":extractions,
            "unresolved":[{"chunk_id":j["primary"]["chunk_id"],"notes":staged[j["primary"]["pilot_id"]]["unresolved"]} for j in document["jobs"]]})
    return {"status":"EXPANSION_VALIDATED_PENDING_NOT_PRODUCTION","batch_id":batch["batch_id"],
            "schema_hash":fingerprint(batch["schema"]),"documents":documents}


def document_plan(graph, schema):
    plan = make_plan(graph,schema)
    plan["run_id"] = "modsa-expansion-v1:"+fingerprint({"graph_hash":plan["graph_hash"],"schema_hash":plan["schema_hash"]})
    return plan


def merge_batch(tx, plans):
    run_ids = [p["run_id"] for p in plans]
    before = other_content(tx,run_ids)
    first = [merge_run(tx,plan,check_unrelated=False) for plan in plans]
    second = [merge_run(tx,plan,check_unrelated=False) for plan in plans]
    if any(r["nodes_created"] or r["relationships_created"] for r in second):
        raise ValueError("Idempotency check failed; rollback batch")
    if any(a["content_hash"] != b["content_hash"] for a,b in zip(first,second)):
        raise ValueError("Readback changed; rollback batch")
    # Recheck the final state too: later imports must not alter earlier document runs.
    content_hashes = {plan["run_id"]: assert_run(tx,plan) for plan in plans}
    if before != other_content(tx,run_ids):
        raise ValueError("Unrelated graph changed; rollback batch")
    return {"documents":len(plans),"nodes_created":sum(r["nodes_created"] for r in first),
            "relationships_created":sum(r["relationships_created"] for r in first),
            "target_content_hashes":content_hashes}


def load(batch, output):
    return load_plans([document_plan(d["graph"],batch["schema"]) for d in output["documents"]])


def load_plans(plans):
    """Import already validated plans in one transaction, including portable copies."""
    from neo4j import GraphDatabase
    uri,user,password,database = connection_settings()
    with GraphDatabase.driver(uri,auth=(user,password),connection_timeout=10,max_transaction_retry_time=0) as driver:
        driver.verify_connectivity()
        with driver.session(database=database) as session:
            session.run(CONSTRAINT).consume()
            constraints = list(session.run("SHOW CONSTRAINTS YIELD type, labelsOrTypes, properties RETURN type, labelsOrTypes, properties"))
            if not any("UNIQUENESS" in row["type"] and row["labelsOrTypes"] == ["MODSAPilot"]
                       and row["properties"] == ["run_id","node_id"] for row in constraints):
                raise ValueError("Required run identity constraint is missing")
            # All document imports and readback checks share one transaction.
            return session.execute_write(merge_batch,plans)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",required=True,help="Whole document JSON file/directory under data/chunks")
    mode = parser.add_mutually_exclusive_group(required=True)
    for flag in ("check","extract","build","load"):
        mode.add_argument("--"+flag,action="store_true")
    parser.add_argument("--max-calls",type=int,default=0)
    parser.add_argument("--repair-once",action="store_true",help="One persisted source-only repair per failed chunk; reserve worst-case call budget")
    parser.add_argument("--reuse-mimo-cache",action="store_true",help="Reuse only exact historical MiMo requests that pass current evidence validation; keep their original identities")
    args = parser.parse_args()
    started, metrics = time.perf_counter(), None
    try:
        if args.max_calls < 0 or (args.max_calls and not args.extract):
            raise ValueError("--max-calls applies only to --extract and must be nonnegative")
        if args.repair_once and not (args.extract or args.check):
            raise ValueError("--repair-once applies only to --extract or offline --check")
        batch = prepare(args.input,reuse_mimo_cache=args.reuse_mimo_cache)
        jobs = [j for d in batch["documents"] for j in d["jobs"]]
        pending, unresolved, ceiling = extraction_plan(batch,args.repair_once)
        missing = len(pending)+len(unresolved)
        print(f"PLAN: {len(batch['documents'])} documents / {len(jobs)} chunks / {missing} missing requests; model {MODEL}")
        reused = sum(bool(j.get("reuse_only")) for j in jobs)
        print(f"CACHE: {len(jobs)-missing} ready, including {reused} revalidated MiMo responses (mixed-model build)")
        reviews = [read(path) for j in jobs if (path:=OUTPUT/"reviews"/(j["key"]+".json")).exists()]
        if reviews:
            deferred = sum(any(edit["action"]=="source_text" for edit in r["edits"]) for r in reviews)
            print(f"SOURCE REVIEW: {len(reviews)} AI-curated chunks (PENDING), {deferred} with numeric interpretation deferred; not semantic approval")
        if args.repair_once:
            print(f"BOUNDED REPAIR: at most {ceiling} new calls; {len(unresolved)} jobs already exhausted/reserved repair")
        if args.check:
            print("Check only: no credentials, API, file writes or database operations")
            return
        mode = "extract" if args.extract else "load" if args.load else "build"
        metrics = start_metrics(batch,mode,missing,args.max_calls,time.perf_counter()-started)
        metrics["repair_once"] = args.repair_once
        metrics["reused_mimo_chunks"] = reused
        if args.extract:
            phase_started = time.perf_counter()
            try:
                calls = extract_missing(batch,args.max_calls,metrics,repair_once=args.repair_once)
            finally:
                metrics["phase_seconds"]["extract_including_validation_cache_and_journal"] = time.perf_counter()-phase_started
            print(f"New API calls: {calls}")
        phase_started = time.perf_counter()
        try:
            output = package(batch)
        finally:
            metrics["phase_seconds"]["package_validation_and_graph_export"] = time.perf_counter()-phase_started
        metrics["graph_counts"] = {"nodes":sum(len(d["graph"]["nodes"]) for d in output["documents"]),
            "edges":sum(len(d["graph"]["edges"]) for d in output["documents"]),
            "facts":sum(n["label"]=="Fact" for d in output["documents"] for n in d["graph"]["nodes"])}
        path = OUTPUT/"batches"/batch["batch_id"]/"graph.json"
        if args.load:
            if not path.exists() or read(path) != output:
                raise ValueError("Build/current-source mismatch; build and inspect this batch before loading")
            phase_started = time.perf_counter()
            try:
                result = load(batch,output)
            finally:
                metrics["phase_seconds"]["neo4j_load_and_readback"] = time.perf_counter()-phase_started
            save(path.parent/"load.json",{"batch_id":batch["batch_id"],"run_ids":[d["run_id"] for d in output["documents"]],**result})
            verification_path = path.with_name("load_verification.json")
            if verification_path.exists():
                save(metrics["_folder"]/"previous_load_verification.json",read(verification_path))
            save(verification_path,batch_verification(path,result["target_content_hashes"]))
            print(f"LOADED: {result['documents']} document versions; {result['nodes_created']} new nodes / {result['relationships_created']} new edges")
        else:
            save(path,output)
            lines = ["# Expansion batch", "", f"Batch: `{batch['batch_id']}`", "",
                "Evidence validation passed; semantic correctness/current policy is NOT approved. All nodes remain PENDING with retrieval disabled.", "",
                "| Source | Version | Nodes | Edges | Facts | Unresolved notes |", "| --- | --- | ---: | ---: | ---: | ---: |"]
            for doc in output["documents"]:
                graph = doc["graph"]
                lines.append(f"| {doc['source']['source_id'].replace('|',' ')} | {doc['source']['version_id'].replace('|',' ')} | {len(graph['nodes'])} | {len(graph['edges'])} | {sum(n['label']=='Fact' for n in graph['nodes'])} | {sum(len(r['notes']) for r in doc['unresolved'])} |")
            lines.extend(["", "See graph.json for source quotes, unresolved notes and exact run IDs. No records are silently marked ACTIVE/VERIFIED.", ""])
            (path.parent/"README.md").write_text("\n".join(lines),encoding="utf-8")
            print(f"BUILT: {path.relative_to(ROOT)}; pending only, no DB writes")
        metrics["status"] = "SUCCEEDED"
    except Exception as error:
        if metrics is not None:
            metrics.update(status="NEEDS_REVIEW" if metrics.get("unresolved_chunks") else "FAILED",error_type=type(error).__name__)
        parser.exit(1,f"Expansion stopped ({type(error).__name__}); no unlimited retry/provider fallback. "
                    +(str(error)+"\n" if type(error) is ValueError else "Inspect input/configuration; secrets omitted.\n"))
    finally:
        if metrics is not None:
            finish_metrics(metrics,started)


if __name__ == "__main__":
    main()
