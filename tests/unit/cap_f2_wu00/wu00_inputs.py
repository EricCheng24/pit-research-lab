"""Input-only structural materialization; no semantic qualification or catalogue capability export."""

import copy
import hashlib
import json
from pathlib import Path

INPUTS = Path(__file__).parent / "data" / "inputs"
NODE_FIELDS = (
    "content_versions",
    "assertions",
    "subjects",
    "publication_events",
    "evidence",
    "supports",
    "time_proofs",
    "observations",
    "relations",
    "reports",
)


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError(f"duplicate key: {key}")
        result[key] = value
    return result


def _integer(text):
    value = int(text)
    if text == "-0" or not -(2**63) <= value < 2**63:
        raise ValueError("invalid int64")
    return value


def _noninteger(text):
    raise ValueError(f"noninteger: {text}")


def decode(text):
    return json.loads(
        text,
        object_pairs_hook=_pairs,
        parse_int=_integer,
        parse_float=_noninteger,
        parse_constant=_noninteger,
    )


def _read(name):
    if name not in {"base.json", "contexts.json", "deltas.json"}:
        raise ValueError("input resource not allowlisted")
    return decode((INPUTS / name).read_text(encoding="utf-8"))


def unique(records, key):
    result = {}
    for record in records:
        identity = record[key]
        if identity in result:
            raise ValueError(f"duplicate {key}: {identity}")
        result[identity] = record
    return result


def literal_bytes(asset):
    if asset["encoding"] != "utf8-literal":
        raise ValueError("unknown literal encoding")
    data = asset["payload"].encode("utf-8")
    if len(data) != asset["byte_length"] or hashlib.sha256(data).hexdigest() != asset["sha256"]:
        raise ValueError(f"literal integrity: {asset['id']}")
    return data


def validate_receipt_pages(receipt_assets, page_assets):
    """Validate a scoped receipt/page envelope using only its supplied lossless assets."""
    unique(receipt_assets, "id")
    pages = unique(page_assets, "id")
    referenced = []
    for asset in receipt_assets:
        receipt = decode(literal_bytes(asset))
        identity = receipt.get("receipt_id", receipt.get("attempt_id"))
        if identity != asset["id"]:
            raise ValueError("receipt identity binding")
        state = receipt["search_state"]
        if state not in {"COMPLETED", "NOT_PERFORMED", "FAILED"}:
            raise ValueError("unknown source-search state")
        if state != "COMPLETED":
            if any(
                receipt[key]
                for key in [
                    "page_sequence",
                    "exact_member_ids",
                    "material_lead_ids",
                    "terminal",
                    "completion_at",
                    "completion_timezone",
                ]
            ):
                raise ValueError("noncompleted receipt fabricated completion")
            continue
        sequence = receipt["page_sequence"]
        if not sequence or not receipt["completion_at"] or receipt["terminal"] != "END_OF_RESULTS":
            raise ValueError("incomplete completed receipt")
        if len({p["page_id"] for p in sequence}) != len(sequence):
            raise ValueError("duplicate page in receipt sequence")
        members = []
        for index, binding in enumerate(sequence):
            page_id = binding["page_id"]
            if page_id not in pages:
                raise ValueError(f"missing referenced page: {page_id}")
            page = pages[page_id]
            body = decode(literal_bytes(page))
            if set(body) != {"schema", "page_id", "query_id", "members", "next_page", "terminal"}:
                raise ValueError("page schema keys")
            if body["schema"] != "synthetic-page-v1" or body["page_id"] != page_id:
                raise ValueError("page identity binding")
            if any(binding[key] != page[key] for key in ["byte_length", "sha256"]):
                raise ValueError("page integrity binding")
            if body["query_id"] != receipt["query_id"]:
                raise ValueError("page query binding")
            next_id = sequence[index + 1]["page_id"] if index + 1 < len(sequence) else None
            terminal = None if next_id is not None else "END_OF_RESULTS"
            if any(body[key] != binding[key] for key in ["next_page", "terminal"]):
                raise ValueError("page terminal binding")
            if body["next_page"] != next_id or body["terminal"] != terminal:
                raise ValueError("page sequence/terminal chain")
            if not isinstance(body["members"], list) or any(
                not isinstance(member, str) for member in body["members"]
            ):
                raise ValueError("page member types")
            members.extend(body["members"])
            if page_id not in referenced:
                referenced.append(page_id)
        if len(members) != len(set(members)) or sorted(members) != receipt["exact_member_ids"]:
            raise ValueError("receipt member binding")
    if list(pages) != referenced:
        raise ValueError("extra or out-of-order scoped page assets")


