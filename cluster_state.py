"""Session state helpers for the multi-page Streamlit app."""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from cluster_utils import CsvCluster

CLUSTERS_KEY = "clusters"
CLUSTER_SOURCE_KEY = "clusters_source_signature"

FILTER_TYPES_KEY = "cluster_filter_selected_types"
FILTER_CATEGORIES_KEY = "cluster_filter_selected_categories"
FILTER_MIN_SIZE_KEY = "cluster_filter_min_size"
FILTER_SEARCH_KEY = "cluster_filter_search_query"


@dataclass(frozen=True)
class FilterState:
    available_types: list[str]
    available_categories: list[str]
    selected_types: list[str]
    selected_categories: list[str]
    min_cluster_size: int
    max_cluster_size: int
    search_query: str


def set_clusters(clusters: list[CsvCluster], source_signature: str) -> None:
    """Persist clusters and their source signature in session state."""
    st.session_state[CLUSTERS_KEY] = clusters
    st.session_state[CLUSTER_SOURCE_KEY] = source_signature


def get_clusters() -> list[CsvCluster]:
    """Retrieve clusters from session state."""
    return st.session_state.get(CLUSTERS_KEY, [])


def get_cluster_source_signature() -> str | None:
    """Return the signature of the currently-loaded cluster file."""
    return st.session_state.get(CLUSTER_SOURCE_KEY)


def clear_clusters() -> None:
    """Remove clusters from session state."""
    st.session_state.pop(CLUSTERS_KEY, None)
    st.session_state.pop(CLUSTER_SOURCE_KEY, None)


def clear_filter_state() -> None:
    """Reset all filter controls."""
    st.session_state.pop(FILTER_TYPES_KEY, None)
    st.session_state.pop(FILTER_CATEGORIES_KEY, None)
    st.session_state.pop(FILTER_MIN_SIZE_KEY, None)
    st.session_state.pop(FILTER_SEARCH_KEY, None)


def require_clusters() -> list[CsvCluster]:
    """Ensure clusters have been uploaded before using other pages."""
    clusters = get_clusters()
    if not clusters:
        st.warning("Upload a CSV on the Cluster Explorer page to explore clusters.")
        st.stop()
    return clusters


def ensure_filter_state(clusters: list[CsvCluster]) -> FilterState:
    """Synchronize filter session state with the loaded clusters."""
    if not clusters:
        return FilterState([], [], [], [], 1, 1, "")

    type_options = sorted({cluster.criterion_type or "—" for cluster in clusters})
    category_options = sorted({cluster.parsed_category or "—" for cluster in clusters})
    max_cluster_size = max((cluster.size for cluster in clusters), default=1)
    max_cluster_size = max(1, max_cluster_size)

    selected_types = _read_list_state(FILTER_TYPES_KEY, type_options)
    selected_categories = _read_list_state(FILTER_CATEGORIES_KEY, category_options)

    min_size = st.session_state.get(FILTER_MIN_SIZE_KEY, 1)
    if not isinstance(min_size, int):
        min_size = 1
    min_size = min(max(min_size, 1), max_cluster_size)
    st.session_state[FILTER_MIN_SIZE_KEY] = min_size

    search_query = st.session_state.get(FILTER_SEARCH_KEY, "")
    if not isinstance(search_query, str):
        search_query = ""
    st.session_state[FILTER_SEARCH_KEY] = search_query

    return FilterState(
        available_types=type_options,
        available_categories=category_options,
        selected_types=selected_types,
        selected_categories=selected_categories,
        min_cluster_size=min_size,
        max_cluster_size=max_cluster_size,
        search_query=search_query,
    )


def _read_list_state(key: str, options: list[str]) -> list[str]:
    """Read a list from session state ensuring it is aligned with options."""
    value = st.session_state.get(key)
    if not isinstance(value, list):
        value = options.copy()
    else:
        filtered = [item for item in value if item in options]
        if not filtered and value:
            filtered = options.copy()
        value = filtered
    st.session_state[key] = value
    return value
