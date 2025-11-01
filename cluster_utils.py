"""Shared utilities for the Streamlit cluster exploration app."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from io import StringIO, TextIOBase
from itertools import zip_longest


@dataclass(frozen=True)
class CsvCluster:
    cluster_id: int
    criterion_type: str
    parsed_category: str
    representative_code: str
    representative_text: str
    size: int
    codes_count: int
    trials_count: int
    codes: list[str]
    trials: list[str]


def split_field(value: str | None) -> list[str]:
    """Parse a CSV cell that may contain a list representation."""
    if not value:
        return []

    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        items = value[1:-1].split(",")
        return [item.strip().strip('"').strip("'") for item in items if item.strip()]

    lines = [part.strip() for part in value.replace("\r", "").split("\n")]
    return [line for line in lines if line]


def load_clusters_from_csv(file_buffer: TextIOBase) -> list[CsvCluster]:
    """Load clusters from a CSV file-like object."""
    reader = csv.DictReader(file_buffer)
    clusters: list[CsvCluster] = []

    for row in reader:
        codes = split_field(row.get("Codes", row.get("codes")))
        trials = split_field(row.get("Trials", row.get("nct_ids")))
        clusters.append(
            CsvCluster(
                cluster_id=int(row.get("Cluster ID", row.get("id", "0")) or 0),
                criterion_type=row.get("Type", row.get("type", "")) or "",
                parsed_category=row.get("Category", row.get("parsed_category", ""))
                or "",
                representative_code=row.get(
                    "Representative Code",
                    row.get("representative_code", ""),
                )
                or "",
                representative_text=row.get(
                    "Representative Text",
                    row.get("representative_text", ""),
                )
                or "",
                size=int(row.get("Size", row.get("size", "0")) or 0),
                codes_count=len(codes),
                trials_count=len(trials),
                codes=codes,
                trials=trials,
            )
        )

    return clusters


def render_metrics(clusters: Iterable[CsvCluster]) -> None:
    """Render headline metrics for a collection of clusters."""
    import streamlit as st

    clusters = list(clusters)
    total_clusters = len(clusters)
    total_criteria = sum(cluster.size for cluster in clusters)
    multi_member = sum(1 for cluster in clusters if cluster.size > 1)

    col1, col2, col3 = st.columns(3)
    col1.metric("Clusters", total_clusters)
    col2.metric("Total Criteria", total_criteria)
    col3.metric("Multi-member Clusters", multi_member)


def cluster_matches_search(cluster: CsvCluster, query: str) -> bool:
    """Check whether the cluster matches the lower-cased search query."""
    if not query:
        return True

    haystacks = [
        cluster.representative_text.lower(),
        cluster.representative_code.lower(),
        " ".join(cluster.codes).lower(),
        " ".join(cluster.trials).lower(),
    ]
    return any(query in haystack for haystack in haystacks)


def cluster_to_row(
    cluster: CsvCluster, *, include_details: bool
) -> dict[str, str | int]:
    """Convert a cluster into a table row dict."""
    row: dict[str, str | int] = {
        "Cluster ID": cluster.cluster_id,
        "Type": cluster.criterion_type or "—",
        "Category": cluster.parsed_category or "—",
        "Representative Code": cluster.representative_code or "—",
        "Representative Text": cluster.representative_text,
        "Size": cluster.size,
        "# Codes": cluster.codes_count,
        "# Trials": cluster.trials_count,
    }

    if include_details:
        codes = "\n".join(cluster.codes)
        trials = "\n".join(cluster.trials)
        row["Codes"] = codes or "—"
        row["Trials"] = trials or "—"

    return row


def rows_to_csv(rows: list[dict[str, str | int]]) -> bytes:
    """Convert a list of table row dicts into CSV bytes."""
    if not rows:
        return b""

    fieldnames = list(rows[0].keys())
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def sort_clusters_by_size(clusters: Iterable[CsvCluster]) -> list[CsvCluster]:
    """Return clusters ordered by descending size."""
    return sorted(clusters, key=lambda cluster: cluster.size, reverse=True)


def filter_clusters(
    clusters: Iterable[CsvCluster],
    *,
    selected_types: Iterable[str],
    selected_categories: Iterable[str],
    min_cluster_size: int,
    search_query: str,
) -> list[CsvCluster]:
    """Filter clusters according to the configured controls."""
    selected_types = {item.lower() for item in selected_types}
    selected_categories = {item.lower() for item in selected_categories}
    query = search_query.strip().lower()

    filtered: list[CsvCluster] = []
    for cluster in clusters:
        cluster_type = (cluster.criterion_type or "—").lower()
        cluster_category = (cluster.parsed_category or "—").lower()
        if cluster_type not in selected_types:
            continue
        if cluster_category not in selected_categories:
            continue
        if cluster.size < min_cluster_size:
            continue
        if query and not cluster_matches_search(cluster, query):
            continue
        filtered.append(cluster)

    return filtered


def paired_codes_trials(cluster: CsvCluster) -> list[tuple[str, str]]:
    """Return newline-ready (code, trial) pairs for detail rendering."""
    return [
        (code or "—", trial or "—")
        for code, trial in zip_longest(cluster.codes, cluster.trials, fillvalue="")
    ]
