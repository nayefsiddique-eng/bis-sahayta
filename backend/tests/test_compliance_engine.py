from datetime import date
import pytest
from app.schemas.product import ProductInput
from app.services.compliance_engine import check_qco_applicability, resolve_requirements

# Current test evaluation date: 2026-09-15
TODAY = date(2026, 9, 15)

def test_toys_qco_applicability_and_exemption():
    product = ProductInput(
        category="Toys",
        sub_category="Plastic Action Figures",
        description="Educational plastic toy",
        manufacturer_scale="msme",
        is_imported=False
    )
    result, _, _ = check_qco_applicability(product, today_date=TODAY)

    assert result.applies is True
    assert result.qco_id == "QCO-TOYS-2020"
    assert result.standard_id == "IS 9873 (Part 1):2019"
    assert result.effective_date == date(2021, 1, 1)
    assert result.exemption_status == "none"
    assert "mandatory" in result.reasoning.lower()

    reqs, labs = resolve_requirements(result)
    assert len(reqs) > 0
    assert any(r.requirement == "Mechanical and Physical Properties Test" for r in reqs)
    assert len(labs) > 0

def test_footwear_msme_exemption():
    msme_product = ProductInput(
        category="Footwear",
        description="Leather boots",
        manufacturer_scale="msme",
        is_imported=False
    )
    result, _, _ = check_qco_applicability(msme_product, today_date=TODAY)

    assert result.applies is True
    assert result.qco_id == "QCO-FOOTWEAR-2024"
    assert result.exemption_status == "msme"
    assert "MSME exemption applies" in result.reasoning

    large_product = ProductInput(
        category="Footwear",
        description="Leather boots",
        manufacturer_scale="large",
        is_imported=False
    )
    result_large, _, _ = check_qco_applicability(large_product, today_date=TODAY)
    assert result_large.exemption_status == "none"

def test_solar_pv_future_effective_date():
    product = ProductInput(
        category="Solar PV",
        description="Monocrystalline solar module",
        manufacturer_scale="large",
        is_imported=False
    )
    result, _, _ = check_qco_applicability(product, today_date=TODAY)

    assert result.applies is True
    assert result.qco_id == "QCO-SOLAR-2026"
    assert result.effective_date == date(2027, 1, 1)
    assert "not yet mandatory" in result.reasoning

def test_steel_products_resolution():
    product = ProductInput(
        category="Steel Products",
        sub_category="Stainless Steel",
        description="Stainless steel strip roll",
        manufacturer_scale="large",
        is_imported=False
    )
    result, _, _ = check_qco_applicability(product, today_date=TODAY)

    assert result.applies is True
    assert result.qco_id == "QCO-STEEL-2023"
    assert result.standard_id == "IS 6911:2017"

    reqs, labs = resolve_requirements(result)
    assert any(r.requirement == "Chemical Composition Analysis" for r in reqs)
    assert "NTH, Kolkata" in labs

def test_non_matching_category():
    product = ProductInput(
        category="Wooden Furniture",
        description="Dining table",
        manufacturer_scale="msme",
        is_imported=False
    )
    result, _, _ = check_qco_applicability(product, today_date=TODAY)

    assert result.applies is False
    assert result.qco_id == "N/A"
    assert result.exemption_status == "none"
    reqs, labs = resolve_requirements(result)
    assert len(reqs) == 0
    assert len(labs) == 0
