"""Criterion Details page - View full history and changes for a criterion."""

import pandas as pd
import streamlit as st

from streamlit_utils import (
    load_criterion_history,
    render_field_diff,
)

st.set_page_config(page_title="Criterion Details", layout="wide")

# Query parameters for navigation
query_params = st.query_params
criterion_id_from_url = query_params.get("criterion_id")

if query_params.get("page") != "criterion_details":
    query_params["page"] = "criterion_details"

# Back button
col1, col2 = st.columns([1, 5])
with col1:
    if st.button("⬅️ Back to Overview"):
        st.query_params.clear()
        st.switch_page("pages/trial_overview.py")
with col2:
    st.title("📋 Criterion Details")

# Get criterion ID from query params or input
default_criterion_id = 1
if criterion_id_from_url:
    try:
        default_criterion_id = int(criterion_id_from_url)
    except (ValueError, TypeError):
        st.error(f"Invalid criterion ID in URL: {criterion_id_from_url}")
        default_criterion_id = 1

# Criterion ID input
criterion_id = st.number_input(
    "Enter Criterion ID",
    min_value=1,
    value=default_criterion_id,
    step=1,
)

# Auto-load if criterion ID is from URL or button clicked
auto_load = criterion_id_from_url is not None

if st.button("Load Criterion") or auto_load:
    criterion, changes, children = load_criterion_history(criterion_id)

    if not criterion:
        st.error(f"Criterion {criterion_id} not found")
        st.stop()

    if query_params.get("criterion_id") != str(criterion_id):
        query_params["criterion_id"] = str(criterion_id)

    # Display criterion details
    st.subheader(f"Criterion {criterion.id}")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Version", criterion.version)
    with col2:
        st.metric("Active", "✅" if criterion.is_active else "❌")
    with col3:
        st.metric("Has Parent", "✅" if criterion.parent_id else "❌")

    st.markdown("---")

    # Current state
    st.markdown("### Current State")
    st.markdown(f"**Code:** `{criterion.code}`")
    st.markdown(f"**Text:** {criterion.text}")
    st.markdown(f"**Category:** {criterion.parsed_category}")
    st.markdown(f"**NCT ID:** {criterion.nct_id}")

    if criterion.parent_id:
        st.info(f"**Parent ID:** {criterion.parent_id}")

    if criterion.refinement_reason:
        st.success(f"**Last Refinement Reason:** {criterion.refinement_reason}")

    # Timestamps
    st.caption(f"Created: {criterion.created_at}")

    # Change history
    if changes:
        st.markdown("---")
        st.markdown("### Change History")

        for i, change in enumerate(changes, 1):
            with st.expander(
                f"{i}. {change.change_type.upper()} at {change.changed_at}",
                expanded=i == 1,
            ):
                if change.reason:
                    st.info(f"**Reason:** {change.reason}")

                # Render GitHub-style diff for common fields
                if change.old_value and change.new_value:
                    # Show diffs for text, code, and category fields
                    for field in ["text", "code", "parsed_category"]:
                        diff_html = render_field_diff(
                            change.old_value, change.new_value, field
                        )
                        if diff_html:
                            st.markdown(f"**{field.replace('_', ' ').title()}:**")
                            st.markdown(diff_html, unsafe_allow_html=True)

                    # Show full JSON in collapsed section for reference
                    with st.expander("View Raw JSON", expanded=False):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown("**Old Value:**")
                            st.json(change.old_value)
                        with col2:
                            st.markdown("**New Value:**")
                            st.json(change.new_value)
                else:
                    # Fallback to old display if only one value exists
                    col1, col2 = st.columns(2)
                    with col1:
                        if change.old_value:
                            st.markdown("**Old Value:**")
                            try:
                                st.json(change.old_value)
                            except Exception:
                                st.code(str(change.old_value))
                    with col2:
                        if change.new_value:
                            st.markdown("**New Value:**")
                            try:
                                st.json(change.new_value)
                            except Exception:
                                st.code(str(change.new_value))
    else:
        st.info("No change history available")

    # Children (if split)
    if children:
        st.markdown("---")
        st.markdown("### Children (Split Results)")

        children_df = pd.DataFrame(
            [
                {
                    "ID": child.id,
                    "Code": child.code,
                    "Text": child.text,
                    "Category": child.parsed_category,
                    "Version": child.version,
                    "Active": "✅" if child.is_active else "❌",
                }
                for child in children
            ]
        )
        st.dataframe(
            children_df,
            width="stretch",
            column_config={
                "Text": st.column_config.TextColumn(
                    "Text", width="large", help="Full text of the criterion"
                )
            },
        )

    # Parent details
    if criterion.parent_id:
        st.markdown("---")
        st.markdown(f"### Parent Criterion (ID {criterion.parent_id})")
        st.markdown(
            f"[🔗 View Parent Criterion](?page=criterion_details&criterion_id={criterion.parent_id})",
            unsafe_allow_html=False,
        )

st.markdown("---")
st.caption("💡 Tip: Use the back button to return to the trial overview")
