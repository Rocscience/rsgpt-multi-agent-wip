"""Tests for enum argument normalization (product-agnostic)."""

from app.services.multi_agent.enum_tool_args import (
    normalize_enum_tool_arguments,
    parse_enum_mappings,
    resolve_enum_argument,
)

_LATERAL_DESC = (
    "- Parameter 'lateralType' (LateralType): {0: 'Elastic', 1: 'SoftClay', 2: 'Sand'}"
)


def test_parse_enum_mappings_from_tool_description():
    mappings = parse_enum_mappings(_LATERAL_DESC)
    assert mappings["lateraltype"]["SoftClay"] == 1
    assert mappings["lateraltype"]["softclay"] == 1


def test_resolve_enum_from_getter_output():
    mapping = parse_enum_mappings(_LATERAL_DESC)["lateraltype"]
    assert resolve_enum_argument("<LateralType.SoftClay: 1>", mapping) == 1
    assert resolve_enum_argument("Sand", mapping) == 2


def test_normalize_lateral_type_ui_label_via_fuzzy_match():
    out = normalize_enum_tool_arguments(
        "RSP_Soil_Property_1_LateralProperties_setLateralType",
        {"lateralType": "API clay + Matlock"},
        tool_description=_LATERAL_DESC,
    )
    assert out["lateralType"] == 1

    out2 = normalize_enum_tool_arguments(
        "RSP_Soil_Property_2_LateralProperties_setLateralType",
        {"lateralType": "API sand + Reese"},
        tool_description=_LATERAL_DESC,
    )
    assert out2["lateralType"] == 2


def test_unmapped_string_left_unchanged_without_description():
    out = normalize_enum_tool_arguments(
        "RSP_Soil_Property_2_LateralProperties_setLateralType",
        {"lateralType": "API sand + Reese"},
    )
    assert out["lateralType"] == "API sand + Reese"
