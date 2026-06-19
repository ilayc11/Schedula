"""
Tests for the Classification Stage (Stage 2)

The classification stage determines polarity (POSITIVE/NEGATIVE) and priority (hard/soft).
"""
import pytest


@pytest.mark.asyncio
async def test_classification_negative_cannot(classification_stage):
    """
    Test that 'cannot' constraints are classified as NEGATIVE with hard priority.
    """
    constraint_text = "I cannot work Tuesday afternoons"
    
    result = await classification_stage.process(constraint_text)
    
    assert result["polarity"] == "NEGATIVE"
    assert result["priority"] == "hard"
    assert "confidence" in result


@pytest.mark.asyncio
async def test_classification_positive_only(classification_stage):
    """
    Test that 'only' constraints are classified as POSITIVE with hard priority.
    """
    constraint_text = "I can only work Monday mornings"
    
    result = await classification_stage.process(constraint_text)
    
    assert result["polarity"] == "POSITIVE"
    assert result["priority"] == "hard", "'only' should always be hard priority"


@pytest.mark.asyncio
async def test_classification_soft_prefer(classification_stage):
    """
    Test that 'prefer' constraints are classified as POSITIVE with soft priority.
    """
    constraint_text = "I prefer mornings"
    
    result = await classification_stage.process(constraint_text)
    
    assert result["polarity"] == "POSITIVE"
    assert result["priority"] == "soft", "'prefer' should be soft priority"


@pytest.mark.asyncio
async def test_classification_negative_unavailable(classification_stage):
    """
    Test that 'unavailable' constraints are classified as NEGATIVE with hard priority.
    """
    constraint_text = "I am unavailable on Wednesday"
    
    result = await classification_stage.process(constraint_text)
    
    assert result["polarity"] == "NEGATIVE"
    assert result["priority"] == "hard"


@pytest.mark.asyncio
async def test_classification_negative_busy(classification_stage):
    """
    Test that 'busy' constraints are classified as NEGATIVE with hard priority.
    """
    constraint_text = "I'm busy Friday mornings"
    
    result = await classification_stage.process(constraint_text)
    
    assert result["polarity"] == "NEGATIVE"
    assert result["priority"] == "hard"


@pytest.mark.asyncio
async def test_classification_has_reasoning(classification_stage):
    """
    Test that classification results include reasoning.
    """
    constraint_text = "I cannot work Sunday"
    
    result = await classification_stage.process(constraint_text)
    
    assert "reasoning" in result
    assert len(result["reasoning"]) > 0

