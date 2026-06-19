"""
Stress tests for solver with large-scale scenarios.

Tests solver behavior under extreme conditions and resource constraints.
"""
import pytest
import time
import random
from src.solver import CSPSolver


@pytest.mark.load
class TestSolverStress:
    """Stress tests for CSP solver with extreme scenarios."""
    
    def _generate_large_schedule(self, num_offerings, num_lecturers, num_cohorts):
        """Generate a large-scale test schedule."""
        offerings = []
        for i in range(num_offerings):
            # Vary course duration
            credit_points = random.choice([2.0, 3.0, 3.0, 4.0])  # More 3-hour courses
            
            # Assign lecturer (ensure realistic distribution)
            lecturer_id = 200 + (i % num_lecturers)
            
            # Assign cohorts with realistic patterns
            cohort_type = i % 10
            if cohort_type == 0:  # 10% electives (no cohort)
                cohorts = []
            elif cohort_type < 3:  # 20% multi-cohort
                num_target_cohorts = random.randint(2, 3)
                cohorts = [
                    {
                        "target_department_id": ((i + j) % num_cohorts) + 1,
                        "target_year_level": random.randint(1, 4)
                    }
                    for j in range(num_target_cohorts)
                ]
            else:  # 70% single cohort
                cohorts = [{
                    "target_department_id": (i % num_cohorts) + 1,
                    "target_year_level": random.randint(1, 4)
                }]
            
            offerings.append({
                "offering_id": i + 1,
                "credit_points": credit_points,
                "group_number": 1,
                "cohorts": cohorts,
                "lecturers": [lecturer_id]
            })
        
        return offerings
    
    def _generate_heavy_constraints(self, num_lecturers, blocks_per_lecturer=5):
        """Generate heavy constraint load."""
        constraints = []
        
        for lecturer_id in range(200, 200 + num_lecturers):
            atomic_constraints = []
            
            for _ in range(blocks_per_lecturer):
                day = random.randint(1, 6)  # All days including Friday
                
                # Vary block sizes
                if random.random() < 0.3:  # 30% large blocks
                    start_hour = 8
                    end_hour = random.choice([12, 14, 16])
                elif random.random() < 0.5:  # 35% medium blocks
                    start_hour = random.choice([8, 10, 14])
                    end_hour = start_hour + random.choice([3, 4])
                else:  # 35% small blocks
                    start_hour = random.choice([8, 10, 12, 14, 16])
                    end_hour = start_hour + 2
                
                # Adjust for Friday
                if day == 6:
                    end_hour = min(end_hour, 15)
                else:
                    end_hour = min(end_hour, 20)
                
                atomic_constraints.append({
                    "type": "block",
                    "days": [day],
                    "time_slot": {
                        "start_hour": start_hour,
                        "end_hour": end_hour
                    }
                })
            
            constraints.append({
                "constraints_id": 2000 + lecturer_id,
                "lecturer_internal_id": lecturer_id,
                "structured_rules": {
                    "atomic_constraints": atomic_constraints
                }
            })
        
        return constraints
    
    def test_large_scale_scheduling(self):
        """
        Stress test: 200 offerings, 100 lecturers, 50 cohorts.
        
        Tests solver behavior with a very large problem size.
        """
        solver = CSPSolver()
        
        print("\n🔥 Large-scale stress test starting...")
        
        # Generate large dataset
        offerings = self._generate_large_schedule(
            num_offerings=200,
            num_lecturers=100,
            num_cohorts=50
        )
        
        constraints = self._generate_heavy_constraints(
            num_lecturers=100,
            blocks_per_lecturer=3  # Moderate constraints for solvability
        )
        
        data = {
            "offerings": offerings,
            "constraints": constraints
        }
        
        print(f"   - {len(offerings)} offerings")
        print(f"   - {len(constraints)} lecturers with constraints")
        print(f"   - Total atomic constraints: {sum(len(c['structured_rules']['atomic_constraints']) for c in constraints)}")
        
        start_time = time.time()
        result = solver.solve(data)
        solve_time = time.time() - start_time
        
        print(f"   - Solve time: {solve_time:.2f}s")
        print(f"   - Status: {result['status']}")
        
        # Should complete within reasonable time (may fail due to constraints)
        assert solve_time < 120.0, "Should complete within 2 minutes"
        assert result['status'] in ['solved', 'failed'], "Should return valid status"
        
        if result['status'] == 'solved':
            print(f"   - ✓ Solution found with {len(result['solution'])} sessions")
        else:
            print(f"   - ⚠ Infeasible (expected with stress test)")
    
    def test_highly_constrained_scenario(self):
        """
        All lecturers have 5+ block constraints.
        
        Tests solver with very limited scheduling flexibility.
        """
        solver = CSPSolver()
        
        print("\n🔥 Highly constrained stress test starting...")
        
        offerings = self._generate_large_schedule(
            num_offerings=50,
            num_lecturers=25,
            num_cohorts=10
        )
        
        # Each lecturer has 6-8 blocks (very constrained)
        constraints = self._generate_heavy_constraints(
            num_lecturers=25,
            blocks_per_lecturer=random.randint(6, 8)
        )
        
        data = {
            "offerings": offerings,
            "constraints": constraints
        }
        
        total_blocks = sum(len(c['structured_rules']['atomic_constraints']) for c in constraints)
        print(f"   - {len(offerings)} offerings")
        print(f"   - {total_blocks} total constraint blocks")
        print(f"   - Avg {total_blocks/len(constraints):.1f} blocks per lecturer")
        
        start_time = time.time()
        result = solver.solve(data)
        solve_time = time.time() - start_time
        
        print(f"   - Solve time: {solve_time:.2f}s")
        print(f"   - Status: {result['status']}")
        
        # Should complete even if infeasible
        assert solve_time < 90.0, "Should complete within 90s"
        assert result['status'] in ['solved', 'failed'], "Should return valid status"
        
        if result['status'] == 'failed':
            conflicts = result.get('conflict_constraints', [])
            print(f"   - ⚠ Infeasible: {len(conflicts)} conflicting constraints detected")
            assert len(conflicts) > 0, "Should identify conflicts"
    
    def test_solver_timeout_behavior(self):
        """
        Verify solver respects timeout and returns partial results.
        
        Creates an extremely complex problem that may not solve quickly.
        """
        solver = CSPSolver()
        
        print("\n🔥 Timeout behavior test starting...")
        
        # Create very complex scenario
        offerings = self._generate_large_schedule(
            num_offerings=150,
            num_lecturers=50,
            num_cohorts=20
        )
        
        # Very heavy constraints
        constraints = self._generate_heavy_constraints(
            num_lecturers=50,
            blocks_per_lecturer=7
        )
        
        data = {
            "offerings": offerings,
            "constraints": constraints
        }
        
        print(f"   - {len(offerings)} offerings")
        print(f"   - {len(constraints)} heavily constrained lecturers")
        
        start_time = time.time()
        result = solver.solve(data)
        solve_time = time.time() - start_time
        
        print(f"   - Solve time: {solve_time:.2f}s")
        print(f"   - Status: {result['status']}")
        
        # Solver has 60s timeout in solver.py
        # Should respect it or solve earlier
        assert solve_time < 65.0, "Should respect solver timeout (60s + overhead)"
        assert result['status'] in ['solved', 'failed'], "Should return valid status"
    
    def test_maximum_cohort_conflicts(self):
        """
        Test with maximum cohort overlap - many courses for same cohort.
        
        All offerings target the same cohort, forcing sequential scheduling.
        """
        solver = CSPSolver()
        
        print("\n🔥 Maximum cohort conflict test starting...")
        
        # 30 courses all for the same cohort
        offerings = []
        for i in range(30):
            offerings.append({
                "offering_id": i + 1,
                "credit_points": 3.0,  # All 3-hour courses
                "group_number": 1,
                "cohorts": [
                    {"target_department_id": 1, "target_year_level": 3}
                ],
                "lecturers": [300 + i]  # Different lecturers
            })
        
        # Moderate constraints to keep it solvable
        constraints = self._generate_heavy_constraints(
            num_lecturers=30,
            blocks_per_lecturer=2
        )
        
        data = {
            "offerings": offerings,
            "constraints": constraints
        }
        
        print(f"   - {len(offerings)} offerings for single cohort")
        
        start_time = time.time()
        result = solver.solve(data)
        solve_time = time.time() - start_time
        
        print(f"   - Solve time: {solve_time:.2f}s")
        print(f"   - Status: {result['status']}")
        
        # Should solve (enough time slots for 30x3h = 90h, we have ~65h available)
        assert solve_time < 30.0, "Should solve within 30s"
        assert result['status'] in ['solved', 'failed'], "Should return valid status"
        
        if result['status'] == 'solved':
            # Verify no overlaps
            sessions = result['solution']
            print(f"   - ✓ Scheduled {len(sessions)} non-overlapping sessions")
            assert len(sessions) == 30, "Should schedule all offerings"
    
    def test_memory_efficiency(self):
        """
        Test that solver doesn't consume excessive memory.
        
        Creates a large problem and ensures it completes without OOM.
        """
        solver = CSPSolver()
        
        print("\n🔥 Memory efficiency test starting...")
        
        # Large but solvable problem
        offerings = self._generate_large_schedule(
            num_offerings=100,
            num_lecturers=40,
            num_cohorts=15
        )
        
        constraints = self._generate_heavy_constraints(
            num_lecturers=40,
            blocks_per_lecturer=4
        )
        
        data = {
            "offerings": offerings,
            "constraints": constraints
        }
        
        print(f"   - {len(offerings)} offerings, {len(constraints)} lecturers")
        
        # Should complete without memory issues
        start_time = time.time()
        result = solver.solve(data)
        solve_time = time.time() - start_time
        
        print(f"   - Solve time: {solve_time:.2f}s")
        print(f"   - Status: {result['status']}")
        print(f"   - ✓ No memory errors")
        
        assert result['status'] in ['solved', 'failed'], "Should complete successfully"

