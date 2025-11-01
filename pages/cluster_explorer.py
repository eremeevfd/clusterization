"""Primary page for uploading and exploring eligibility clusters."""

from __future__ import annotations

import csv
import hashlib
from io import StringIO

import streamlit as st

from cluster_state import (
    FILTER_CATEGORIES_KEY,
    FILTER_MIN_SIZE_KEY,
    FILTER_SEARCH_KEY,
    FILTER_TYPES_KEY,
    FilterState,
    clear_clusters,
    clear_filter_state,
    ensure_filter_state,
    get_cluster_source_signature,
    get_clusters,
    set_clusters,
)
from cluster_utils import (
    cluster_to_row,
    filter_clusters,
    load_clusters_from_csv,
    paired_codes_trials,
    render_metrics,
    rows_to_csv,
    sort_clusters_by_size,
)


def _compute_signature(
    uploaded_file: "st.runtime.uploaded_file_manager.UploadedFile",
) -> str:
    """Create a stable signature for identifying an uploaded file."""
    file_bytes = uploaded_file.getvalue()
    digest = hashlib.sha256(file_bytes).hexdigest()
    return f"{uploaded_file.name}:{uploaded_file.size}:{digest}"


def _load_uploaded_clusters(
    uploaded_file: "st.runtime.uploaded_file_manager.UploadedFile",
) -> list:
    """Decode the uploaded CSV into clusters."""
    try:
        text_buffer = StringIO(uploaded_file.getvalue().decode("utf-8"))
    except UnicodeDecodeError as exc:  # pragma: no cover - streamlit runtime
        st.error(f"Unable to decode `{uploaded_file.name}` as UTF-8: {exc}")
        return []

    try:
        return load_clusters_from_csv(text_buffer)
    except csv.Error as exc:  # pragma: no cover - streamlit runtime
        st.error(f"Failed to parse `{uploaded_file.name}`: {exc}")
        return []


def _render_filters(
    filter_state: FilterState,
) -> tuple[list[str], list[str], int, str, bool]:
    """Render filter controls and return their values."""
    st.subheader("Filters")

    selected_types = st.multiselect(
        "Criterion Types",
        options=filter_state.available_types,
        default=filter_state.selected_types,
        key=FILTER_TYPES_KEY,
    )

    selected_categories = st.multiselect(
        "Categories",
        options=filter_state.available_categories,
        default=filter_state.selected_categories,
        key=FILTER_CATEGORIES_KEY,
    )

    min_cluster_size = st.slider(
        "Minimum Cluster Size",
        min_value=1,
        max_value=filter_state.max_cluster_size,
        value=filter_state.min_cluster_size,
        key=FILTER_MIN_SIZE_KEY,
        help="Filter out clusters with fewer than the selected number of criteria.",
    )

    search_query = st.text_input(
        "Search (text, code, or NCT ID)",
        placeholder="e.g. biologics, pregnancy, NCT01234567",
        value=filter_state.search_query,
        key=FILTER_SEARCH_KEY,
    )

    detailed_view = st.toggle(
        "Show detailed columns (codes & trials)",
        value=st.session_state.get("explorer_show_details", False),
        key="explorer_show_details",
        help="Adds columns with newline-separated codes and trials.",
    )

    return (
        selected_types,
        selected_categories,
        int(min_cluster_size),
        search_query,
        bool(detailed_view),
    )


def _render_table(filtered_clusters: list) -> None:
    """Render the filtered table and download button."""
    ordered_clusters = sort_clusters_by_size(filtered_clusters)
    detailed_view = bool(st.session_state.get("explorer_show_details", False))

    table_rows = [
        cluster_to_row(cluster, include_details=detailed_view)
        for cluster in ordered_clusters
    ]

    st.dataframe(table_rows, hide_index=True, use_container_width=True)

    filtered_csv = rows_to_csv(
        [cluster_to_row(cluster, include_details=True) for cluster in ordered_clusters]
    )
    st.download_button(
        "Download filtered clusters (CSV)",
        data=filtered_csv,
        file_name="eligibility_clusters_filtered.csv",
        mime="text/csv",
        disabled=not ordered_clusters,
    )


def _render_details(filtered_clusters: list) -> None:
    """Render expandable detail sections for the filtered clusters."""
    ordered_clusters = sort_clusters_by_size(filtered_clusters)
    default_limit = min(25, len(ordered_clusters))

    limit_key = "explorer_details_limit"
    current_limit = int(st.session_state.get(limit_key, default_limit))
    current_limit = min(max(current_limit, 1), len(ordered_clusters))
    st.session_state[limit_key] = current_limit

    limit = st.number_input(
        "Maximum clusters to display below",
        min_value=1,
        max_value=len(ordered_clusters),
        value=current_limit,
        step=1,
        key=limit_key,
    )

    for cluster in ordered_clusters[: int(limit)]:
        header = (
            f"[{(cluster.criterion_type or '—').upper()}] "
            f"{cluster.representative_text} (size {cluster.size})"
        )
        with st.expander(header):
            st.markdown(
                f"**Representative code:** `{cluster.representative_code or '-'}'"
            )
            st.markdown(f"**Category:** {cluster.parsed_category or '—'}")
            st.markdown(f"**Total criteria:** {cluster.size}")
            st.divider()

            for idx, (code, trial) in enumerate(paired_codes_trials(cluster), start=1):
                st.markdown(f"{idx}. `{code}` — {trial}")


def main() -> None:
    st.set_page_config(page_title="Eligibility Clusters Explorer", layout="wide")
    st.title("Cluster Explorer")
    st.write(
        "Upload a CSV export from the cluster visualizer, then use the filters below "
        "to analyze and export subsets or inspect individual clusters."
    )

    uploaded = st.file_uploader(
        "Upload clusters CSV", type=["csv"], accept_multiple_files=False
    )

    if uploaded is not None:
        signature = _compute_signature(uploaded)
        if signature != get_cluster_source_signature():
            clusters = _load_uploaded_clusters(uploaded)
            if clusters:
                set_clusters(clusters, signature)
                clear_filter_state()
                ensure_filter_state(clusters)
                st.success(
                    f"Loaded {len(clusters)} clusters from `{uploaded.name}`. "
                    "Adjust the filters below to explore the dataset."
                )
            else:
                clear_clusters()
                clear_filter_state()
                st.warning(
                    "No clusters were loaded from the uploaded file. "
                    "Please verify the CSV export."
                )
        else:
            st.info("This file is already loaded. Adjust the filters below.")

    clusters = get_clusters()
    if not clusters:
        st.info("Upload a clusters CSV to get started.")
        st.stop()

    filter_state = ensure_filter_state(clusters)

    st.subheader("Dataset Overview")
    render_metrics(clusters)

    (
        selected_types,
        selected_categories,
        min_cluster_size,
        search_query,
        _,
    ) = _render_filters(filter_state)

    filtered_clusters = filter_clusters(
        clusters,
        selected_types=selected_types,
        selected_categories=selected_categories,
        min_cluster_size=min_cluster_size,
        search_query=search_query,
    )

    st.subheader("Filtered Summary")
    render_metrics(filtered_clusters)

    if not filtered_clusters:
        st.warning("No clusters match the current filters.")
        st.stop()

    st.subheader("Filtered Table")
    _render_table(filtered_clusters)

    st.subheader("Cluster Details")
    _render_details(filtered_clusters)


if __name__ == "__main__":  # pragma: no cover - Streamlit page entry point
    main()
