"""
Fraud Network Analyzer — Case Memory Graph via PostgreSQL + NetworkX.

Implementasi sesuai:
- GAR-HGNN (ACM ACAIB 2025): Heterogeneous Graph untuk fraud detection
- Proposal FR-4: Network Risk Propagator

Arsitektur:
- PostgreSQL (Supabase) menyimpan semua job_cases yang sudah diverifikasi
- NetworkX membangun in-memory graph dari entitas (HP, email, PT, URL)
- Query: apakah entitas baru terhubung ke kasus BAHAYA/WASPADA sebelumnya?
- Output: fraud_network_context yang dimasukkan ke SHAP explainer

Node types (sesuai skema Graf Heterogen di proposal):
- JobCase: node lowongan
- Phone: node nomor HP/WA
- Email: node alamat email
- Company: node nama PT/perusahaan
- URL: node domain/URL

Edge types:
- USES_PHONE, USES_EMAIL, MENTIONS_COMPANY, LINKS_TO
"""

from __future__ import annotations

import logging
from typing import Any

import networkx as nx

logger = logging.getLogger(__name__)


def build_fraud_network(job_cases: list[dict[str, Any]]) -> nx.MultiDiGraph:
    """
    Bangun heterogeneous graph dari riwayat job_cases.

    Args:
        job_cases: List dict dari tabel job_cases (phones, emails, companies, verdict)

    Returns:
        NetworkX MultiDiGraph dengan node entitas dan edge relasi
    """
    G = nx.MultiDiGraph()

    for case in job_cases:
        case_id = str(case.get("id", ""))
        verdict = case.get("verdict", "AMAN")
        risk_score = case.get("risk_score", 0)

        # Node: JobCase
        G.add_node(
            f"case:{case_id}",
            node_type="JobCase",
            verdict=verdict,
            risk_score=risk_score,
            created_at=str(case.get("created_at", "")),
        )

        # Edges: USES_PHONE
        for phone in (case.get("phones") or []):
            phone_node = f"phone:{phone}"
            if not G.has_node(phone_node):
                G.add_node(phone_node, node_type="Phone", value=phone)
            G.add_edge(
                f"case:{case_id}", phone_node,
                edge_type="USES_PHONE",
                verdict=verdict,
            )

        # Edges: USES_EMAIL
        for email in (case.get("emails") or []):
            email_node = f"email:{email.lower()}"
            if not G.has_node(email_node):
                G.add_node(email_node, node_type="Email", value=email)
            G.add_edge(
                f"case:{case_id}", email_node,
                edge_type="USES_EMAIL",
                verdict=verdict,
            )

        # Edges: MENTIONS_COMPANY
        for company in (case.get("companies") or []):
            co_name = company.upper().strip() if isinstance(company, str) else ""
            if co_name:
                co_node = f"company:{co_name}"
                if not G.has_node(co_node):
                    G.add_node(co_node, node_type="Company", value=co_name)
                G.add_edge(
                    f"case:{case_id}", co_node,
                    edge_type="MENTIONS_COMPANY",
                    verdict=verdict,
                )

        # Edges: LINKS_TO (URL/domain)
        for url in (case.get("urls") or []):
            # Normalize ke domain saja
            domain = _extract_domain(url)
            if domain:
                url_node = f"url:{domain}"
                if not G.has_node(url_node):
                    G.add_node(url_node, node_type="URL", value=domain)
                G.add_edge(
                    f"case:{case_id}", url_node,
                    edge_type="LINKS_TO",
                    verdict=verdict,
                )

    return G


