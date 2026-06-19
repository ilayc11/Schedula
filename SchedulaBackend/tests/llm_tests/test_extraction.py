"""
Tests for the Extraction Stage (Stage 4)

The extraction stage extracts days (as integers 1-6) and time slots from constraint text.
"""
import pytest


@pytest.mark.asyncio
async def test_extraction_single_day(extraction_stage):
    """
    Test extraction of a single day constraint.
    Sunday = 1
    """
    constraint_text = "I cannot work Sunday"
    
    result = await extraction_stage.process(constraint_text)
    
    assert result["days"] == [1], f"Sunday should be 1, got {result['days']}"
    assert result["time_slot"] is None


@pytest.mark.asyncio
async def test_extraction_monday_is_2(extraction_stage):
    """
    Test that Monday is correctly mapped to 2.
    """
    constraint_text = "I cannot work Monday"
    
    result = await extraction_stage.process(constraint_text)
    
    assert result["days"] == [2], f"Monday should be 2, got {result['days']}"


@pytest.mark.asyncio
async def test_extraction_thursday_is_5(extraction_stage):
    """
    Test that Thursday is correctly mapped to 5.
    """
    constraint_text = "I cannot work Thursday"
    
    result = await extraction_stage.process(constraint_text)
    
    assert result["days"] == [5], f"Thursday should be 5, got {result['days']}"


@pytest.mark.asyncio
async def test_extraction_friday_is_6(extraction_stage):
    """
    Test that Friday is correctly mapped to 6.
    Note: This test may occasionally fail with certain LLM providers due to
    interpretation issues (e.g., extracting "all days except Friday" instead of "only Friday").
    """
    constraint_text = "I cannot work Friday"
    
    result = await extraction_stage.process(constraint_text)
    
    # Accept either [6] or occasionally LLMs might return all other days
    # Ideally should be [6], but some LLMs misinterpret
    assert result["days"] == [6], f"Friday should be 6, got {result['days']}"


@pytest.mark.asyncio
async def test_extraction_morning_time_slot(extraction_stage):
    """
    Test that 'morning' extracts to 08:00-12:00.
    """
    constraint_text = "I cannot work Monday mornings"
    
    result = await extraction_stage.process(constraint_text)
    
    assert result["days"] == [2]
    assert result["time_slot"] is not None
    assert result["time_slot"].start_hour == 8
    assert result["time_slot"].end_hour == 12


@pytest.mark.asyncio
async def test_extraction_afternoon_time_slot(extraction_stage):
    """
    Test that 'afternoon' extracts to 13:00-16:00 (not 15:00).
    """
    constraint_text = "I cannot work Tuesday afternoons"
    
    result = await extraction_stage.process(constraint_text)
    
    assert result["days"] == [3]
    assert result["time_slot"] is not None
    assert result["time_slot"].start_hour == 13
    assert result["time_slot"].end_hour == 16, "Afternoon should end at 16:00 (not 15:00 except Friday)"


@pytest.mark.asyncio
async def test_extraction_friday_afternoon_ends_at_15(extraction_stage):
    """
    Test that Friday afternoon ends at 15:00 (special case).
    """
    constraint_text = "I cannot work Friday afternoons"
    
    result = await extraction_stage.process(constraint_text)
    
    assert result["days"] == [6]
    assert result["time_slot"] is not None
    assert result["time_slot"].start_hour == 13
    assert result["time_slot"].end_hour == 15, "Friday afternoon should end at 15:00"


@pytest.mark.asyncio
async def test_extraction_specific_time_range(extraction_stage):
    """
    Test extraction of a specific time range.
    """
    constraint_text = "I cannot work Sunday 14:00-16:00"
    
    result = await extraction_stage.process(constraint_text)
    
    assert result["days"] == [1]
    assert result["time_slot"] is not None
    assert result["time_slot"].start_hour == 14
    assert result["time_slot"].end_hour == 16


@pytest.mark.asyncio
async def test_extraction_all_days_when_no_day_specified(extraction_stage):
    """
    Test that constraints without specific days apply to all days.
    """
    constraint_text = "I cannot work afternoons"
    
    result = await extraction_stage.process(constraint_text)
    
    # Should apply to all working days (1-6)
    assert len(result["days"]) == 6, f"Expected all 6 days, got {result['days']}"
    assert set(result["days"]) == {1, 2, 3, 4, 5, 6}


@pytest.mark.asyncio
async def test_extraction_has_confidence(extraction_stage):
    """
    Test that extraction results include confidence scores.
    """
    constraint_text = "I cannot work Monday"
    
    result = await extraction_stage.process(constraint_text)
    
    assert "confidence" in result
    assert 0 <= result["confidence"] <= 1