def selected_receipt_pages(world, receipt_assets):
    """Resolve only selected pages, preserving receipt/sequence first occurrence order."""
    catalogue = unique(world["page_assets"], "id")
    selected = []
    seen = set()
    for asset in receipt_assets:
        receipt = decode(literal_bytes(asset))
        for binding in receipt["page_sequence"]:
            page_id = binding["page_id"]
            if page_id not in catalogue:
                raise ValueError(f"missing referenced page: {page_id}")
            if page_id not in seen:
                selected.append(copy.deepcopy(catalogue[page_id]))
                seen.add(page_id)
    validate_receipt_pages(receipt_assets, selected)
    return selected


def validate_catalogue(world):
    """Harness-only structural audit. Custody references never grant active proof visibility."""
    for field, count in [("raw_assets", 17), ("page_assets", 21), ("receipt_assets", 23)]:
        if len(unique(world[field], "id")) != count:
            raise ValueError(f"wrong {field} count")
        for asset in world[field]:
            decode(literal_bytes(asset))
    chains = unique(world["chains"], "key")
    if len(chains) != 19 or len(unique(world["graph_edges"], "id")) != 170:
        raise ValueError("graph accounting")
    nodes = set()
    for field in NODE_FIELDS:
        nodes.update(world[field])
    nodes.update("REP-RAW-" + asset["id"] for asset in world["raw_assets"])
    for edge in world["graph_edges"]:
        if edge["from"] not in nodes or edge["to"] not in nodes:
            raise ValueError(f"dangling graph edge: {edge['id']}")
    validate_receipt_pages(world["receipt_assets"], world["page_assets"])
    for asset in world["receipt_assets"]:
        receipt = decode(asset["payload"])
        for field in ["exact_member_ids", "material_lead_ids"]:
            values = receipt[field]
            if values != sorted(values) or len(values) != len(set(values)):
                raise ValueError("duplicate/unordered receipt members")
        if receipt["search_state"] == "FAILED" and (
            receipt["record_kind"] != "search_attempt" or "receipt_id" in receipt
        ):
            raise ValueError("failed attempt misrepresented as receipt")
        if receipt["source_publication_timezone"] is not None:
            raise ValueError("receipt cannot provide publication timezone")
    return world


def load_catalogue():
    """Acceptance harness access only; materialize never returns this catalogue."""
    return validate_catalogue(_read("base.json"))


def load_deltas():
    records = _read("deltas.json")
    if len(unique(records, "case_id")) != 64 or len(unique(records, "delta_id")) != 64:
        raise ValueError("delta accounting")
    if any(r["delta_id"] != "D-" + r["case_id"] for r in records):
        raise ValueError("delta identity binding")
    return records


def integrity_stimulus(stimulus_id):
    """Input-only identity-collision versus read-corruption stimuli, without expected statuses."""
    world = load_catalogue()
    stimulus = unique(world["integrity_stimuli"], "stimulus_id")[stimulus_id]
    representations = unique(world["integrity_representations"], "id")
    return {
        "request": copy.deepcopy(stimulus),
        "verified_representation": copy.deepcopy(
            representations[stimulus["verified_representation_ref"]]
        ),
        "actual_payload": copy.deepcopy(representations[stimulus["actual_payload_ref"]]),
        "future_input_description": copy.deepcopy(world["future_pinned_input_description"]),
    }


def _view(world, keys):
    chains = unique(world["chains"], "key")
    view = {key: {} for key in NODE_FIELDS}
    view.update(raw_assets={}, graph_edges=[])
    raw = {a["alias"]: a for a in world["raw_assets"]}
    for key in keys:
        chain = chains[key]
        for field, identity in [
            ("content_versions", chain["cv"]),
            ("subjects", chain["subject"]),
            ("supports", chain["support"]),
            ("observations", chain["observation"]),
        ]:
            if identity in world[field]:
                view[field][identity] = copy.deepcopy(world[field][identity])
        target_field = {"assertion": "assertions", "relation": "relations", "report": "reports"}[
            chain["kind"]
        ]
        view[target_field][chain["target"]] = copy.deepcopy(world[target_field][chain["target"]])
        view["raw_assets"][chain["rep"]] = copy.deepcopy(raw[chain["alias"]])
        if chain["event"]:
            view["publication_events"][chain["event"]] = copy.deepcopy(
                world["publication_events"][chain["event"]]
            )
        if chain["time"]:
            view["time_proofs"]["TP-" + key] = copy.deepcopy(world["time_proofs"]["TP-" + key])
        ev = view["evidence"].setdefault(
            chain["evidence"],
            {
                "evidence_id": chain["evidence"],
                "bindings": [],
            },
        )
        ev["bindings"].extend(
            copy.deepcopy(
                [
                    b
                    for b in world["evidence"][chain["evidence"]]["bindings"]
                    if b["target_id"] == chain["target"]
                ]
            )
        )
        view["graph_edges"].extend(
            copy.deepcopy([e for e in world["graph_edges"] if e["id"].startswith("G-" + key + "-")])
        )
    return view


