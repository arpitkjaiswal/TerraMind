"""
TerraMind — Cognee Data Ingestion Pipeline
=============================================
Ingests all data (real + synthetic) into Cognee's knowledge graph.

Can run in two modes:
  1. ONLINE mode: Uses Cognee API (requires COGNEE_API_KEY)
  2. OFFLINE mode: Generates the graph structure locally (for demo)

Usage:
  python ingest_data.py --mode offline   # Generate graph JSON locally
  python ingest_data.py --mode online    # Full Cognee pipeline
"""

import os
import sys
import json
import argparse
from datetime import datetime
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = BASE_DIR
GENERATED_DIR = os.path.join(BASE_DIR, "data_generation", "generated")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs", "cognee_graph")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_all_data():
    """Load all datasets — both real and synthetic."""
    import pandas as pd

    data = {}

    # Real datasets
    data["crop_yield"] = pd.read_csv(os.path.join(DATA_DIR, "crop_yield.csv"))
    data["crop_yield"].columns = data["crop_yield"].columns.str.strip().str.lower()

    data["weather"] = pd.read_csv(os.path.join(DATA_DIR, "state_weather_data_1997_2020.csv"))
    data["weather"].columns = data["weather"].columns.str.strip().str.lower()

    data["soil"] = pd.read_csv(os.path.join(DATA_DIR, "state_soil_data.csv"))
    data["soil"].columns = data["soil"].columns.str.strip().str.lower()

    # Synthetic datasets
    if os.path.exists(os.path.join(GENERATED_DIR, "field_notes.json")):
        with open(os.path.join(GENERATED_DIR, "field_notes.json"), encoding="utf-8") as f:
            data["field_notes"] = json.load(f)
    else:
        data["field_notes"] = []

    if os.path.exists(os.path.join(GENERATED_DIR, "chemical_logs.json")):
        with open(os.path.join(GENERATED_DIR, "chemical_logs.json"), encoding="utf-8") as f:
            data["chemical_logs"] = json.load(f)
    else:
        data["chemical_logs"] = []

    if os.path.exists(os.path.join(GENERATED_DIR, "weather_events.json")):
        with open(os.path.join(GENERATED_DIR, "weather_events.json"), encoding="utf-8") as f:
            data["weather_events"] = json.load(f)
    else:
        data["weather_events"] = []

    if os.path.exists(os.path.join(GENERATED_DIR, "seed_data.json")):
        with open(os.path.join(GENERATED_DIR, "seed_data.json"), encoding="utf-8") as f:
            data["seed_data"] = json.load(f)
    else:
        data["seed_data"] = {"farms": [], "plots": []}

    print(f"  Crop yield:     {len(data['crop_yield']):,} records")
    print(f"  Weather:        {len(data['weather']):,} records")
    print(f"  Soil:           {len(data['soil']):,} records")
    print(f"  Field notes:    {len(data['field_notes']):,} notes")
    print(f"  Chemical logs:  {len(data['chemical_logs']):,} records")
    print(f"  Weather events: {len(data['weather_events']):,} events")

    return data


