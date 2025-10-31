"""Streamlit visualization for eligibility clusters exported as CSV.

Run with:
    streamlit run get_cure_backend/llm/service/cluster_visualizer_csv.py
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from io import StringIO, TextIOBase
from itertools import zip_longest

import streamlit as st


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


def _split_field(value: str | None) -> list[str]:
    if not value:
        return []
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        items = value[1:-1].split(",")
        return [item.strip().strip('"').strip("'") for item in items if item.strip()]
    lines = [part.strip() for part in value.replace("\r", "").split("\n")]
    return [line for line in lines if line]


def _load_clusters_from_csv(file_buffer: TextIOBase) -> list[CsvCluster]:
    reader = csv.DictReader(file_buffer)
    clusters: list[CsvCluster] = []
    for row in reader:
        codes = _split_field(row.get("Codes", row.get("codes")))
        trials = _split_field(row.get("Trials", row.get("nct_ids")))
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


def _render_metrics(clusters: Iterable[CsvCluster]) -> None:
    clusters = list(clusters)
    total_clusters = len(clusters)
    total_criteria = sum(cluster.size for cluster in clusters)
    multi_member = sum(1 for cluster in clusters if cluster.size > 1)

    col1, col2, col3 = st.columns(3)
    col1.metric("Clusters", total_clusters)
    col2.metric("Total Criteria", total_criteria)
    col3.metric("Multi-member Clusters", multi_member)


def _cluster_matches_search(cluster: CsvCluster, query: str) -> bool:
    haystacks = [
        cluster.representative_text.lower(),
        cluster.representative_code.lower(),
        " ".join(cluster.codes).lower(),
        " ".join(cluster.trials).lower(),
    ]
    return any(query in haystack for haystack in haystacks)


def _cluster_to_row(
    cluster: CsvCluster, *, include_details: bool
) -> dict[str, str | int]:
    row: dict[str, str | int] = {
        "Cluster ID": cluster.cluster_id,
        "Type": cluster.criterion_type,
        "Category": cluster.parsed_category,
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


def _rows_to_csv(rows: list[dict[str, str | int]]) -> bytes:
    if not rows:
        return b""

    fieldnames = list(rows[0].keys())
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def main() -> None:
    st.set_page_config(page_title="Eligibility Clusters (CSV)", layout="wide")
    st.title("Eligibility Criteria Clusters (CSV)")

    uploaded = st.file_uploader(
        "Upload clusters CSV", type=["csv"], accept_multiple_files=False
    )
    if uploaded is None:
        st.info("Upload a CSV export generated from the cluster visualizer to begin.")
        return

    text_buffer = StringIO(uploaded.getvalue().decode("utf-8"))
    clusters = _load_clusters_from_csv(text_buffer)
    if not clusters:
        st.warning("The CSV file does not contain any cluster rows.")
        return

    _render_metrics(clusters)

    available_types = sorted({cluster.criterion_type or "—" for cluster in clusters})
    selected_types = st.multiselect(
        "Criterion Types",
        options=available_types,
        default=available_types,
    )

    type_filtered = [
        cluster
        for cluster in clusters
        if (cluster.criterion_type or "—") in selected_types
    ]

    available_categories = sorted(
        {cluster.parsed_category or "—" for cluster in type_filtered}
    )
    selected_categories = st.multiselect(
        "Categories",
        options=available_categories,
        default=available_categories,
    )

    max_cluster_size = (
        max(cluster.size for cluster in type_filtered) if type_filtered else 1
    )
    min_cluster_size = st.slider(
        "Minimum Cluster Size",
        min_value=1,
        max_value=max_cluster_size,
        value=1,
        help="Filter out clusters with fewer than the selected number of criteria.",
    )

    search_query = (
        st.text_input(
            "Search (text, code, or NCT ID)",
            placeholder="e.g. biologics, pregnancy, NCT01234567",
        )
        .strip()
        .lower()
    )

    filtered_clusters = [
        cluster
        for cluster in type_filtered
        if (cluster.parsed_category or "—") in selected_categories
        and cluster.size >= min_cluster_size
        and (not search_query or _cluster_matches_search(cluster, search_query))
    ]

    st.subheader("Filtered Summary")
    _render_metrics(filtered_clusters)

    if not filtered_clusters:
        st.warning("No clusters match the current filters.")
        return

    detailed_view = st.toggle(
        "Show detailed columns (codes & trials)",
        value=False,
        help="Adds columns with newline-separated codes and trials.",
    )

    clusters_by_id = {cluster.cluster_id: cluster for cluster in filtered_clusters}
    default_order = sorted(
        filtered_clusters, key=lambda cluster: cluster.size, reverse=True
    )

    table_rows = [
        _cluster_to_row(cluster, include_details=detailed_view)
        for cluster in default_order
    ]
    st.dataframe(table_rows, hide_index=True, width="stretch")
    displayed_ids = [
        row["Cluster ID"]
        for row in table_rows
        if isinstance(row.get("Cluster ID"), int)
    ]
    ordered_filtered = [clusters_by_id[cluster_id] for cluster_id in displayed_ids]

    filtered_csv = _rows_to_csv(
        [_cluster_to_row(cluster, include_details=True) for cluster in ordered_filtered]
    )
    st.download_button(
        "Download filtered clusters (CSV)",
        data=filtered_csv,
        file_name="eligibility_clusters_filtered.csv",
        mime="text/csv",
        disabled=not ordered_filtered,
    )

    st.subheader("Cluster Details")

    default_limit = min(25, len(ordered_filtered))
    limit = st.number_input(
        "Maximum clusters to display below",
        min_value=1,
        max_value=len(ordered_filtered),
        value=default_limit,
        step=1,
    )

    for cluster in ordered_filtered[: int(limit)]:
        header = f"[{cluster.criterion_type.upper()}] {cluster.representative_text} (size {cluster.size})"
        with st.expander(header):
            st.markdown(
                f"**Representative code:** `{cluster.representative_code or '-'}'"
            )
            st.markdown(f"**Category:** {cluster.parsed_category}")
            st.markdown(f"**Total criteria:** {cluster.size}")
            paired = [
                (code or "—", trial or "—")
                for code, trial in zip_longest(
                    cluster.codes, cluster.trials, fillvalue=""
                )
            ]
            for idx, (code, trial) in enumerate(paired, start=1):
                st.markdown(f"{idx}. `{code or '—'}` — {trial or '—'}")


if __name__ == "__main__":  # pragma: no cover - Streamlit entry point
    main()
