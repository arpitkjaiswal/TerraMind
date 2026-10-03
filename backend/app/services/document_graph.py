"""Project saved document metadata without inventing extracted agronomic facts."""
from datetime import date


def merge_document_graph(plot, documents, graph, date_from=None, date_to=None):
    nodes = {node["id"]: node for node in graph["nodes"] if node.get("id")}
    edges = [edge for edge in graph["edges"] if edge and
             edge.get("source") in nodes and edge.get("target") in nodes]
    field_id = next((key for key, node in nodes.items() if node["type"] == "Field"),
                    f"record-field:{plot.id}")
    if field_id not in nodes:
        nodes[field_id] = {
            "id": field_id, "type": "Field", "label": plot.name, "date": None,
            "properties": {"crop_type": plot.crop_type, "size_ha": plot.size_ha},
        }
    for doc in documents:
        # Defend the projection boundary as well as the database query.
        if doc.farm_id != plot.farm_id or doc.plot_id != plot.id:
            continue
        # The database stores event dates as ISO strings, not Date columns.
        event_date = doc.uploaded_at.date()
        if doc.date_of_event:
            try:
                event_date = date.fromisoformat(str(doc.date_of_event))
            except ValueError:
                # Legacy invalid dates must not make the entire field unreadable.
                pass
        if (date_from and event_date < date_from) or (date_to and event_date > date_to):
            continue
        node_id = f"record-document:{doc.id}"
        nodes[node_id] = {
            "id": node_id, "type": "Document", "label": doc.label,
            "date": event_date.isoformat(),
            "properties": {"source_type": doc.source_type, "status": doc.ingest_status,
                           "source_document_id": doc.id},
        }
        edges.append({"source": field_id, "target": node_id, "type": "HAS_DOCUMENT",
                      "confirmed": True, "date": event_date.isoformat(), "source_document_id": doc.id})
    return {"nodes": list(nodes.values()), "edges": edges}