def build_graph_offline(data):
    """Build the knowledge graph structure locally (offline mode)."""
    nodes = []
    edges = []
    node_id_counter = 0

    def make_node(node_type, label, date=None, properties=None):
        nonlocal node_id_counter
        node_id_counter += 1
        node = {
            "id": f"node-{node_id_counter:05d}",
            "type": node_type,
            "label": label,
            "date": date,
            "properties": properties or {},
        }
        nodes.append(node)
        return node["id"]

    def make_edge(source, target, rel_type, confirmed=False, date=None, source_doc=None):
        edges.append({
            "source": source,
            "target": target,
            "type": rel_type,
            "confirmed": confirmed,
            "date": date,
            "source_document_id": source_doc,
        })

    # 1. Create Farm and Plot nodes
    seed = data["seed_data"]
    farm_nodes = {}
    plot_nodes = {}

    for farm in seed.get("farms", []):
        fid = make_node("Farm", farm["name"], properties={
            "state": farm["state"], "owner": farm["owner"], "farm_id": farm["id"]
        })
        farm_nodes[farm["id"]] = fid

    for plot in seed.get("plots", []):
        pid = make_node("Field", plot["name"], properties={
            "crop": plot["crop"], "size_ha": plot["size_ha"],
            "farm_id": plot["farm_id"], "plot_id": plot["id"]
        })
        plot_nodes[plot["id"]] = pid
        if plot["farm_id"] in farm_nodes:
            make_edge(farm_nodes[plot["farm_id"]], pid, "CONTAINS")

    # 2. Create Weather Event nodes
    weather_nodes = {}
    for event in data["weather_events"]:
        wid = make_node("WeatherEvent", f"{event['event_type']}_{event['state']}_{event['year']}",
                        date=event["date_start"],
                        properties={
                            "event_type": event["event_type"],
                            "severity": event["severity"],
                            "duration_days": event["duration_days"],
                            "description": event["description"][:200],
                            "state": event["state"],
                        })
        weather_nodes[event["event_id"]] = wid

        # Link to affected plot
        if event["plot_id"] in plot_nodes:
            make_edge(wid, plot_nodes[event["plot_id"]], "OCCURRED_DURING",
                      date=event["date_start"])

    # 3. Create Chemical Application nodes
    chem_nodes = {}
    for log in data["chemical_logs"]:
        cid = make_node("ChemicalProduct",
                        f"{log['chemical_name']}_{log['plot_id']}_{log['year']}",
                        date=log["date"],
                        properties={
                            "chemical_name": log["chemical_name"],
                            "chemical_type": log["chemical_type"],
                            "application_rate": log["application_rate"],
                            "unit": log["unit"],
                            "method": log["application_method"],
                        })
        chem_nodes[log["record_id"]] = cid

        if log["plot_id"] in plot_nodes:
            make_edge(cid, plot_nodes[log["plot_id"]], "APPLIED_TO",
                      date=log["date"], source_doc=log["record_id"])

    # 4. Create Yield Measurement nodes from harvest notes
    yield_nodes = {}
    for note in data["field_notes"]:
        if note["category"] == "harvest_report":
            yid = make_node("YieldMeasurement",
                            f"yield_{note['plot_id']}_{note['date'][:4]}",
                            date=note["date"],
                            properties={
                                "yield_per_ha": note.get("yield_per_ha", 0),
                                "plot_id": note["plot_id"],
                                "text": note["text"][:300],
                            })
            yield_nodes[f"{note['plot_id']}_{note['date'][:4]}"] = yid

            if note["plot_id"] in plot_nodes:
                make_edge(plot_nodes[note["plot_id"]], yid, "PRODUCED")

    # 5. Create temporal PRECEDED edges between consecutive years
    for plot_id in plot_nodes:
        years = sorted([int(k.split("_")[-1]) for k in yield_nodes if k.startswith(plot_id)])
        for i in range(1, len(years)):
            prev_key = f"{plot_id}_{years[i-1]}"
            curr_key = f"{plot_id}_{years[i]}"
            if prev_key in yield_nodes and curr_key in yield_nodes:
                make_edge(yield_nodes[prev_key], yield_nodes[curr_key], "PRECEDED",
                          date=f"{years[i]}-01-01")

    # 6. Create CORRELATED_WITH edges for chemical-yield relationships
    for log in data["chemical_logs"]:
        yield_key = f"{log['plot_id']}_{log['year']}"
        if log["record_id"] in chem_nodes and yield_key in yield_nodes:
            make_edge(chem_nodes[log["record_id"]], yield_nodes[yield_key],
                      "CORRELATED_WITH", date=log["date"])

    # 7. Weather-Yield correlations
    for event in data["weather_events"]:
        yield_key = f"{event['plot_id']}_{event['year']}"
        if event["event_id"] in weather_nodes and yield_key in yield_nodes:
            make_edge(weather_nodes[event["event_id"]], yield_nodes[yield_key],
                      "CORRELATED_WITH", date=event["date_start"])

    # 8. Create Practice nodes from field notes
    for note in data["field_notes"]:
        if note["category"] == "planting_record":
            pid = make_node("Practice", f"planting_{note['plot_id']}_{note['date'][:4]}",
                           date=note["date"],
                           properties={"text": note["text"][:300], "category": "planting"})
            if note["plot_id"] in plot_nodes:
                make_edge(pid, plot_nodes[note["plot_id"]], "APPLIED_TO", date=note["date"])

    # 9. Soil test nodes
    for note in data["field_notes"]:
        if note["category"] == "soil_test":
            sid = make_node("Practice", f"soil_test_{note['plot_id']}_{note['date'][:4]}",
                           date=note["date"],
                           properties={
                               "n": note.get("soil_n", 0),
                               "p": note.get("soil_p", 0),
                               "k": note.get("soil_k", 0),
                               "ph": note.get("soil_ph", 0),
                               "text": note["text"][:300],
                           })
            if note["plot_id"] in plot_nodes:
                make_edge(sid, plot_nodes[note["plot_id"]], "APPLIED_TO", date=note["date"])

    print(f"\n  Graph built: {len(nodes)} nodes, {len(edges)} edges")

    # Build the complete graph response
    graph = {
        "nodes": nodes,
        "edges": edges,
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "node_types": {str(k): int(v) for k, v in pd.Series([n["type"] for n in nodes]).value_counts().items()},
            "edge_types": {str(k): int(v) for k, v in pd.Series([e["type"] for e in edges]).value_counts().items()},
        }
    }

    return graph


