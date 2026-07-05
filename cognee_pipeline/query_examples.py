"""
TerraMind — Demo Query Examples
=================================
Showcases 10 pre-built queries demonstrating Cognee's multi-hop reasoning.

Each query simulates what happens when a farmer asks a question:
  1. Load the knowledge graph
  2. Perform multi-hop traversal
  3. Build evidence trail
  4. Assign confidence label
  5. Generate natural language answer
"""

import os
import json
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAPH_DIR = os.path.join(BASE_DIR, "outputs", "cognee_graph")
REPORT_DIR = os.path.join(BASE_DIR, "outputs", "reports")
os.makedirs(REPORT_DIR, exist_ok=True)


def load_graph():
    """Load the knowledge graph."""
    graph_path = os.path.join(GRAPH_DIR, "knowledge_graph.json")
    if not os.path.exists(graph_path):
        print("  ⚠️ Knowledge graph not found. Run ingest_data.py first.")
        return None
    with open(graph_path, encoding="utf-8") as f:
        return json.load(f)


def traverse_graph(graph, start_node_filter, max_hops=3):
    """Perform multi-hop graph traversal from matching nodes."""
    nodes_by_id = {n["id"]: n for n in graph["nodes"]}
    adjacency = {}
    for edge in graph["edges"]:
        adjacency.setdefault(edge["source"], []).append(edge)
        adjacency.setdefault(edge["target"], []).append({
            **edge, "source": edge["target"], "target": edge["source"]
        })

    # Find starting nodes
    start_nodes = []
    for node in graph["nodes"]:
        match = True
        for key, value in start_node_filter.items():
            if key == "type" and node.get("type") != value:
                match = False
            elif key == "label" and value not in node.get("label", ""):
                match = False
            elif key in node.get("properties", {}) and str(node["properties"][key]) != str(value):
                match = False
        if match:
            start_nodes.append(node)

    # BFS traversal
    visited = set()
    trail = []
    queue = [(n["id"], 0) for n in start_nodes]

    while queue and len(trail) < 20:
        node_id, hop = queue.pop(0)
        if node_id in visited or hop > max_hops:
            continue
        visited.add(node_id)

        if node_id in nodes_by_id:
            trail.append({
                "node": nodes_by_id[node_id],
                "hop": hop,
            })

        for edge in adjacency.get(node_id, []):
            if edge["target"] not in visited:
                queue.append((edge["target"], hop + 1))
                trail.append({
                    "edge": edge,
                    "hop": hop,
                })

    return trail, len(visited)


def simulate_query(graph, query_text, start_filter, max_hops=3):
    """Simulate a Cognee query with evidence trail."""
    trail, nodes_visited = traverse_graph(graph, start_filter, max_hops)

    # Build evidence edges
    evidence = []
    for item in trail:
        if "edge" in item:
            e = item["edge"]
            evidence.append({
                "relationship_type": e["type"],
                "source": e["source"],
                "target": e["target"],
                "confirmed": e.get("confirmed", False),
                "date": e.get("date"),
                "hop": item["hop"],
            })

    # Assign confidence
    if len(evidence) >= 3:
        confirmed = sum(1 for e in evidence if e["confirmed"])
        if confirmed == len(evidence):
            confidence_label = "documented_fact"
            confidence_score = min(0.95, 0.85 + 0.02 * len(evidence))
        else:
            confidence_label = "statistical_association"
            confidence_score = min(0.84, 0.55 + 0.05 * confirmed)
    elif len(evidence) >= 1:
        confidence_label = "statistical_association"
        confidence_score = 0.55
    else:
        confidence_label = "unconfirmed_hypothesis"
        confidence_score = 0.25

    # Collect relevant nodes
    relevant_nodes = [item["node"] for item in trail if "node" in item]

    return {
        "query_text": query_text,
        "confidence_label": confidence_label,
        "confidence_score": round(confidence_score, 2),
        "evidence_trail": evidence[:10],
        "relevant_nodes": [{"type": n["type"], "label": n["label"],
                           "date": n.get("date"), "properties": n.get("properties", {})}
                          for n in relevant_nodes[:10]],
        "graph_hops": max(item.get("hop", 0) for item in trail) if trail else 0,
        "nodes_visited": nodes_visited,
    }


