"""
Tests for the Negation Stage (Stage 3)

The negation stage converts positive constraints to negative blocks.
For example: "I can only work Monday mornings" becomes blocks for all other times.
"""
import pytest


@pytest.mark.asyncio
async def test_negation_only_day_time(negation_stage):
    """
    Test that 'only Monday mornings' creates blocks for other times and days.
    """
    constraint_text = "I can only work Monday mornings"
    priority = "hard"
    
    result = await negation_stage.process(constraint_text, priority)
    
    assert "inverted_constraints" in result
    inverted = result["inverted_constraints"]
    
    # Should have multiple inverted constraints:
    # - Monday afternoon, Monday evening (blocking other times same day)
    # - All other days (Sunday, Tuesday, Wednesday, Thursday, Friday)
    assert len(inverted) >= 5, f"Expected at least 5 inverted constraints, got {len(inverted)}"
    
    # All should have the same priority
    for c in inverted:
        assert c["priority"] == "hard", f"Priority should be hard, got {c['priority']}"


@pytest.mark.asyncio
async def test_negation_preserves_hard_priority(negation_stage):
    """
    Test that hard priority is preserved in all inverted constraints.
    """
    constraint_text = "I can only work Wednesday"
    priority = "hard"
    
    result = await negation_stage.process(constraint_text, priority)
    
    for c in result["inverted_constraints"]:
        assert c["priority"] == "hard"


@pytest.mark.asyncio
async def test_negation_preserves_soft_priority(negation_stage):
    """
    Test that soft priority is preserved in all inverted constraints.
    """
    constraint_text = "I prefer mornings"
    priority = "soft"
    
    result = await negation_stage.process(constraint_text, priority)
    
    for c in result["inverted_constraints"]:
        assert c["priority"] == "soft"


@pytest.mark.asyncio
async def test_negation_specific_time_slot(negation_stage):
    """
    Test negation with a specific time slot creates appropriate blocks.
    """
    constraint_text = "I can only work Wednesday 10:00-14:00"
    priority = "hard"
    
    result = await negation_stage.process(constraint_text, priority)
    
    inverted = result["inverted_constraints"]
    texts = [c["text"].lower() for c in inverted]
    
    # Should block other times on Wednesday and all other days
    assert any("wednesday" in t and ("08" in t or "14" in t or "morning" in t or "evening" in t) for t in texts) or \
           len([t for t in texts if "wednesday" not in t]) >= 5, \
           "Should have blocks for other times on Wednesday or all other days"


@pytest.mark.asyncio
async def test_negation_has_summary(negation_stage):
    """
    Test that negation results include an inversion summary.
    """
    constraint_text = "I can only work Monday"
    priority = "hard"
    
    result = await negation_stage.process(constraint_text, priority)
    
    assert "inversion_summary" in result
    assert len(result["inversion_summary"]) > 0


@pytest.mark.asyncio
async def test_negation_no_duplicates(negation_stage):
    """
    Test that negation doesn't produce duplicate constraints.
    """
    constraint_text = "I can only work Monday mornings"
    priority = "hard"
    
    result = await negation_stage.process(constraint_text, priority)
    
    texts = [c["text"] for c in result["inverted_constraints"]]
    unique_texts = set(texts)
    
    assert len(texts) == len(unique_texts), f"Found duplicates: {texts}"

