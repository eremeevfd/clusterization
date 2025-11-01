"""Trial Overview page - Browse and filter criteria by trial."""

import pandas as pd
import streamlit as st

from streamlit_utils import (
    load_criteria,
    load_trials,
    render_field_diff,
)

st.set_page_config(page_title="Trial Overview", layout="wide")

# Ensure URL reflects current page context
if st.query_params.get("page") != "trial_overview":
    st.query_params["page"] = "trial_overview"

trial_param = st.query_params.get("trial")

# Header with refresh button
col_title, col_refresh = st.columns([5, 1])
with col_title:
    st.title("📊 Eligibility Criteria - Trial Overview")
with col_refresh:
    st.write("")  # Spacing
    if st.button(
        "🔄 Refresh", width="stretch", help="Reload trials data from database"
    ):
        st.rerun()

# Load trials
all_trials = load_trials()
if not all_trials:
    st.warning("No trials found with criteria")
    st.stop()

# Trial filters
st.subheader("🔍 Trial Filters")

col1, col2 = st.columns(2)

with col1:
    # NCT ID search
    search_nct = st.text_input(
        "Search by NCT ID",
        value="",
        placeholder="e.g., NCT03997786",
        help="Filter trials by NCT ID (case-insensitive partial match)",
    )

with col2:
    # Filter by refined criteria
    show_only_refined = st.checkbox(
        "Show only trials with refined criteria",
        value=True,
        help="Show only trials that have at least one refined criterion (version > 1)",
    )

# Apply filters
trials = all_trials

if search_nct:
    trials = [t for t in trials if search_nct.upper() in t["nct_id"].upper()]

if show_only_refined:
    trials = [t for t in trials if t["refined"] > 0]

# Show filter results
if len(trials) < len(all_trials):
    st.info(f"Showing {len(trials)} of {len(all_trials)} trials")

if not trials:
    st.warning("No trials match the current filters")
    st.stop()

st.markdown("---")

# Trial selector with session state persistence
if "trial_selector" not in st.session_state:
    st.session_state.trial_selector = 0

# if trial_param:
#     matching_idx = next(
#         (idx for idx, trial in enumerate(trials) if trial["nct_id"] == trial_param),
#         None,
#     )
#     if matching_idx is not None:
#         st.session_state.trial_selector = matching_idx

# Reset selection if out of bounds
if st.session_state.trial_selector >= len(trials):
    st.session_state.trial_selector = 0


trial_options = [
    f"{t['nct_id']} ({t['active']} active, {t['refined']} refined)" for t in trials
]
print(f"Trial options: {trial_options}")
selected_trial_idx = st.selectbox(
    "Select Trial",
    range(len(trials)),
    format_func=lambda x: trial_options[x],
    index=st.session_state.trial_selector,
    key="trial_selector",
)
selected_trial = trials[selected_trial_idx]["nct_id"]

print(f"Selected trial: {selected_trial}")
if st.query_params.get("trial") != selected_trial:
    st.query_params["trial"] = selected_trial

print(f"Updated query params: {st.query_params}")

# Show inactive criteria toggle with session state
if "show_inactive" not in st.session_state:
    st.session_state.show_inactive = False

show_inactive = st.checkbox(
    "Show inactive criteria",
    value=st.session_state.show_inactive,
    key="show_inactive_checkbox",
)
st.session_state.show_inactive = show_inactive

st.subheader(f"Criteria for {selected_trial}")

# Load and display criteria
criteria = load_criteria(selected_trial, show_inactive, include_history=True)

# Statistics
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Criteria", len(criteria))
with col2:
    active_count = sum(1 for c in criteria if c["is_active"])
    st.metric("Active", active_count)
with col3:
    refined_count = sum(1 for c in criteria if c["version"] > 1)
    st.metric("Refined (v>1)", refined_count)
with col4:
    split_count = sum(1 for c in criteria if c["parent_id"] is not None)
    st.metric("Split from Parent", split_count)

# Active criteria snapshot
active_snapshot = [
    {
        "ID": c["id"],
        "Code": c["code"],
        "Text": c["text"],
        "Type": c["type"],
        "Category": c["category"],
        "Version": c["version"],
    }
    for c in criteria
    if c["is_active"]
]

if active_snapshot:
    st.markdown("### Active Criteria Snapshot")
    snapshot_df = (
        pd.DataFrame(active_snapshot)
        .sort_values(by=["Version", "Type", "ID"], ascending=[False, True, False])
        .reset_index(drop=True)
    )
    st.dataframe(
        snapshot_df,
        width="stretch",
        hide_index=True,
        column_config={
            "Text": st.column_config.TextColumn(
                "Text", width="large", help="Current active criterion text"
            )
        },
    )
else:
    st.info("No active criteria for this trial.")

# Filters with session state persistence
st.subheader("Filters")

# Initialize filter state
if "version_filter" not in st.session_state:
    st.session_state.version_filter = []
