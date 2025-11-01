from sqlmodel import SQLModel, Field, String, Column, Index, JSON
from enum import StrEnum, auto
from datetime import datetime, UTC


class CriterionType(StrEnum):
    INCLUSION = auto()
    EXCLUSION = auto()


class CriterionCategory(StrEnum):
    DIAGNOSIS_DISEASE_STATE = "Diagnosis/Disease State"
    PARENT_BIOMARKER_PROFILE = "Parent Biomarker Profile"
    CONDITIONAL_ADDITIONAL_BIOMARKER = "Conditional Additional Biomarker"
    PERFORMANCE_STATUS = "Performance Status"
    ORGAN_FUNCTION = "Organ Function"
    PRIOR_TREATMENT_THERAPY = "Prior Treatment/Therapy"
    IMAGING_RADIOLOGY_FINDINGS = "Imaging/Radiology Findings"
    AGE_DEMOGRAPHICS = "Age/Demographics"
    CONCOMITANT_CONDITIONS = "Concomitant Medical Conditions/Comorbidities"
    PREGNANCY_LACTATION = "Pregnancy/Lactation"
    ALLERGIC_REACTIONS_HYPERSENSITIVITY = "Allergic Reactions/Hypersensitivity"
    ANATOMICAL_DISEASE_LOCATION = "Anatomical/Disease Location"
    LABORATORY_VALUES = "Laboratory Values"
    GENERAL_HEALTH_PHYSICAL_EXAM = "General Health/Physical Exam"
    TRIAL_SPECIFIC = "Trial Specific"
    OTHER = "Other"


class ParsedEligibilityCriteria(SQLModel, table=True):
    """Parsed eligibility criteria with LLM-generated questions."""

    __tablename__ = "eligibility_criteria_parsed"

    id: int = Field(default=None, primary_key=True)
    nct_id: str = Field(index=True)
    code: str = Field(max_length=255, index=True)
    text: str = Field()
    criterion_type: CriterionType = Field(
        sa_type=String, sa_column_kwargs={"name": "type"}
    )
    parsed_category: CriterionCategory = Field(sa_type=String)
    source: str = Field()

    version: int = Field(default=1, index=True)
    parent_id: int | None = Field(
        default=None, foreign_key="eligibility_criteria_parsed.id", index=True
    )
    refinement_reason: str | None = Field(default=None)
    is_active: bool = Field(default=True, index=True)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CriteriaChangeHistory(SQLModel, table=True):
    """Track all changes made to criteria during refinement."""

    __tablename__ = "criteria_change_history"

    id: int = Field(default=None, primary_key=True)
    criterion_id: int = Field(foreign_key="eligibility_criteria_parsed.id", index=True)
    change_type: str = Field(index=True)
    old_value: dict | None = Field(default=None, sa_column=Column(JSON))
    new_value: dict | None = Field(default=None, sa_column=Column(JSON))
    reason: str | None = Field(default=None)
    changed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("idx_criteria_change_history_criterion", "criterion_id"),
        Index("idx_criteria_change_history_type", "change_type"),
    )
