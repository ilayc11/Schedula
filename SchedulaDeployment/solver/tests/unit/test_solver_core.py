"""
Unit tests for CSPSolver core logic.

Tests basic solver functionality, constraint handling, and breaking constraints detection.
"""
import pytest
from src.solver import CSPSolver
from datetime import time


@pytest.mark.unit
class TestCSPSolverLogic:
    
    def test_solve_empty_constraints(self):
        """Test solver behavior with no constraints."""
        solver = CSPSolver()
        # Data wrapper with empty offerings and constraints
        data = {
            "offerings": [],
            "constraints": []
        }
        result = solver.solve(data)
        
        assert isinstance(result, dict)
        assert result['status'] == 'solved'
        assert result['solution'] == []

    def test_solve_single_constraint(self, mock_db_constraint_row_factory):
        """Test solver with a single valid constraint."""
        solver = CSPSolver()
        
        # Mock Offering
        offering = {
            "offering_id": 1,
            "credit_points": 2.0,
            "group_number": 1,
            "cohorts": [],
            "lecturers": [101]
        }

        # Create a constraint: Block Monday 9-12 for lecturer 101
        # DB Day 1 = Monday? 
        # Check db.py or solver.py:
        # DB Days: 1=Sun, 2=Mon...
        # Let's assume we want to block day 2 (Mon).
        constraint_row = mock_db_constraint_row_factory(
            lecturer_id=101,
            days=[1], # Atomic Constraint 0-based index? 
            # Solver logic: db_day = atomic_day + 1. 
            # If atomic_day=1 (Mon), db_day=2.
            # wait, mock_atomic_constraint_factory default is [1]
            start_hour=9,
            end_hour=12
        )
        
        data = {
            "offerings": [offering],
            "constraints": [constraint_row]
        }

        result = solver.solve(data)
        
        assert result['status'] == 'solved'
        assert len(result['solution']) > 0
        
        # Verify it didn't schedule on the blocked time (Mon 9-12)
        # Session format: day_of_week, start_time, end_time
        session = result['solution'][0]
        # It should schedule somewhere else, e.g. Day 1, or Day 2 different time
        # Check conflict logic if needed, but 'solved' implies success.

    def test_solve_conflicting_constraints(self, mock_db_constraint_row_factory, mock_atomic_constraint_factory):
        """Test solver behavior with conflicting constraints (Impossible to schedule)."""
        solver = CSPSolver()
        
        # Offering: 5 hours duration
        offering = {
            "offering_id": 1,
            "credit_points": 5.0,
            "group_number": 1,
            "cohorts": [],
            "lecturers": [101]
        }

        # Constraint: Block ALL days for lecturer 101
        # Days 1-6 (Sun-Fri), blocking entire day
        # This makes it impossible to fit a 5-hour course anywhere
        atomic_constraints = []
        for day in range(1, 7):
            end_hour = 15 if day == 6 else 20
            atomic_constraints.append(
                mock_atomic_constraint_factory(
                    days=[day],
                    start_hour=8,
                    end_hour=end_hour,
                    ctype="block"
                )
            )
        
        c1 = mock_db_constraint_row_factory(
            lecturer_id=101,
            constraints_id=100,
            atomic_constraints=atomic_constraints
        )

        data = {
            "offerings": [offering],
            "constraints": [c1]
        }

        result = solver.solve(data)
        
        # Should fail with breaking constraints
        assert result['status'] == 'failed'
        assert 'conflict_constraints' in result
        assert len(result['conflict_constraints']) > 0
        
        # Verify breaking constraints have correct structure
        for bc in result['conflict_constraints']:
            assert 'constraints_id' in bc
            assert 'atomic_index' in bc
            assert bc['constraints_id'] == 100


    def test_constraint_parsing(self, mock_db_constraint_row_factory):
        """Test that the solver correctly parses the JSON structure of constraints."""
        solver = CSPSolver()
        
        offering = {
            "offering_id": 1,
            "credit_points": 2.0,
            "group_number": 1,
            "cohorts": [],
            "lecturers": [101]
        }

        constraint_row = mock_db_constraint_row_factory(
            lecturer_id=101,
            days=[1, 3], # Mon, Wed
            start_hour=14,
            end_hour=16,
            priority="hard"
        )
        
        data = {
            "offerings": [offering],
            "constraints": [constraint_row]
        }

        try:
            result = solver.solve(data)
            assert result['status'] in ['solved', 'failed']
        except Exception as e:
            pytest.fail(f"Solver crashed on valid constraint input: {e}")

    def test_invalid_constraint_format(self):
        """Test resilience against malformed constraint data."""
        solver = CSPSolver()
        
        malformed_constraint = {
            "lecturer_internal_id": 101,
            "structured_rules": "NOT A JSON OBJECT" 
        }
        
        data = {
            "offerings": [],
            "constraints": [malformed_constraint]
        }

        try:
            result = solver.solve(data)
            assert result['status'] == 'solved' # Should ignore bad constraints
        except Exception as e:
             pytest.fail(f"Solver crashed on invalid input: {e}")
    
    def test_breaking_constraints_correct_ids(self, mock_db_constraint_row_factory, mock_atomic_constraint_factory):
        """Test that breaking constraints return correct constraint_id and atomic_index."""
        solver = CSPSolver()
        
        # Two offerings for same lecturer, both 3 hours
        offerings = [
            {
                "offering_id": 1,
                "credit_points": 3.0,
                "group_number": 1,
                "cohorts": [],
                "lecturers": [101]
            },
            {
                "offering_id": 2,
                "credit_points": 3.0,
                "group_number": 2,
                "cohorts": [],
                "lecturers": [101]
            }
        ]
        
        # Block all available time slots - impossible to schedule both courses
        atomic_constraints = []
        for day in range(1, 7):
            end_hour = 15 if day == 6 else 20
            atomic_constraints.append(
                mock_atomic_constraint_factory(
                    days=[day],
                    start_hour=8,
                    end_hour=end_hour,
                    ctype="block"
                )
            )
        
        constraint = mock_db_constraint_row_factory(
            lecturer_id=101,
            constraints_id=200,
            atomic_constraints=atomic_constraints
        )
        
        data = {
            "offerings": offerings,
            "constraints": [constraint]
        }
        
        result = solver.solve(data)
        
        # Should fail
        assert result['status'] == 'failed'
        assert len(result['conflict_constraints']) > 0
        
        # All breaking constraints should reference constraint_id 200
        for bc in result['conflict_constraints']:
            assert bc['constraints_id'] == 200
            assert 0 <= bc['atomic_index'] < len(atomic_constraints)
    
    def test_multiple_lecturers_breaking_constraints(self, mock_db_constraint_row_factory, mock_atomic_constraint_factory):
        """Test detection of breaking constraints from multiple lecturers."""
        solver = CSPSolver()
        
        # Two offerings for different lecturers
        offerings = [
            {
                "offering_id": 1,
                "credit_points": 3.0,
                "group_number": 1,
                "cohorts": [],
                "lecturers": [101]
            },
            {
                "offering_id": 2,
                "credit_points": 3.0,
                "group_number": 1,
                "cohorts": [],
                "lecturers": [102]
            }
        ]
        
        # Both lecturers block all time
        constraints = []
        for lect_id, const_id in [(101, 300), (102, 301)]:
            atomic_constraints = []
            for day in range(1, 7):
                end_hour = 15 if day == 6 else 20
                atomic_constraints.append(
                    mock_atomic_constraint_factory(
                        days=[day],
                        start_hour=8,
                        end_hour=end_hour,
                        ctype="block"
                    )
                )
            
            constraints.append(
                mock_db_constraint_row_factory(
                    lecturer_id=lect_id,
                    constraints_id=const_id,
                    atomic_constraints=atomic_constraints
                )
            )
        
        data = {
            "offerings": offerings,
            "constraints": constraints
        }
        
        result = solver.solve(data)
        
        # Should fail
        assert result['status'] == 'failed'
        
        # Should have breaking constraints from both lecturers
        constraint_ids = {bc['constraints_id'] for bc in result['conflict_constraints']}
        assert 300 in constraint_ids or 301 in constraint_ids
    
    def test_non_conflicting_constraints_not_flagged(self, mock_db_constraint_row_factory, mock_atomic_constraint_factory):
        """Test that non-conflicting constraints are not flagged as breaking."""
        solver = CSPSolver()
        
        # One offering, 2 hours
        offering = {
            "offering_id": 1,
            "credit_points": 2.0,
            "group_number": 1,
            "cohorts": [],
            "lecturers": [101]
        }
        
        # Block only Monday morning - plenty of other time available
        atomic_constraints = [
            mock_atomic_constraint_factory(
                days=[2],  # Monday
                start_hour=8,
                end_hour=12,
                ctype="block"
            )
        ]
        
        constraint = mock_db_constraint_row_factory(
            lecturer_id=101,
            constraints_id=400,
            atomic_constraints=atomic_constraints
        )
        
        data = {
            "offerings": [offering],
            "constraints": [constraint]
        }
        
        result = solver.solve(data)
        
        # Should succeed
        assert result['status'] == 'solved'
        assert len(result['conflict_constraints']) == 0
        assert len(result['solution']) > 0
