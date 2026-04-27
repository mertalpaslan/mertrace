from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import chromadb
from umap import UMAP
import hdbscan

from app.core.config import settings
from app.core.logging import get_logger
from app.ingestion.embedder import collection_name

logger = get_logger(__name__)

UMAP_N_COMPONENTS = 2
UMAP_N_NEIGHBORS = 15
UMAP_MIN_DIST = 0.1
HDBSCAN_MIN_CLUSTER_SIZE = 5


def build_umap(
    project_id: str,
    chroma_client: chromadb.ClientAPI,
) -> Path:
    """
    Fetch all embeddings from ChromaDB, run UMAP + HDBSCAN,
    and save umap_coords.json to the project data directory.
    Returns the path to the saved file.
    """
    t0 = time.monotonic()
    col = chroma_client.get_collection(collection_name(project_id))
    count = col.count()

    if count == 0:
        raise ValueError(f"No embeddings found for project {project_id}")

    logger.info("Fetching embeddings for UMAP", extra={"count": count, "project_id": project_id})

    # Fetch in batches of 5000 (ChromaDB limit)
    all_embeddings = []
    all_metadatas = []
    all_ids = []
    batch_size = 5000

    for offset in range(0, count, batch_size):
        result = col.get(
            limit=batch_size,
            offset=offset,
            include=["embeddings", "metadatas"],
        )
        all_embeddings.extend(result["embeddings"])
        all_metadatas.extend(result["metadatas"])
        all_ids.extend(result["ids"])

    X = np.array(all_embeddings, dtype=np.float32)

    # UMAP reduction
    logger.info("Running UMAP", extra={"shape": list(X.shape)})
    reducer = UMAP(
        n_components=UMAP_N_COMPONENTS,
        n_neighbors=min(UMAP_N_NEIGHBORS, count - 1),
        min_dist=UMAP_MIN_DIST,
        metric="cosine",
        random_state=42,
        low_memory=True,
    )
    coords = reducer.fit_transform(X)

    # HDBSCAN clustering
    logger.info("Running HDBSCAN clustering")
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min(HDBSCAN_MIN_CLUSTER_SIZE, max(2, count // 10)),
        metric="euclidean",
        prediction_data=False,
    )
    labels = clusterer.fit_predict(coords)

    # Build output
    points = []
    for i, (cid, meta, coord) in enumerate(zip(all_ids, all_metadatas, coords)):
        points.append({
            "chunk_id": cid,
            "x": float(coord[0]),
            "y": float(coord[1]),
            "chunk_type": meta.get("chunk_type", "unknown"),
            "file_path": meta.get("file_path", ""),
            "symbol_name": meta.get("symbol_name", ""),
            "language": meta.get("language", "unknown"),
            "cluster": int(labels[i]),
        })

    # Compute cluster centroids
    unique_labels = sorted(set(labels.tolist()) - {-1})
    clusters = []
    for label in unique_labels:
        mask = labels == label
        centroid = coords[mask].mean(axis=0)
        clusters.append({
            "id": label,
            "label": f"Cluster {label}",
            "centroid": [float(centroid[0]), float(centroid[1])],
        })

    output = {"points": points, "clusters": clusters}

    # Save to disk
    out_dir = Path(settings.projects_data_dir) / project_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "umap_coords.json"
    out_file.write_text(json.dumps(output))

    duration_ms = int((time.monotonic() - t0) * 1000)
    logger.info(
        "UMAP complete",
        extra={"points": len(points), "clusters": len(clusters), "duration_ms": duration_ms},
    )
    return out_file
