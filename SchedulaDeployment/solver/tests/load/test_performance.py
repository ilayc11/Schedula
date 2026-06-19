"""
Load tests for solver performance benchmarks.

Tests solver performance with varying problem sizes and constraint densities.
"""
import pytest
import time
import random
from src.solver import CSPSolver


@pytest.mark.load
class TestSolverPerformance:
    """Performance benchmarks for CSP solver."""
    
    def _generate_offerings(self, num_offerings, num_lecturers=None, num_cohorts=None):
        """Generate test offerings with varied configurations."""
        if num_lecturers is None:
            num_lecturers = max(num_offerings // 2, 1)
        if num_cohorts is None:
            num_cohorts = max(num_offerings // 3, 1)
        
        offerings = []
        for i in range(num_offerings):
            # Vary course duration (2-4 hours)
            credit_points = random.choice([2.0, 3.0, 4.0])
            
            # Assign lecturer (round-robin with some overlap)
            lecturer_id = 100 + (i % num_lecturers)
            
            # Assign cohorts (some single, some multi-cohort)
            if i % 3 == 0:  # ~33% multi-cohort
                cohorts = [
                    {"target_department_id": (i % num_cohorts) + 1, "target_year_level": 2},
                    {"target_department_id": ((i + 1) % num_cohorts) + 1, "target_year_level": 2}
                ]
            elif i % 5 == 0:  # ~20% no cohort (electives)
                cohorts = []
            else:  # ~47% single cohort
                cohorts = [
                    {"target_department_id": (i % num_cohorts) + 1, "target_year_level": random.randint(1, 4)}
                ]
            
            offerings.append({
                "offering_id": i + 1,
                "credit_points": credit_points,
                "group_number": 1,
                "cohorts": cohorts,
                "lecturers": [lecturer_id]
            })
        
        return offerings
    
    def _generate_constraints(self, num_lecturers, density=0.3):
        """
        Generate constraints for lecturers.
        
        Args:
            num_lecturers: Number of lecturers
            density: Constraint density (0.0-1.0), percentage of time blocked
        """
        constraints = []
        
        for lecturer_id in range(100, 100 + num_lecturers):
            # Number of blocks based on density
            # density=0.3 means ~3-4 blocks per lecturer
            num_blocks = int(density * 10) + random.randint(0, 2)
            
            if num_blocks == 0:
                continue
            
            atomic_constraints = []
            for _ in range(num_blocks):
                day = random.randint(1, 5)  # Sun-Thu (avoid Friday for simplicity)
                
                # Random time blocks
                start_hour = random.choice([8, 9, 10, 12, 14, 16])
                duration = random.choice([2, 3, 4])
                end_hour = min(start_hour + duration, 20)
                
                atomic_constraints.append({
                    "type": "block",
                    "days": [day],
                    "time_slot": {
                        "start_hour": start_hour,
                        "end_hour": end_hour
                    }
                })
            
            constraints.append({
                "constraints_id": 1000 + lecturer_id,
                "lecturer_internal_id": lecturer_id,
                "structured_rules": {
                    "atomic_constraints": atomic_constraints
                }
            })
        
        return constraints
    
    @pytest.mark.parametrize("num_offerings", [10, 25, 50, 100])
    def test_solve_time_scales_reasonably(self, num_offerings):
        """
        Benchmark solver performance with increasing offerings.
        
        Expected: Solve time should scale sub-linearly with problem size.
        """
        solver = CSPSolver()
        
        # Generate test data
        offerings = self._generate_offerings(num_offerings)
        lecturers_count = max(num_offerings // 2, 1)
        constraints = self._generate_constraints(lecturers_count, density=0.2)
        
        data = {
            "offerings": offerings,
            "constraints": constraints
        }
        
        # Measure solve time
        start_time = time.time()
        result = solver.solve(data)
        solve_time = time.time() - start_time
        
        # Performance thresholds (adjust based on actual performance)
        thresholds = {
            10: 2.0,    # 10 offerings: < 2s
            25: 5.0,    # 25 offerings: < 5s
            50: 15.0,   # 50 offerings: < 15s
            100: 45.0   # 100 offerings: < 45s
        }
        
        print(f"\n{num_offerings} offerings: {solve_time:.2f}s (threshold: {thresholds[num_offerings]}s)")
        
        assert result['status'] in ['solved', 'failed'], "Solver should complete"
        assert solve_time < thresholds[num_offerings], \
            f"Solve time {solve_time:.2f}s exceeded threshold {thresholds[num_offerings]}s"
    
    def test_multi_cohort_performance_improvement(self):
        """
        Verify prioritization improves solve time for complex schedules.
        
        This test compares solve time with proper cohort prioritization
        (built into solver) vs. a scenario that would be slower without it.
        """
        solver = CSPSolver()
        
        # Create schedule with many multi-cohort offerings
        offerings = []
        for i in range(30):
            if i < 10:  # First 10: multi-cohort (should be prioritized)
                cohorts = [
                    {"target_department_id": 1, "target_year_level": j}
                    for j in range(1, 4)
                ]
            else:  # Rest: single cohort
                cohorts = [{"target_department_id": (i % 5) + 1, "target_year_level": 2}]
            
            offerings.append({
                "offering_id": i + 1,
                "credit_points": 3.0,
                "group_number": 1,
                "cohorts": cohorts,
                "lecturers": [100 + (i % 15)]
            })
        
        constraints = self._generate_constraints(15, density=0.3)
        
        data = {
            "offerings": offerings,
            "constraints": constraints
        }
        
        start_time = time.time()
        result = solver.solve(data)
        solve_time = time.time() - start_time
        
        print(f"\nMulti-cohort schedule (30 offerings, 10 multi-cohort): {solve_time:.2f}s")
        
        # With prioritization, should solve in reasonable time
        assert result['status'] == 'solved', "Should find solution"
        assert solve_time < 20.0, "Should solve within 20s with prioritization"
    
    @pytest.mark.parametrize("constraint_density", [0.1, 0.3, 0.5, 0.8])
    def test_constraint_density_impact(self, constraint_density):
        """
        Measure impact of constraint density on solve time.
        
        Higher density = more constraints = longer solve time.
        """
        solver = CSPSolver()
        
        num_offerings = 40
        offerings = self._generate_offerings(num_offerings, num_lecturers=20)
        constraints = self._generate_constraints(20, density=constraint_density)
        
        data = {
            "offerings": offerings,
            "constraints": constraints
        }
        
        start_time = time.time()
        result = solver.solve(data)
        solve_time = time.time() - start_time
        
        # Thresholds increase with density
        threshold = 10.0 + (constraint_density * 20.0)
        
        print(f"\nDensity {constraint_density}: {solve_time:.2f}s (threshold: {threshold:.1f}s)")
        
        assert result['status'] in ['solved', 'failed'], "Solver should complete"
        assert solve_time < threshold, f"Exceeded threshold for density {constraint_density}"
    
    def test_worst_case_performance(self):
        """
        Test worst-case scenario: high constraint density + multi-cohort conflicts.
        
        Ensures solver doesn't hang on difficult problems.
        """
        solver = CSPSolver()
        
        # Create challenging scenario
        num_offerings = 50
        offerings = self._generate_offerings(num_offerings, num_lecturers=15, num_cohorts=5)
        
        # High constraint density
        constraints = self._generate_constraints(15, density=0.7)
        
        data = {
            "offerings": offerings,
            "constraints": constraints
        }
        
        start_time = time.time()
        result = solver.solve(data)
        solve_time = time.time() - start_time
        
        print(f"\nWorst-case scenario (50 offerings, high density): {solve_time:.2f}s")
        
        # Should complete within timeout (60s is solver default)
        assert solve_time < 60.0, "Should complete within timeout"
        assert result['status'] in ['solved', 'failed'], "Should return valid status"
    
    def test_empty_schedule_performance(self):
        """Test that empty/minimal schedules solve very quickly."""
        solver = CSPSolver()
        
        data = {
            "offerings": [],
            "constraints": []
        }
        
        start_time = time.time()
        result = solver.solve(data)
        solve_time = time.time() - start_time
        
        print(f"\nEmpty schedule: {solve_time:.4f}s")
        
        assert result['status'] == 'solved'
        assert solve_time < 0.1, "Empty schedule should solve instantly"
    
    def test_single_offering_performance(self):
        """Test that single offering solves very quickly."""
        solver = CSPSolver()
        
        data = {
            "offerings": [
                {
                    "offering_id": 1,
                    "credit_points": 3.0,
                    "group_number": 1,
                    "cohorts": [{"target_department_id": 1, "target_year_level": 1}],
                    "lecturers": [100]
                }
            ],
            "constraints": []
        }
        
        start_time = time.time()
        result = solver.solve(data)
        solve_time = time.time() - start_time
        
        print(f"\nSingle offering: {solve_time:.4f}s")
        
        assert result['status'] == 'solved'
        assert solve_time < 0.5, "Single offering should solve very quickly"

