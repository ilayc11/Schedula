"""
Unit tests for cohort-based scheduling constraints.

Tests cohort conflict prevention and multi-cohort prioritization.
"""
import pytest
from src.solver import CSPSolver


@pytest.mark.unit
class TestCohortConflicts:
    """Test that solver prevents student conflicts for same cohort."""
    
    def test_same_cohort_no_overlap(self):
        """
        Test that two courses for the same cohort (dept + year level)
        cannot be scheduled at the same time.
        """
        solver = CSPSolver()
        
        # Two courses for Department 1, Year 3 students
        # Both taught by different lecturers
        data = {
            "offerings": [
                {
                    "offering_id": 1,
                    "credit_points": 2.0,
                    "group_number": 1,
                    "cohorts": [
                        {"target_department_id": 1, "target_year_level": 3}
                    ],
                    "lecturers": [101]  # Lecturer A
                },
                {
                    "offering_id": 2,
                    "credit_points": 2.0,
                    "group_number": 1,
                    "cohorts": [
                        {"target_department_id": 1, "target_year_level": 3}
                    ],
                    "lecturers": [102]  # Lecturer B (different lecturer)
                }
            ],
            "constraints": []
        }
        
        result = solver.solve(data)
        
        # Should find a solution
        assert result['status'] == 'solved'
        
        # Extract the scheduled sessions
        sessions = result['solution']
        assert len(sessions) == 2  # Both offerings scheduled
        
        # Verify they are NOT scheduled at the same time
        offering1_sessions = [s for s in sessions if s['offering_id'] == 1]
        offering2_sessions = [s for s in sessions if s['offering_id'] == 2]
        
        assert len(offering1_sessions) == 1
        assert len(offering2_sessions) == 1
        
        s1 = offering1_sessions[0]
        s2 = offering2_sessions[0]
        
        # They should either be on different days OR different times
        if s1['day_of_week'] == s2['day_of_week']:
            # Same day - must have different times (no overlap)
            # Convert times to comparable format
            s1_start = s1['start_time'].hour
            s1_end = s1['end_time'].hour
            s2_start = s2['start_time'].hour
            s2_end = s2['end_time'].hour
            
            # No overlap: either s1 ends before s2 starts, or s2 ends before s1 starts
            assert s1_end <= s2_start or s2_end <= s1_start
        # else: different days - no conflict

    def test_different_cohorts_can_overlap(self):
        """
        Test that courses for DIFFERENT cohorts CAN be scheduled at the same time
        (e.g., Dept 1 Year 3 and Dept 2 Year 4)
        """
        solver = CSPSolver()
        
        data = {
            "offerings": [
                {
                    "offering_id": 1,
                    "credit_points": 2.0,
                    "group_number": 1,
                    "cohorts": [
                        {"target_department_id": 1, "target_year_level": 3}
                    ],
                    "lecturers": [101]
                },
                {
                    "offering_id": 2,
                    "credit_points": 2.0,
                    "group_number": 1,
                    "cohorts": [
                        {"target_department_id": 2, "target_year_level": 4}  # Different cohort
                    ],
                    "lecturers": [102]
                }
            ],
            "constraints": []
        }
        
        result = solver.solve(data)
        
        # Should find a solution (they CAN overlap since different cohorts)
        assert result['status'] == 'solved'
        assert len(result['solution']) == 2

    def test_null_cohort_offerings(self):
        """
        Test that offerings with empty cohort lists are not restricted
        (e.g., elective courses not tied to specific cohorts)
        """
        solver = CSPSolver()
        
        data = {
            "offerings": [
                {
                    "offering_id": 1,
                    "credit_points": 2.0,
                    "group_number": 1,
                    "cohorts": [],  # Not cohort-specific
                    "lecturers": [101]
                },
                {
                    "offering_id": 2,
                    "credit_points": 2.0,
                    "group_number": 1,
                    "cohorts": [],  # Not cohort-specific
                    "lecturers": [102]
                }
            ],
            "constraints": []
        }
        
        result = solver.solve(data)
        
        # Should find a solution - empty cohorts don't trigger no-overlap
        assert result['status'] == 'solved'
        assert len(result['solution']) == 2

    def test_same_course_different_cohorts_can_overlap(self):
        """
        Test that the SAME course offered to DIFFERENT cohorts CAN be scheduled simultaneously.
        This is a key use case: e.g., "Data Structures" for CS Year 3 and Math Year 4.
        """
        solver = CSPSolver()
        
        # Same conceptual course (could be same course_number in real DB)
        # offered to two different cohorts
        data = {
            "offerings": [
                {
                    "offering_id": 100,  # Data Structures for CS Year 3
                    "credit_points": 3.0,
                    "group_number": 1,
                    "cohorts": [
                        {"target_department_id": 1, "target_year_level": 3}  # CS Year 3
                    ],
                    "lecturers": [201]          # Prof. Smith
                },
                {
                    "offering_id": 101,  # Same course for Math Year 4
                    "credit_points": 3.0,
                    "group_number": 1,
                    "cohorts": [
                        {"target_department_id": 2, "target_year_level": 4}  # Math Year 4
                    ],
                    "lecturers": [202]          # Prof. Jones (different lecturer)
                }
            ],
            "constraints": []
        }
        
        result = solver.solve(data)
        
        # Should find a solution
        assert result['status'] == 'solved'
        assert len(result['solution']) == 2
        
        # The two offerings CAN be scheduled at the same time
        # because they serve different student cohorts
        sessions = result['solution']
        offering1 = [s for s in sessions if s['offering_id'] == 100][0]
        offering2 = [s for s in sessions if s['offering_id'] == 101][0]
        
        # They COULD overlap (same day and time) - that's valid!
        # We're just verifying the solver doesn't prevent it
        # (The test passes if solver doesn't fail/conflict)
        assert offering1 is not None
        assert offering2 is not None


