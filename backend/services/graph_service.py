"""Bounded, source-backed expansion of an explicitly opted-in pilot snapshot.

Not a production policy retriever: PENDING/UNKNOWN remains unchanged. The CLI
checks the complete, pinned Neo4j run before constructing this local index.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy

from langchain_core.documents import Document


def pilot_documents(bundle: dict) -> list[Document]:
    sources = {source["source_id"]: source for source in bundle["sources"]}
    documents = []
    for chunk in bundle["pilot"]:
        source = sources[chunk["source_id"]]
        metadata = {
            "source": source["source_path"], "title": source["title"],
            "source_id": chunk["source_id"], "version_id": chunk["version_id"],
            "content_hash": source["content_hash"], "chunk_id": chunk["chunk_id"],
            "pilot_id": chunk["pilot_id"], "source_index": chunk["source_index"],
            "category": chunk["category"], "pilot_role": chunk["role"],
            "document_status": source["document_status"],
            "verification_status": source["verification_status"],
            "retrieval_enabled": False,
        }
        if chunk["page"] is not None:
            metadata["page"] = chunk["page"] - 1
        documents.append(Document(page_content=chunk["content"], metadata=metadata))
    return documents


class PilotGraph:
    def __init__(self, nodes: dict, edges: dict, documents: list[Document], *, allow_pending: bool = False):
        if not allow_pending:
            raise ValueError("PENDING graph requires explicit experimental pilot opt-in")
        self.nodes, self.edges = deepcopy(nodes), deepcopy(edges)
        self.outgoing, self.incoming = defaultdict(list), defaultdict(list)
        for node in self.nodes.values():
            props = node["properties"]
            if props.get("review_status") != "PENDING" or props.get("retrieval_enabled") is not False:
                raise ValueError("Pilot must not promote or mix retrieval policy states")
        for edge_id, edge in sorted(self.edges.items()):
            if edge["source"] not in self.nodes or edge["target"] not in self.nodes:
                raise ValueError("Dangling pilot edge")
            self.outgoing[edge["source"]].append((edge_id, edge))
            self.incoming[edge["target"]].append((edge_id, edge))

        self.documents = {}
        for doc in documents:
            key = self.identity(doc)
            if not all(key) or key in self.documents:
                raise ValueError("Pilot documents require unique version/chunk identities")
            self.documents[key] = deepcopy(doc)
        self.chunks, self.chunk_nodes, self.versions = {}, {}, {}
        for node_id, node in self.nodes.items():
            if node["label"] != "Chunk":
                continue
            version_node = self.parent(node_id, "HAS_CHUNK", "DocumentVersion")
            version = self.nodes[version_node]["properties"]
            source_node = self.parent(version_node, "HAS_VERSION", "SourceDocument")
            source = self.nodes[source_node]["properties"]
            key = (version["version_id"], node["properties"]["chunk_id"])
            doc = self.documents.get(key)
            if (doc is None or doc.metadata.get("source_id") != source["source_id"]
                    or doc.metadata.get("content_hash") != version["content_hash"]
                    or doc.page_content != node["properties"]["content"]
                    or doc.metadata.get("page") != (node["properties"]["page"] - 1 if node["properties"].get("page") is not None else None)
                    or key in self.chunk_nodes):
                raise ValueError("Graph chunk differs from the pinned source/version")
            self.chunks[node_id], self.chunk_nodes[key] = doc, node_id
            self.versions[node_id] = version_node

        for edge in self.edges.values():
            if edge["type"] == "SUPPORTED_BY":
                quote = edge["properties"].get("quote")
                if (self.nodes[edge["source"]]["label"] != "Fact" or edge["target"] not in self.chunks
                        or not quote or quote not in self.chunks[edge["target"]].page_content):
                    raise ValueError("Fact evidence does not match its source chunk")
            elif edge["type"] == "NEXT_CHUNK":
                a, b = edge["source"], edge["target"]
                if (a not in self.chunks or b not in self.chunks or self.versions[a] != self.versions[b]
                        or self.chunks[b].metadata["source_index"] != self.chunks[a].metadata["source_index"] + 1):
                    raise ValueError("NEXT_CHUNK must be truly adjacent in the same version")

    @staticmethod
    def identity(doc: Document) -> tuple[str, str]:
        return doc.metadata.get("version_id", ""), doc.metadata.get("chunk_id", "")

    def parent(self, node_id: str, relation: str, label: str) -> str:
        parents = [edge["source"] for _, edge in self.incoming[node_id] if edge["type"] == relation]
        if len(parents) != 1 or self.nodes[parents[0]]["label"] != label:
            raise ValueError("Pilot chunk/version must have exactly one typed parent")
        return parents[0]

    def anchor(self, doc: Document) -> str | None:
        node_id = self.chunk_nodes.get(self.identity(doc))
        if node_id is None:
            return None
        original = self.chunks[node_id]
        if (doc.page_content != original.page_content
                or any(doc.metadata.get(key) != original.metadata.get(key)
                       for key in ("source_id", "content_hash", "page"))):
            return None
        return node_id

    def expand(self, seeds: list[Document], limit: int = 4) -> tuple[list[Document], list[dict]]:
        if type(limit) is not int or not 0 <= limit <= 20:
            raise ValueError("Graph expansion limit must be between 0 and 20")
        if not seeds or not limit:
            return [], []
        seed_keys = {self.identity(doc) for doc in seeds}
        candidates, paths = {}, []

        def offer(seed: str, target: str, path: dict) -> None:
            if target not in self.chunks or self.versions[target] != self.versions[seed]:
                return
            doc = self.chunks[target]
            key = self.identity(doc)
            if key in seed_keys:
                return
            candidates.setdefault(key, doc)
            paths.append({"seed_chunk_id": self.chunks[seed].metadata["chunk_id"],
                          "chunk_id": doc.metadata["chunk_id"], "version_id": key[0], **path})

        for doc in seeds:
            seed = self.anchor(doc)
            if seed is None:
                paths.append({"kind": "bridge_rejected", "chunk_id": doc.metadata.get("chunk_id"),
                              "reason": "missing_or_stale_source_version"})
                continue
            # Only one real adjacency edge; never recursively flood the document.
            for edge_id, edge in self.outgoing[seed] + self.incoming[seed]:
                if edge["type"] == "NEXT_CHUNK":
                    target = edge["target"] if edge["source"] == seed else edge["source"]
                    offer(seed, target, {"kind": "adjacent", "edge_ids": [edge_id]})
            for mention_id, mention in self.incoming[seed]:
                if mention["type"] != "MENTIONED_IN":
                    continue
                subject = mention["source"]
                if self.nodes[subject]["label"] not in {"Entity", "Offering"}:
                    continue
                for about_id, about in self.incoming[subject]:
                    if about["type"] != "ABOUT" or self.nodes[about["source"]]["label"] != "Fact":
                        continue
                    for support_id, support in self.outgoing[about["source"]]:
                        if support["type"] == "SUPPORTED_BY":
                            offer(seed, support["target"], {"kind": "fact_evidence", "subject_node_id": subject,
                                "fact_node_id": about["source"], "quote": support["properties"]["quote"],
                                "edge_ids": [mention_id, about_id, support_id]})
        selected = list(candidates)[:limit]
        selected_keys = set(selected)
        return ([deepcopy(candidates[key]) for key in selected],
                [path for path in paths if path["kind"] == "bridge_rejected"
                 or (path["version_id"], path["chunk_id"]) in selected_keys])