def _june_proof(view, case_id, payload):
    """Declarative path replacement, with no temporal evaluation or fallback lookup."""
    evidence = view["evidence"].pop("EVID-JUN1-TIME")
    support = view["supports"].pop("SUP-JUN1-PUB")
    proof = view["time_proofs"].pop("TP-JUN1")
    removed = {"G-JUN1-" + suffix for suffix in ["B", "I", "T", "E", "S"]}
    old_edges = [e for e in view["graph_edges"] if e["id"] in removed]
    view["graph_edges"] = [e for e in view["graph_edges"] if e["id"] not in removed]
    if payload is None:
        return
    replacements = {
        old: old + "-" + case_id
        for old in [
            "EVID-JUN1-TIME",
            "SUP-JUN1-PUB",
            "TP-JUN1",
        ]
    }
    evidence["evidence_id"] = replacements["EVID-JUN1-TIME"]
    evidence["bindings"][0]["time_proof_ref"] = replacements["TP-JUN1"]
    support.update(support_id=replacements["SUP-JUN1-PUB"], evidence_id=evidence["evidence_id"])
    proof.update(payload, proof_id=replacements["TP-JUN1"])
    view["evidence"][evidence["evidence_id"]] = evidence
    view["supports"][support["support_id"]] = support
    view["time_proofs"][proof["proof_id"]] = proof
    for edge in old_edges:
        edge["id"] = edge["id"].replace("G-JUN1-", "G-JUN1-" + case_id + "-")
        for key in ["from", "to", "evidence", "time"]:
            edge[key] = replacements.get(edge[key], edge[key])
        view["graph_edges"].append(edge)