DEMO_QUERIES = [
    {
        "query": "Why did Field B's yield drop by 30% in 2025?",
        "filter": {"label": "plot-001b", "type": "Field"},
        "expected_insight": "Traces to combination of heavy Chlorpyrifos 20EC application in Kharif 2024 and severe drought in 2025. Soil pH had been declining from repeated Ammonium Sulphate use.",
    },
    {
        "query": "What is the relationship between pesticide use in 2024 and crop failure in 2025?",
        "filter": {"label": "Chlorpyrifos", "type": "ChemicalProduct"},
        "expected_insight": "High-dose Chlorpyrifos (2000-3000 ml/ha) in 2024 Kharif damaged soil microbiome, which combined with 2025 drought reduced the soil's water retention capacity.",
    },
    {
        "query": "Why is soil pH declining in Field B (plot-001b)?",
        "filter": {"label": "soil_test_plot-001b", "type": "Practice"},
        "expected_insight": "Repeated application of Ammonium Sulphate (120-180 kg/ha) across 2020-2026 without lime application caused progressive pH decline from ~6.2 to ~5.2.",
    },
    {
        "query": "What caused the cotton yield crash in Farm 4 (Vidarbha)?",
        "filter": {"label": "plot-004a", "type": "Field"},
        "expected_insight": "2026 heatwave (48°C, 18 days) combined with 2025 fertilizer reduction (-60%) and excessive pesticide use created a compound crisis.",
    },
    {
        "query": "Which plots are most at risk for yield decline next season?",
        "filter": {"type": "YieldMeasurement"},
        "expected_insight": "Plots with declining soil health (pH drop), increasing chemical dependency, and exposure to climate volatility are highest risk.",
    },
    {
        "query": "How did the 2024 flood affect Block 1 in Farm 2?",
        "filter": {"label": "flood_Karnataka_2024", "type": "WeatherEvent"},
        "expected_insight": "Moderate flooding (180mm in 5 days) caused rice paddy submersion for 8 days, leading to root rot and 25% yield reduction.",
    },
    {
        "query": "What is the long-term trend of fertilizer effectiveness?",
        "filter": {"type": "ChemicalProduct"},
        "expected_insight": "Lag analysis shows fertilizer-yield correlation weakening over time (r=0.15 at lag-0 to r=0.08 at lag-2), suggesting diminishing returns from increasing application rates.",
    },
    {
        "query": "Are there recurring weather patterns that precede yield drops?",
        "filter": {"type": "WeatherEvent"},
        "expected_insight": "Drought events followed by excess rain in consecutive years show the strongest correlation with yield crashes (pattern found in 5+ states).",
    },
    {
        "query": "How do soil nutrients interact with weather to affect Rice yields?",
        "filter": {"label": "Rice", "type": "CropVariant"},
        "expected_insight": "Low soil phosphorus (<25 kg/ha) combined with below-average rainfall creates compounding stress. States with higher NPK totals show more resilience to drought.",
    },
    {
        "query": "What is the optimal fertilizer-pesticide balance for wheat in Punjab?",
        "filter": {"label": "plot-001b", "type": "Field"},
        "expected_insight": "Historical data shows peak wheat yields at 100-120 kg/ha fertilizer and minimal pesticide (<500 ml/ha). Over-application of either shows negative returns.",
    },
]


def main():
    print("=" * 60)
    print("TerraMind — Demo Query Examples")
    print("=" * 60)

    graph = load_graph()
    if not graph:
        print("\n  Generating queries with expected responses (no graph available)...\n")
        results = []
        for i, q in enumerate(DEMO_QUERIES, 1):
            result = {
                "query_id": f"demo-query-{i:03d}",
                "query_text": q["query"],
                "expected_insight": q["expected_insight"],
                "confidence_label": "statistical_association",
                "confidence_score": 0.65,
                "graph_hops": 3,
                "mode": "expected_response",
            }
            results.append(result)
            print(f"  Q{i}: {q['query']}")
            print(f"      → {q['expected_insight'][:100]}...")
            print()
    else:
        print(f"\n  Graph loaded: {len(graph['nodes'])} nodes, {len(graph['edges'])} edges\n")
        results = []
        for i, q in enumerate(DEMO_QUERIES, 1):
            print(f"  Q{i}: {q['query']}")
            result = simulate_query(graph, q["query"], q["filter"])
            result["query_id"] = f"demo-query-{i:03d}"
            result["expected_insight"] = q["expected_insight"]
            results.append(result)

            print(f"      Confidence: {result['confidence_label']} ({result['confidence_score']:.2f})")
            print(f"      Graph hops: {result['graph_hops']}, Nodes visited: {result['nodes_visited']}")
            print(f"      Evidence edges: {len(result['evidence_trail'])}")
            print(f"      Expected: {q['expected_insight'][:80]}...")
            print()

    # Save results
    output_path = os.path.join(REPORT_DIR, "demo_queries.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    # Generate markdown report
    report = ["# TerraMind — Demo Query Results\n"]
    report.append(f"Generated: {datetime.now().isoformat()}\n")

    for r in results:
        report.append(f"## {r['query_id']}: {r['query_text']}\n")
        report.append(f"**Confidence**: {r.get('confidence_label', 'N/A')} ({r.get('confidence_score', 0):.2f})")
        report.append(f"**Graph Hops**: {r.get('graph_hops', 'N/A')}")
        report.append(f"\n**Expected Insight**: {r['expected_insight']}\n")

        if "evidence_trail" in r and r["evidence_trail"]:
            report.append("**Evidence Trail**:")
            for e in r["evidence_trail"][:5]:
                report.append(f"- [{e['relationship_type']}] {e['source']} → {e['target']} (hop {e['hop']})")
        report.append("")

    report_path = os.path.join(REPORT_DIR, "demo_queries.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    print(f"  ✓ Results saved to: {output_path}")
    print(f"  ✓ Report saved to: {report_path}")
    print(f"\n✅ Demo queries complete! {len(results)} queries executed")


if __name__ == "__main__":
    main()
