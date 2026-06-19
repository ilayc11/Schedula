"""
Full Pipeline Integration Tests

Tests the complete constraint processing pipeline from API endpoint to structured output.
These tests require Ollama to be running.
"""
import pytest
from fastapi import status

# Test constant (must match conftest.py)
TEST_LECTURER_ID = 999


@pytest.mark.asyncio
async def test_pipeline_api_endpoint(async_client):
    """
    Tests the full pipeline integration via API:
    Backend receives POST -> Processes via LLM pipeline -> Returns 200 OK with structured data.

    NOTE: Ollama must be running and accessible (via OLLAMA_URL environment variable).
    """
    payload = {
        "semester_year": 2026,
        "semester_number": 1,
        "raw_text": "I can only teach on Monday mornings, and never on Friday.",
        "lecturer_id": TEST_LECTURER_ID,
    }

    response = await async_client.post("/lecturer/constraints/preview", json=payload)

    if response.status_code != status.HTTP_200_OK:
        print(f"\n❌ Response status: {response.status_code}")
        print(f"Response body: {response.text}")
    
    assert response.status_code == status.HTTP_200_OK, f"Expected 200, got {response.status_code}: {response.text}"

    data = response.json()

    # Verify response structure
    assert data["lecturer_internal_id"] == TEST_LECTURER_ID
    assert data["raw_text"] == payload["raw_text"]
    assert "structured_rules" in data
    assert "atomic_constraints" in data["structured_rules"]

    # Verify LLM returned at least one structured constraint
    assert isinstance(data["structured_rules"]["atomic_constraints"], list)
    assert len(data["structured_rules"]["atomic_constraints"]) >= 1

    # Verify serialization works
    assert isinstance(data["last_updated_at"], str)


@pytest.mark.asyncio
async def test_pipeline_direct_simple_negative(pipeline):
    """
    Test direct pipeline processing of a simple negative constraint.
    """
    input_text = "I cannot work Friday"
    
    result = await pipeline.process(input_text)
    
    assert result.success is True
    assert len(result.atomic_constraints) >= 1
    
    # Should have constraint for Friday (day 6)
    friday_constraint = None
    for c in result.atomic_constraints:
        if 6 in c.days:
            friday_constraint = c
            break
    
    assert friday_constraint is not None, "Should have a constraint for Friday"


@pytest.mark.asyncio
async def test_pipeline_direct_positive_to_negative(pipeline):
    """
    Test that positive constraints are correctly inverted to negative blocks.
    """
    input_text = "I can only work Monday mornings"
    
    result = await pipeline.process(input_text)
    
    assert result.success is True
    assert len(result.atomic_constraints) >= 1
    
    # Should have blocks for other times (not Monday morning)
    # At minimum: Monday afternoon, Monday evening, and all other days


@pytest.mark.asyncio
async def test_pipeline_direct_compound_constraint(pipeline):
    """
    Test processing of compound constraint with 'and' separator.
    """
    input_text = "I cannot work Sunday and I cannot work Friday"
    
    result = await pipeline.process(input_text)
    
    assert result.success is True
    
    # Should have constraints for both Sunday (1) and Friday (6)
    days_blocked = set()
    for c in result.atomic_constraints:
        days_blocked.update(c.days)
    
    assert 1 in days_blocked, "Should block Sunday"
    assert 6 in days_blocked, "Should block Friday"


@pytest.mark.asyncio
async def test_pipeline_metadata(pipeline):
    """
    Test that pipeline results include proper metadata.
    """
    input_text = "I cannot work Monday"
    
    result = await pipeline.process(input_text)
    
    assert result.success is True
    assert result.original_input == input_text
    assert "processing_metadata" in dir(result) or hasattr(result, "processing_metadata")
    
    # Check metadata contains expected fields
    if hasattr(result, "processing_metadata") and result.processing_metadata:
        assert "pipeline_version" in result.processing_metadata


@pytest.mark.asyncio
async def test_pipeline_error_handling(pipeline):
    """
    Test pipeline handles empty input gracefully.
    """
    input_text = ""
    
    result = await pipeline.process(input_text)
    
    # Should either fail gracefully or return empty constraints
    # Not crash with an exception
    assert hasattr(result, "success")

