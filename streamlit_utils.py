"""Shared utilities for Streamlit app."""

import difflib

from sqlalchemy import case, cast, func
from sqlalchemy.types import Integer
from sqlmodel import select, Session, create_engine, SQLModel
import contextlib
import functools


@functools.cache
def get_engine():
    """Get the database engine."""
    return create_engine("sqlite:///test.db", echo=True)


def create_db_and_tables(test_engine=None):
    # Import all models to register them with SQLModel.metadata
    from models import ParsedEligibilityCriteria, CriteriaChangeHistory  # noqa: F401,F403

    db_engine = test_engine or get_engine()
    SQLModel.metadata.create_all(db_engine)


@contextlib.contextmanager
def session_context():
    """Context manager to provide a session."""
    with Session(get_engine()) as session:
        yield session


def load_trials():
    from models import (
        CriteriaChangeHistory,
        ParsedEligibilityCriteria,
    )

    """Load list of trials with criteria using SQLModel."""
    with session_context() as session:
        statement = (
            select(
                ParsedEligibilityCriteria.nct_id,
                func.count().label("total_criteria"),
                func.sum(cast(ParsedEligibilityCriteria.is_active, Integer)).label(
                    "active"
                ),
                func.sum(
                    case((ParsedEligibilityCriteria.version > 1, 1), else_=0)
                ).label("refined"),
            )
            .group_by(ParsedEligibilityCriteria.nct_id)
            .order_by(ParsedEligibilityCriteria.nct_id)
        )

        results = session.exec(statement).all()
        return [
            {
                "nct_id": r.nct_id,
                "total": r.total_criteria,
                "active": r.active or 0,
                "refined": r.refined or 0,
            }
            for r in results
        ]


def load_criteria(nct_id, show_inactive=False, include_history=False):
    """Load all criteria for a trial using SQLModel."""
    from models import (
        CriteriaChangeHistory,
        ParsedEligibilityCriteria,
    )

    with session_context() as session:
        statement = select(ParsedEligibilityCriteria).where(
            ParsedEligibilityCriteria.nct_id == nct_id
        )

        if not show_inactive:
            statement = statement.where(ParsedEligibilityCriteria.is_active)

        statement = statement.order_by(ParsedEligibilityCriteria.id)

        results = session.exec(statement).all()

        criteria_list = []
        for r in results:
            criterion_data = {
                "id": r.id,
                "code": r.code,
                "text": r.text,
                "type": (
                    r.criterion_type.value
                    if hasattr(r.criterion_type, "value")
                    else r.criterion_type
                ),
                "category": r.parsed_category,
                "version": r.version,
                "parent_id": r.parent_id,
                "reason": r.refinement_reason,
                "is_active": r.is_active,
                "created_at": r.created_at,
            }

            # Optionally load change history
            if include_history:
                changes_statement = (
                    select(CriteriaChangeHistory)
                    .where(CriteriaChangeHistory.criterion_id == r.id)
                    .order_by(CriteriaChangeHistory.changed_at.desc())
                )
                changes = session.exec(changes_statement).all()
                criterion_data["changes"] = changes

            criteria_list.append(criterion_data)

        return criteria_list


def render_diff(old_text: str | None, new_text: str | None) -> str:
    """Render GitHub-style inline diff with color-coded changes."""
    if not old_text and not new_text:
        return ""

    old_text = str(old_text) if old_text else ""
    new_text = str(new_text) if new_text else ""

    diff = difflib.unified_diff(
        old_text.splitlines(keepends=True),
        new_text.splitlines(keepends=True),
        lineterm="",
        n=3,
    )

    diff_html: list[str] = []
    for line in diff:
        line = line.rstrip()
        if line.startswith(("---", "+++")):
            continue
        if line.startswith("@@"):
            diff_html.append(
                '<div style="background-color: #e8f2ff; padding: 4px 8px;'
                ' margin: 4px 0; font-family: monospace; color: #0969da;">'
                f"{line}</div>"
            )
            continue
        if line.startswith("-"):
            diff_html.append(
                '<div style="background-color: #ffebe9; padding: 4px 8px;'
                ' margin: 2px 0; font-family: monospace;">'
                f'<span style="color: #cf222e;">- {line[1:]}</span></div>'
            )
            continue
        if line.startswith("+"):
            diff_html.append(
                '<div style="background-color: #dafbe1; padding: 4px 8px;'
                ' margin: 2px 0; font-family: monospace;">'
                f'<span style="color: #1a7f37;">+ {line[1:]}</span></div>'
            )
            continue
        diff_html.append(
            '<div style="padding: 4px 8px; margin: 2px 0;'
            f' font-family: monospace; color: #656d76;">{line}</div>'
        )

    return (
        "".join(diff_html)
        if diff_html
        else '<div style="padding: 8px; color: #656d76;">No changes detected</div>'
    )


def render_field_diff(
    old_value: dict | None, new_value: dict | None, field_name: str
) -> str | None:
    """Render diff for a specific field from old/new value dicts."""
    old_field = old_value.get(field_name, "") if isinstance(old_value, dict) else ""
    new_field = new_value.get(field_name, "") if isinstance(new_value, dict) else ""

    if old_field == new_field:
        return None

    return render_diff(old_field, new_field)


def load_criterion_history(criterion_id):
    """Load full history for a criterion using SQLModel."""
    from models import (
        CriteriaChangeHistory,
        ParsedEligibilityCriteria,
    )

    create_db_and_tables()
    with session_context() as session:
        # Get criterion details
        criterion = session.get(ParsedEligibilityCriteria, criterion_id)

        if not criterion:
            return None, [], []

        # Get change history
        changes_statement = (
            select(CriteriaChangeHistory)
            .where(CriteriaChangeHistory.criterion_id == criterion_id)
            .order_by(CriteriaChangeHistory.changed_at.desc())
        )
        changes = session.exec(changes_statement).all()

        # Get children if split
        children_statement = (
            select(ParsedEligibilityCriteria)
            .where(ParsedEligibilityCriteria.parent_id == criterion_id)
            .order_by(ParsedEligibilityCriteria.id)
        )
        children = session.exec(children_statement).all()

        return criterion, changes, children