def check_entity_in_network(
    G: nx.MultiDiGraph,
    entities: dict[str, Any],
) -> dict[str, Any]:
    """
    Periksa apakah entitas dari lowongan baru terhubung ke jaringan penipuan.

    Args:
        G: Graf fraud network dari riwayat kasus
        entities: Dict entitas yang diekstrak dari lowongan baru
                  (phones, emails, companies, urls)

    Returns:
        {
            "entity_in_fraud_network": bool,
            "entity_seen_multiple_cases": bool,
            "fraud_case_count": int,
            "total_case_count": int,
            "matched_entities": list[dict],
            "network_graph_summary": dict,
        }
    """
    matched_entities: list[dict[str, Any]] = []
    fraud_case_count = 0
    total_case_count = 0

    # Cek tiap tipe entitas
    checks = [
        ("phones",    "phone",   entities.get("contacts") or []),
        ("emails",    "email",   [e.lower() for e in (entities.get("emails") or [])]),
        ("companies", "company", [(c.upper().strip()) for c in (entities.get("companies") or [])]),
        ("urls",      "url",     [_extract_domain(u) for u in (entities.get("urls") or []) if _extract_domain(u)]),
    ]

    for entity_type, node_prefix, values in checks:
        for val in values:
            node_id = f"{node_prefix}:{val}"
            if not G.has_node(node_id):
                continue

            # Temukan semua kasus yang menggunakan entitas ini
            predecessor_cases = [
                (n, G.nodes[n])
                for n in G.predecessors(node_id)
                if G.nodes[n].get("node_type") == "JobCase"
            ]

            if not predecessor_cases:
                continue

            total_case_count += len(predecessor_cases)
            fraud_cases = [
                (n, d) for n, d in predecessor_cases
                if d.get("verdict") in ("BAHAYA", "WASPADA")
            ]
            fraud_case_count += len(fraud_cases)

            if fraud_cases or len(predecessor_cases) >= 2:
                matched_entities.append({
                    "entity_type": entity_type,
                    "entity_value": val,
                    "total_appearances": len(predecessor_cases),
                    "fraud_appearances": len(fraud_cases),
                    "verdicts": [d.get("verdict") for _, d in predecessor_cases],
                })

    entity_in_fraud_network = fraud_case_count > 0
    entity_seen_multiple_cases = total_case_count >= 2

    return {
        "entity_in_fraud_network": entity_in_fraud_network,
        "entity_seen_multiple_cases": entity_seen_multiple_cases,
        "fraud_case_count": fraud_case_count,
        "total_case_count": total_case_count,
        "matched_entities": matched_entities,
        "network_graph_summary": {
            "total_nodes": G.number_of_nodes(),
            "total_edges": G.number_of_edges(),
            "case_nodes": sum(1 for n, d in G.nodes(data=True) if d.get("node_type") == "JobCase"),
            "fraud_cases": sum(
                1 for n, d in G.nodes(data=True)
                if d.get("node_type") == "JobCase" and d.get("verdict") in ("BAHAYA", "WASPADA")
            ),
        },
    }


def get_network_graph_data(
    G: nx.MultiDiGraph,
    max_nodes: int = 50,
) -> dict[str, Any]:
    """
    Export graph data untuk visualisasi di FE (format: nodes + edges).

    Args:
        G: Fraud network graph
        max_nodes: Batas node untuk export (hindari payload terlalu besar)

    Returns:
        {"nodes": [...], "edges": [...]} untuk D3.js / cytoscape.js
    """
    nodes = []
    edges = []

    # Prioritaskan node yang terhubung ke kasus fraud
    fraud_related = set()
    for n, d in G.nodes(data=True):
        if d.get("node_type") == "JobCase" and d.get("verdict") in ("BAHAYA", "WASPADA"):
            fraud_related.add(n)
            for neighbor in G.neighbors(n):
                fraud_related.add(neighbor)

    selected = list(fraud_related)[:max_nodes]

    for node_id in selected:
        d = G.nodes[node_id]
        nodes.append({
            "id": node_id,
            "type": d.get("node_type", "Unknown"),
            "label": d.get("value", node_id.split(":", 1)[-1]),
            "verdict": d.get("verdict"),
            "risk_score": d.get("risk_score"),
        })

    seen_edges = set()
    for u, v, data in G.edges(data=True):
        if u in fraud_related and v in fraud_related:
            key = (u, v, data.get("edge_type"))
            if key not in seen_edges:
                seen_edges.add(key)
                edges.append({
                    "source": u,
                    "target": v,
                    "type": data.get("edge_type", "RELATED"),
                    "verdict": data.get("verdict"),
                })

    return {"nodes": nodes, "edges": edges}


def _extract_domain(url: str) -> str | None:
    """Extract domain dari URL."""
    import re
    if not url:
        return None
    # Hapus protocol
    url = re.sub(r"^https?://", "", url.lower().strip())
    # Ambil bagian sebelum path
    domain = url.split("/")[0].split("?")[0]
    # Hapus www.
    domain = re.sub(r"^www\.", "", domain)
    # Validasi minimal ada titik
    if "." in domain and len(domain) > 3:
        return domain
    return None