def materialize(case_id):
    """Fresh case inputs only. Source selection, results and immutable manifests belong to later WUs."""
    world = load_catalogue()
    config = _read("contexts.json")
    delta = unique(load_deltas(), "case_id")[case_id]
    context = copy.deepcopy(config["contexts"][delta["context_ref"]])
    request = {**context, **copy.deepcopy(delta["request"])}
    evidence_set = context["evidence_set_ref"]
    for operation in delta["operations"]:
        if operation["kind"] == "evidence_set":
            evidence_set = operation["ref"]
    membership = copy.deepcopy(config["evidence_sets"][evidence_set])
    keys = membership["chain_keys"]
    for operation in delta["operations"]:
        if operation["kind"] == "add_chain":
            keys.append(operation["chain_key"])
        if operation["kind"] == "remove_chain":
            keys.remove(operation["chain_key"])
        if operation["kind"] == "receipt_refs":
            membership["receipt_refs"] = operation["refs"]
    active = _view(world, keys)
    auxiliary = []
    dependency = []
    audit = []
    specs = copy.deepcopy(config["feature_specs"])
    receipts = {a["id"]: a for a in world["receipt_assets"]}
    for operation in delta["operations"]:
        kind = operation["kind"]
        if kind == "replace_june_proof":
            _june_proof(active, case_id, operation["payload"])
        elif kind == "remove_june_proof":
            _june_proof(active, case_id, None)
        elif kind in {"auxiliary_chains", "dependency_chains"}:
            target = auxiliary if kind == "auxiliary_chains" else dependency
            target.append(_view(world, operation["chain_keys"]))
        elif kind == "auxiliary_body":
            raw = next(a for a in world["raw_assets"] if a["alias"] == operation["raw_alias"])
            auxiliary.append(
                {
                    "request": copy.deepcopy(operation),
                    "raw_asset": raw,
                    "assertion": world["assertions"][operation["target_assertion_ref"]],
                }
            )
        elif kind == "provider_capture":
            raw = next(a for a in world["raw_assets"] if a["alias"] == operation["raw_alias"])
            observation = world["observations"][operation["observation_ref"]]
            edges = [e for e in world["graph_edges"] if e["id"] == "G-PX-CAPTURE"]
            if len(edges) != 1:
                raise ValueError("provider capture edge cardinality: expected exactly one")
            binding = {
                "id": "G-PX-CAPTURE",
                "from": "OBS-P-X-A02-C04",
                "to": "REP-RAW-CV-A02-C04-PX-CAPTURE",
                "type": "provider_lab_capture_only",
            }
            if (
                any(edges[0].get(key) != value for key, value in binding.items())
                or observation["observation_id"] != binding["from"]
                or observation["raw_representation_id"] != binding["to"]
                or "REP-RAW-" + raw["id"] != binding["to"]
            ):
                raise ValueError("provider capture edge binding mismatch")
            auxiliary.append(
                {
                    "raw_asset": copy.deepcopy(raw),
                    "observation": copy.deepcopy(observation),
                    "graph_edges": copy.deepcopy(edges),
                }
            )
        elif kind == "observation":
            observation = copy.deepcopy(active["observations"][operation["source_observation"]])
            observation.update(
                observation_id=operation["observation_id"], completed_at=operation["completed_at"]
            )
            if operation["replace"]:
                del active["observations"][operation["source_observation"]]
                active["graph_edges"] = [
                    e for e in active["graph_edges"] if e["from"] != operation["source_observation"]
                ]
            active["observations"][observation["observation_id"]] = observation
            active["graph_edges"].append(
                {
                    "id": "G-OBS-" + operation["observation_id"],
                    "from": operation["observation_id"],
                    "to": observation["raw_representation_id"],
                    "type": "lab_capture_only",
                    "time": "CAPTURE-" + operation["observation_id"],
                }
            )
        elif kind == "feature_spec":
            specs[operation["body"]["physical_spec_id"]] = copy.deepcopy(operation["body"])
        elif kind == "lead":
            active.setdefault("leads", {})[operation["lead_ref"]] = world["leads"][
                operation["lead_ref"]
            ]
        elif kind == "audit_annotation":
            audit.append(copy.deepcopy(operation["body"]))
        elif kind in {
            "fault_schedule",
            "pending_append",
            "pending_receipt_append",
            "integrity_fault",
        }:
            stimulus = copy.deepcopy(operation)
            if kind == "pending_append":
                stimulus["writer_inputs"] = _view(world, operation["chain_keys"])
            if kind == "fault_schedule" and "writer_chain_keys" in operation:
                stimulus["writer_inputs"] = _view(world, operation["writer_chain_keys"])
            if kind == "pending_receipt_append":
                stimulus["receipt"] = copy.deepcopy(receipts[operation["receipt_ref"]])
                stimulus["pages"] = selected_receipt_pages(world, [stimulus["receipt"]])
            if kind == "integrity_fault":
                stimulus["representations"] = copy.deepcopy(world["integrity_representations"])
                stimulus["required_raw_ref"] = copy.deepcopy(
                    active["raw_assets"]["REP-RAW-CV-JUN-01"]
                )
            dependency.append(stimulus)
    request["evidence_set_ref"] = evidence_set
    subject_ref = request.get("requested_subject_ref", "SUB-A-Q2")
    active["subjects"][subject_ref] = copy.deepcopy(world["subjects"][subject_ref])
    selected_receipts = [copy.deepcopy(receipts[r]) for r in membership["receipt_refs"]]
    return {
        "case_id": case_id,
        "delta_id": delta["delta_id"],
        "request": request,
        "active_discovery_membership": {
            "facts": active,
            "receipts": selected_receipts,
            "pages": selected_receipt_pages(world, selected_receipts),
        },
        "auxiliary_comparison_inputs": auxiliary,
        "dependency_only_or_fault_schedule_inputs": dependency,
        "audit_annotations": audit,
        "feature_specs": specs,
        "calendar": copy.deepcopy(config["calendar"]),
        "universe": copy.deepcopy(config["universe"]),
        "grid": copy.deepcopy(config["grid"]),
        "numeric_contract": copy.deepcopy(config["numeric_contract"]),
        "decision_wall_times": copy.deepcopy(config["decision_wall_times"]),
        "contract_metadata": {
            "feature_rule": config["feature_rule"],
            "fallback_policy": config["fallback_policy"],
            "timezone": config["timezone"],
            "precision": config["precision"],
            "cutoff_bound": config["cutoff_bound"],
        },
        "provenance": {"inventory_sha256": world["inventory_sha256"], "base_id": world["base_id"]},
    }