async def ingest_online(data):
    """Ingest data using Cognee API (online mode)."""
    try:
        import cognee
    except ImportError:
        print("  ⚠️ Cognee not installed. Install with: pip install cognee")
        print("  Falling back to offline mode...")
        return None

    api_key = os.environ.get("COGNEE_API_KEY")
    if not api_key:
        print("  ⚠️ COGNEE_API_KEY not set. Falling back to offline mode...")
        return None

    print("  Initializing Cognee...")
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)

    # Ingest field notes as text documents
    print("  Ingesting field notes...")
    for note in data["field_notes"]:
        text = f"Date: {note['date']}\nPlot: {note['plot_id']}\nCategory: {note['category']}\n---\n{note['text']}"
        await cognee.add(text, dataset_name=f"field_notes_{note['plot_id']}")

    # Ingest chemical logs as structured text
    print("  Ingesting chemical logs...")
    for log in data["chemical_logs"]:
        text = (f"Chemical Application Record\n"
                f"Date: {log['date']}\nPlot: {log['plot_id']}\n"
                f"Chemical: {log['chemical_name']} ({log['chemical_type']})\n"
                f"Rate: {log['application_rate']} {log['unit']}\n"
                f"Method: {log['application_method']}\n"
                f"Notes: {log.get('notes', '')}")
        await cognee.add(text, dataset_name=f"chemical_logs_{log['plot_id']}")

    # Ingest weather events
    print("  Ingesting weather events...")
    for event in data["weather_events"]:
        text = (f"Weather Event: {event['event_type'].title()}\n"
                f"Date: {event['date_start']} to {event['date_end']}\n"
                f"Location: {event['state']}, Plot: {event['plot_id']}\n"
                f"Severity: {event['severity']}\n"
                f"Duration: {event['duration_days']} days\n"
                f"Description: {event['description']}")
        await cognee.add(text, dataset_name=f"weather_events_{event['plot_id']}")

    # Run cognify
    print("  Running Cognee cognify (building knowledge graph)...")
    await cognee.cognify()

    print("  ✓ Cognee ingestion complete!")
    return True


def main():
    import pandas as pd

    parser = argparse.ArgumentParser(description="TerraMind Cognee Data Ingestion")
    parser.add_argument("--mode", choices=["online", "offline"], default="offline",
                        help="Ingestion mode (default: offline)")
    args = parser.parse_args()

    print("=" * 60)
    print(f"TerraMind — Cognee Data Ingestion ({args.mode} mode)")
    print("=" * 60)

    data = load_all_data()

    if args.mode == "online":
        import asyncio
        result = asyncio.run(ingest_online(data))
        if result is None:
            print("\n  Falling back to offline mode...")
            graph = build_graph_offline(data)
        else:
            print("\n  ✓ Online ingestion successful!")
            return
    else:
        graph = build_graph_offline(data)

    # Save graph
    graph_path = os.path.join(OUTPUT_DIR, "knowledge_graph.json")
    with open(graph_path, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2)
    print(f"\n  Graph saved to: {graph_path}")

    # Save per-plot graphs (for frontend)
    for plot in data["seed_data"].get("plots", []):
        plot_nodes = [n for n in graph["nodes"]
                      if n.get("properties", {}).get("plot_id") == plot["id"]
                      or n.get("properties", {}).get("farm_id") == plot["farm_id"]]
        plot_node_ids = {n["id"] for n in plot_nodes}
        plot_edges = [e for e in graph["edges"]
                      if e["source"] in plot_node_ids or e["target"] in plot_node_ids]

        plot_graph = {
            "nodes": plot_nodes,
            "edges": plot_edges,
            "plot_id": plot["id"],
            "farm_id": plot["farm_id"],
        }
        plot_path = os.path.join(OUTPUT_DIR, f"graph_{plot['id']}.json")
        with open(plot_path, "w", encoding="utf-8") as f:
            json.dump(plot_graph, f, indent=2)

    print(f"\n✅ Cognee ingestion pipeline complete!")
    print(f"   {len(graph['nodes'])} nodes, {len(graph['edges'])} edges")
    print(f"   Graph files saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
