"""
Tests for the Atomization Stage (Stage 1)

The atomization stage splits compound constraints into atomic units.
"""
import pytest


@pytest.mark.asyncio
async def test_atomization_single_constraint(atomization_stage):
    """
    Test that a single day+time constraint is NOT split.
    "I can work Monday morning" should remain as one constraint.
    """
    input_text = "I can work Monday morning"
    
    result = await atomization_stage.process(input_text)
    
    assert isinstance(result, list)
    assert len(result) == 1, f"Expected 1 constraint, got {len(result)}: {result}"
    assert "monday" in result[0]["text"].lower()


@pytest.mark.asyncio
async def test_atomization_compound_and_separator(atomization_stage):
    """
    Test that explicit 'and' separator splits into multiple constraints.
    "I cannot work Sunday and Monday" should become 2 constraints.
    """
    input_text = "I cannot work Sunday and Monday"
    
    result = await atomization_stage.process(input_text)
    
    assert isinstance(result, list)
    assert len(result) == 2, f"Expected 2 constraints, got {len(result)}: {result}"
    
    texts = [c["text"].lower() for c in result]
    assert any("sunday" in t for t in texts), "Should have Sunday constraint"
    assert any("monday" in t for t in texts), "Should have Monday constraint"


@pytest.mark.asyncio
async def test_atomization_compound_but_separator(atomization_stage):
    """
    Test that 'but' separator splits into multiple constraints.
    "I prefer mornings but cannot work Friday" should become 2 constraints.
    """
    input_text = "I prefer mornings but cannot work Friday"
    
    result = await atomization_stage.process(input_text)
    
    assert isinstance(result, list)
    assert len(result) == 2, f"Expected 2 constraints, got {len(result)}: {result}"


@pytest.mark.asyncio
async def test_atomization_comma_separated_list(atomization_stage):
    """
    Test that comma-separated day lists are split.
    "I cannot work Monday, Tuesday, and Wednesday" should become 3 constraints.
    """
    input_text = "I cannot work Monday, Tuesday, and Wednesday"
    
    result = await atomization_stage.process(input_text)
    
    assert isinstance(result, list)
    assert len(result) == 3, f"Expected 3 constraints, got {len(result)}: {result}"


@pytest.mark.asyncio
async def test_atomization_time_period_only(atomization_stage):
    """
    Test that a single time period preference stays as one constraint.
    "I prefer mornings" should remain as one constraint.
    """
    input_text = "I prefer mornings"
    
    result = await atomization_stage.process(input_text)
    
    assert isinstance(result, list)
    assert len(result) == 1, f"Expected 1 constraint, got {len(result)}: {result}"


@pytest.mark.asyncio
async def test_atomization_has_confidence_scores(atomization_stage):
    """
    Test that atomization results include confidence scores.
    """
    input_text = "I cannot work Sunday"
    
    result = await atomization_stage.process(input_text)
    
    assert isinstance(result, list)
    assert len(result) >= 1
    assert "confidence" in result[0], "Should have confidence score"
    assert 0 <= result[0]["confidence"] <= 1, "Confidence should be between 0 and 1"