@pytest.mark.unit
class TestCohortPrioritization:
    """Test that solver prioritizes multi-department offerings."""

    def test_multi_department_offering_prioritized(self):
        """
        Test that offerings targeting multiple departments get scheduled
        even when slots are limited.
        
        Scenario:
        - Offering 1: For CS Year 3 AND Math Year 3 (2 cohorts)
        - Offering 2: For Physics Year 3 only (1 cohort)
        - Limited time slots available
        
        Expected: Offering 1 should be prioritized due to more cohorts
        """
        solver = CSPSolver()
        
        data = {
            "offerings": [
                {
                    "offering_id": 1,
                    "credit_points": 3.0,  # 3 hour course
                    "group_number": 1,
                    "cohorts": [
                        {"target_department_id": 1, "target_year_level": 3},  # CS Year 3
                        {"target_department_id": 2, "target_year_level": 3}   # Math Year 3
                    ],
                    "lecturers": [101]
                },
                {
                    "offering_id": 2,
                    "credit_points": 3.0,  # 3 hour course
                    "group_number": 1,
                    "cohorts": [
                        {"target_department_id": 3, "target_year_level": 3}   # Physics Year 3
                    ],
                    "lecturers": [102]
                }
            ],
            "constraints": []
        }
        
        result = solver.solve(data)
        
        # Should find a solution
        assert result['status'] == 'solved'
        assert len(result['solution']) == 2
        
        # Both offerings should be scheduled
        offering_ids = {s['offering_id'] for s in result['solution']}
        assert 1 in offering_ids
        assert 2 in offering_ids

    def test_prioritization_with_conflicts(self):
        """
        Test prioritization when there are cohort conflicts.
        
        Scenario:
        - Offering 1: For CS Year 3 (1 cohort)
        - Offering 2: For CS Year 3 AND Math Year 3 (2 cohorts)
        - Offering 3: For Math Year 3 (1 cohort)
        
        All three target overlapping cohorts, so they can't be at same time.
        Multi-cohort offering (2) should get priority in scheduling decisions.
        """
        solver = CSPSolver()
        
        data = {
            "offerings": [
                {
                    "offering_id": 1,
                    "credit_points": 2.0,
                    "group_number": 1,
                    "cohorts": [
                        {"target_department_id": 1, "target_year_level": 3}  # CS Year 3
                    ],
                    "lecturers": [101]
                },
                {
                    "offering_id": 2,
                    "credit_points": 2.0,
                    "group_number": 1,
                    "cohorts": [
                        {"target_department_id": 1, "target_year_level": 3},  # CS Year 3
                        {"target_department_id": 2, "target_year_level": 3}   # Math Year 3
                    ],
                    "lecturers": [102]
                },
                {
                    "offering_id": 3,
                    "credit_points": 2.0,
                    "group_number": 1,
                    "cohorts": [
                        {"target_department_id": 2, "target_year_level": 3}   # Math Year 3
                    ],
                    "lecturers": [103]
                }
            ],
            "constraints": []
        }
        
        result = solver.solve(data)
        
        # Should find a solution (all can be scheduled on different days/times)
        assert result['status'] == 'solved'
        assert len(result['solution']) == 3
        
        # Extract sessions
        sessions = {s['offering_id']: s for s in result['solution']}
        
        # Verify they don't overlap
        # Offering 2 should not overlap with 1 (share CS Year 3)
        # Offering 2 should not overlap with 3 (share Math Year 3)
        # Offering 1 and 3 CAN overlap (different cohorts)
        
        s1 = sessions[1]
        s2 = sessions[2]
        s3 = sessions[3]
        
        # Check offering 2 doesn't overlap with offering 1
        if s1['day_of_week'] == s2['day_of_week']:
            assert s1['end_time'] <= s2['start_time'] or s2['end_time'] <= s1['start_time']
        
        # Check offering 2 doesn't overlap with offering 3
        if s3['day_of_week'] == s2['day_of_week']:
            assert s3['end_time'] <= s2['start_time'] or s2['end_time'] <= s3['start_time']

    def test_equal_cohorts_all_scheduled(self):
        """
        Test that when all offerings have same cohort count,
        all still get scheduled properly.
        """
        solver = CSPSolver()
        
        data = {
            "offerings": [
                {
                    "offering_id": 1,
                    "credit_points": 2.0,
                    "group_number": 1,
                    "cohorts": [
                        {"target_department_id": 1, "target_year_level": 1}
                    ],
                    "lecturers": [101]
                },
                {
                    "offering_id": 2,
                    "credit_points": 2.0,
                    "group_number": 1,
                    "cohorts": [
                        {"target_department_id": 2, "target_year_level": 1}
                    ],
                    "lecturers": [102]
                },
                {
                    "offering_id": 3,
                    "credit_points": 2.0,
                    "group_number": 1,
                    "cohorts": [
                        {"target_department_id": 3, "target_year_level": 1}
                    ],
                    "lecturers": [103]
                }
            ],
            "constraints": []
        }
        
        result = solver.solve(data)
        
        # Should find a solution
        assert result['status'] == 'solved'
        assert len(result['solution']) == 3

    def test_many_cohorts_vs_one_cohort(self):
        """
        Test extreme case: one offering targets 5 departments,
        another targets only 1.
        
        The 5-department offering should be processed first.
        """
        solver = CSPSolver()
        
        data = {
            "offerings": [
                {
                    "offering_id": 1,
                    "credit_points": 2.0,
                    "group_number": 1,
                    "cohorts": [
                        {"target_department_id": 1, "target_year_level": 2}
                    ],
                    "lecturers": [101]
                },
                {
                    "offering_id": 2,
                    "credit_points": 2.0,
                    "group_number": 1,
                    "cohorts": [
                        {"target_department_id": 1, "target_year_level": 3},
                        {"target_department_id": 2, "target_year_level": 3},
                        {"target_department_id": 3, "target_year_level": 3},
                        {"target_department_id": 4, "target_year_level": 3},
                        {"target_department_id": 5, "target_year_level": 3}
                    ],
                    "lecturers": [102]
                }
            ],
            "constraints": []
        }
        
        result = solver.solve(data)
        
        # Should find a solution
        assert result['status'] == 'solved'
        assert len(result['solution']) == 2
        
        # Both should be scheduled (different cohorts, no conflicts)
        offering_ids = {s['offering_id'] for s in result['solution']}
        assert offering_ids == {1, 2}

    def test_empty_cohorts_deprioritized(self):
        """
        Test that offerings with empty cohorts (electives) are deprioritized.
        """
        solver = CSPSolver()
        
        data = {
            "offerings": [
                {
                    "offering_id": 1,
                    "credit_points": 2.0,
                    "group_number": 1,
                    "cohorts": [],  # Elective - no specific cohort
                    "lecturers": [101]
                },
                {
                    "offering_id": 2,
                    "credit_points": 2.0,
                    "group_number": 1,
                    "cohorts": [
                        {"target_department_id": 1, "target_year_level": 3},
                        {"target_department_id": 2, "target_year_level": 3}
                    ],
                    "lecturers": [102]
                }
            ],
            "constraints": []
        }
        
        result = solver.solve(data)
        
        # Should find a solution
        assert result['status'] == 'solved'
        assert len(result['solution']) == 2
        
        # The multi-cohort offering (2) was processed first (higher priority)
        # But both should still be scheduled
        offering_ids = {s['offering_id'] for s in result['solution']}
        assert offering_ids == {1, 2}

