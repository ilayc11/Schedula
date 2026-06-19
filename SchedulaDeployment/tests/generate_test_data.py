#!/usr/bin/env python3
"""
Standalone CLI script for generating test data.

Usage:
    python generate_test_data.py --scenario happy_path
    python generate_test_data.py --scenario over_constrained
    python generate_test_data.py --scenario failure_path
    python generate_test_data.py --scenario happy_path --lecturers 100 --courses 100

This script is useful for:
- Manually populating the database for testing
- Creating demo data
- Setting up specific test scenarios for debugging
"""

import asyncio
import argparse
import sys
from test_data_generators import (
    setup_happy_path_data,
    setup_over_constrained_data,
    setup_failure_path_data,
    setup_realistic_university_data
)

# Default configuration
DEFAULT_BACKEND_URL = "http://localhost:8000"
DEFAULT_YEAR = 2025
DEFAULT_SEMESTER = 1
DEFAULT_LECTURERS = 50
DEFAULT_COURSES = 50


async def main():
    parser = argparse.ArgumentParser(
        description="Generate test data for CSP solver testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --scenario happy_path
  %(prog)s --scenario over_constrained --lecturers 100 --courses 100
  %(prog)s --scenario failure_path --year 2027 --semester 2
        """
    )
    
    parser.add_argument(
        '--scenario',
        type=str,
        required=True,
        choices=['happy_path', 'over_constrained', 'failure_path', 'realistic_university'],
        help='Test scenario to generate data for'
    )
    
    parser.add_argument(
        '--backend-url',
        type=str,
        default=DEFAULT_BACKEND_URL,
        help=f'Backend API URL (default: {DEFAULT_BACKEND_URL})'
    )
    
    parser.add_argument(
        '--year',
        type=int,
        default=DEFAULT_YEAR,
        help=f'Semester year (default: {DEFAULT_YEAR})'
    )
    
    parser.add_argument(
        '--semester',
        type=int,
        default=DEFAULT_SEMESTER,
        choices=[1, 2, 3],
        help=f'Semester number (default: {DEFAULT_SEMESTER})'
    )
    
    parser.add_argument(
        '--lecturers',
        type=int,
        default=DEFAULT_LECTURERS,
        help=f'Number of lecturers to create (default: {DEFAULT_LECTURERS})'
    )
    
    parser.add_argument(
        '--courses',
        type=int,
        default=DEFAULT_COURSES,
        help=f'Number of courses to create (default: {DEFAULT_COURSES})'
    )
    
    args = parser.parse_args()
    
    # Validate inputs
    if args.lecturers < 1 or args.lecturers > 1000:
        print("Error: Number of lecturers must be between 1 and 1000")
        sys.exit(1)
    
    if args.courses < 1 or args.courses > 1000:
        print("Error: Number of courses must be between 1 and 1000")
        sys.exit(1)
    
    # Print configuration
    print("\n" + "="*70)
    print("TEST DATA GENERATOR")
    print("="*70)
    print(f"Scenario:      {args.scenario}")
    print(f"Backend URL:   {args.backend_url}")
    print(f"Semester:      {args.year}-{args.semester}")
    print(f"Lecturers:     {args.lecturers}")
    print(f"Courses:       {args.courses}")
    print("="*70 + "\n")
    
    # Generate data based on scenario
    try:
        if args.scenario == 'happy_path':
            print("Generating HAPPY PATH data (simple, easily solvable constraints)...\n")
            lecturers = await setup_happy_path_data(
                args.backend_url,
                args.year,
                args.semester,
                num_lecturers=args.lecturers,
                num_courses=args.courses
            )
            
        elif args.scenario == 'over_constrained':
            print("Generating OVER-CONSTRAINED data (complex but solvable constraints)...\n")
            lecturers = await setup_over_constrained_data(
                args.backend_url,
                args.year,
                args.semester,
                num_lecturers=args.lecturers,
                num_courses=args.courses
            )
            
        elif args.scenario == 'failure_path':
            print("Generating FAILURE PATH data (impossible-to-satisfy constraints)...\n")
            lecturers = await setup_failure_path_data(
                args.backend_url,
                args.year,
                args.semester,
                num_lecturers=args.lecturers,
                num_courses=args.courses
            )
        
        elif args.scenario == 'realistic_university':
            print("Generating REALISTIC UNIVERSITY data (3 depts, varied constraints)...\n")
            lecturers, _ = await setup_realistic_university_data(
                args.backend_url,
                args.year,
                args.semester
            )
        
        # Success summary
        print("\n" + "="*70)
        print("✅ DATA GENERATION COMPLETE")
        print("="*70)
        print(f"Created {len(lecturers)} lecturers")
        print(f"Created {args.courses} courses")
        print(f"Generated constraints for scenario: {args.scenario}")
        print("\nThe solver should now process this data automatically.")
        print("Monitor solver logs to see scheduling results.")
        print("="*70 + "\n")
        
    except Exception as e:
        print("\n" + "="*70)
        print("❌ DATA GENERATION FAILED")
        print("="*70)
        print(f"Error: {e}")
        print("\nPlease check:")
        print("  - Backend service is running and accessible")
        print("  - Database is available")
        print("  - API endpoints are correctly configured")
        print("="*70 + "\n")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