if "category_filter" not in st.session_state:
    st.session_state.category_filter = []

col1, col2 = st.columns(2)
with col1:
    version_filter = st.multiselect(
        "Version",
        options=sorted({c["version"] for c in criteria}),
        default=st.session_state.version_filter,
        key="version_filter_multiselect",
    )
    st.session_state.version_filter = version_filter
with col2:
    category_filter = st.multiselect(
        "Category",
        options=sorted({c["category"] for c in criteria}),
        default=st.session_state.category_filter,
        key="category_filter_multiselect",
    )
    st.session_state.category_filter = category_filter

# Apply filters
filtered = criteria
if version_filter:
    filtered = [c for c in filtered if c["version"] in version_filter]
if category_filter:
    filtered = [c for c in filtered if c["category"] in category_filter]

# Sort so refined criteria appear first, then by version/id descending
filtered = sorted(
    filtered,
    key=lambda c: (
        c["version"] <= 1,
        -c["version"],
        -c["id"],
    ),
)

st.info(f"Showing {len(filtered)} of {len(criteria)} criteria")

# Display criteria in a table
for criterion in filtered:
    # Build expander title with status indicators
    title_parts = []
    title_parts.append("✅" if criterion["is_active"] else "❌")
    title_parts.append(f"ID {criterion['id']}")
    title_parts.append(f"{criterion['code']}")

    # Add version badge
    if criterion["version"] > 1:
        title_parts.append(f"🔄 v{criterion['version']}")
    else:
        title_parts.append(f"v{criterion['version']}")

    # Add parent indicator if this is a child
    if criterion["parent_id"]:
        title_parts.append(f"👶 (from #{criterion['parent_id']})")

    expander_title = " ".join(title_parts)

    with st.expander(expander_title):
        # Main content
        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown(f"**Text:** {criterion['text']}")
            st.markdown(f"**Category:** {criterion['category']}")

        with col2:
            st.markdown(f"**Version:** {criterion['version']}")
            st.markdown(f"**Active:** {criterion['is_active']}")
            if criterion["parent_id"]:
                st.markdown(
                    "**Parent ID:** "
                    f"[#{criterion['parent_id']}](?page=criterion_details&criterion_id={criterion['parent_id']})"
                )

        # Historical information section
        st.markdown("---")
        st.markdown("**📜 Historical Information**")

        hist_col1, hist_col2 = st.columns(2)

        with hist_col1:
            st.caption(
                f"🕐 Created: {criterion['created_at'].strftime('%Y-%m-%d %H:%M:%S')}"
            )

            # Count children
            children_count = sum(
                1 for c in criteria if c.get("parent_id") == criterion["id"]
            )
            if children_count > 0:
                st.caption(
                    f"👶 Has {children_count} child{'ren' if children_count > 1 else ''} (split result)"
                )

        with hist_col2:
            if criterion["version"] > 1:
                st.caption(
                    f"🔄 Refined {criterion['version'] - 1} time{'s' if criterion['version'] > 2 else ''}"
                )
            else:
                st.caption("✨ Original (never refined)")

        # Refinement reason
        if criterion["reason"]:
            st.info(f"**Last Refinement Reason:** {criterion['reason']}")

        # Embedded change history
        changes = criterion.get("changes") or []
        if changes:
            st.markdown("**📈 Change History**")
            for idx, change in enumerate(changes, start=1):
                change_title = (
                    f"{idx}. {change.change_type.upper()} • "
                    f"{change.changed_at.strftime('%Y-%m-%d %H:%M')}"
                )
                with st.expander(change_title, expanded=idx == 1):
                    if change.reason:
                        st.info(f"**Reason:** {change.reason}")

                    diffs_rendered = False
                    for field_name, label in [
                        ("text", "Text"),
                        ("code", "Code"),
                        ("parsed_category", "Category"),
                    ]:
                        diff_html = render_field_diff(
                            change.old_value, change.new_value, field_name
                        )
                        if diff_html:
                            diffs_rendered = True
                            st.markdown(f"**{label}:**")
                            st.markdown(diff_html, unsafe_allow_html=True)

                    if not diffs_rendered:
                        st.caption("No field-level differences captured.")

                    if change.old_value or change.new_value:
                        with st.expander("View Raw JSON", expanded=False):
                            raw_col1, raw_col2 = st.columns(2)
                            with raw_col1:
                                if change.old_value:
                                    st.markdown("**Old Value:**")
                                    st.json(change.old_value)
                            with raw_col2:
                                if change.new_value:
                                    st.markdown("**New Value:**")
                                    st.json(change.new_value)
        else:
            st.caption("No change history recorded yet.")

        # View history link
        st.markdown(
            f"[📊 View Full History & Changes](?page=criterion_details&criterion_id={criterion['id']})",
            unsafe_allow_html=False,
        )

st.markdown("---")
st.caption(
    "💡 Tip: Click 'View Full History' to see detailed change history for each criterion"
)
