// src/pages/Schedule/secretaryScheduleMock.js
const delay = (ms = 250) => new Promise((r) => setTimeout(r, ms));

const SEMESTER = { semester_year: 2026, semester_number: 1 };

let MOCK_MODE = "solved"; // "none" | "pending" | "solved" | "failed"

export function setSecretaryMockMode(mode) {
  MOCK_MODE = mode;
}

export async function mockGetSemesterInfo() {
  await delay(180);
  return { ...SEMESTER };
}

export async function mockGetSolverStatus(semester_year, semester_number) {
  await delay(220);

  if (MOCK_MODE === "none") {
    return {
      run_id: null,
      status: "none",
      schedule_id: null,
      broken_constraint_details: null,
      semester_year,
      semester_number,
    };
  }

  if (MOCK_MODE === "pending") {
    return {
      run_id: 99,
      status: "pending",
      schedule_id: null,
      broken_constraint_details: null,
      semester_year,
      semester_number,
    };
  }

  if (MOCK_MODE === "failed") {
    return {
      run_id: 101,
      status: "failed",
      schedule_id: null,
      broken_constraint_details: [
        {
          lecturer_name: "Dr. Ada Lovelace",
          raw_text: "Cannot teach on Tuesday 10:00-12:00 but was assigned.",
        },
        {
          lecturer_name: "Dr. Grace Hopper",
          raw_text: "Two sessions overlap for the same lecturer.",
        },
      ],
      semester_year,
      semester_number,
    };
  }

  return {
    run_id: 100,
    status: "solved",
    schedule_id: 42,
    broken_constraint_details: null,
    semester_year,
    semester_number,
  };
}

/**
 * cohorts format aligns with backend idea:
 * cohorts: [{ target_department_id: number, target_year_level: number }, ...]
 *
 * Notes:
 * - A session can target multiple cohorts.
 * - Department names usually require another endpoint, so we keep ids here.
 */
export async function mockGetScheduleDetails(schedule_id) {
  await delay(260);

  if (MOCK_MODE !== "solved") return [];

  return [
    {
      session_id: 1,
      schedule_id,
      day_of_week: 1,
      start_time: "10:00",
      end_time: "12:00",
      course_name: "Algorithms",
      course_number: 20417,
      offering_id: 50,
      lecturer_internal_id: 101,
      group_number: 1,
      lecturer_name: "Dr. Ada Lovelace",
      semester_year: SEMESTER.semester_year,
      semester_number: SEMESTER.semester_number,
      cohorts: [
        { target_department_id: 1, target_year_level: 2 },
        { target_department_id: 1, target_year_level: 3 },
      ],
    },
    {
      session_id: 2,
      schedule_id,
      day_of_week: 3,
      start_time: "13:00",
      end_time: "14:00",
      course_name: "Databases",
      course_number: 20277,
      offering_id: 51,
      lecturer_internal_id: 102,
      group_number: 2,
      lecturer_name: "Dr. Edgar Codd",
      semester_year: SEMESTER.semester_year,
      semester_number: SEMESTER.semester_number,
      cohorts: [{ target_department_id: 2, target_year_level: 2 }],
    },
    {
      session_id: 3,
      schedule_id,
      day_of_week: 4,
      start_time: "17:00",
      end_time: "20:00",
      course_name: "Web Dev",
      course_number: 37210,
      offering_id: 52,
      lecturer_internal_id: 103,
      group_number: 1,
      lecturer_name: "Dr. Grace Hopper",
      semester_year: SEMESTER.semester_year,
      semester_number: SEMESTER.semester_number,
      cohorts: [
        { target_department_id: 3, target_year_level: 1 },
        { target_department_id: 3, target_year_level: 2 },
      ],
    },
    {
      session_id: 4,
      schedule_id,
      day_of_week: 2,
      start_time: "08:00",
      end_time: "10:00",
      course_name: "Discrete Math",
      course_number: 20425,
      offering_id: 53,
      lecturer_internal_id: 104,
      group_number: 1,
      lecturer_name: "Dr. Alan Turing",
      semester_year: SEMESTER.semester_year,
      semester_number: SEMESTER.semester_number,
      cohorts: [{ target_department_id: 1, target_year_level: 2 }],
    },
    {
      session_id: 5,
      schedule_id,
      day_of_week: 4,
      start_time: "08:00",
      end_time: "10:00",
      course_name: "Operating Systems",
      course_number: 20561,
      offering_id: 54,
      lecturer_internal_id: 105,
      group_number: 1,
      lecturer_name: "Dr. Linus Torvalds",
      semester_year: SEMESTER.semester_year,
      semester_number: SEMESTER.semester_number,
      cohorts: [{ target_department_id: 1, target_year_level: 2 }],
    },
    {
      session_id: 6,
      schedule_id,
      day_of_week: 5,
      start_time: "12:00",
      end_time: "14:00",
      course_name: "Computer Architecture",
      course_number: 20612,
      offering_id: 55,
      lecturer_internal_id: 106,
      group_number: 1,
      lecturer_name: "Dr. Barbara Liskov",
      semester_year: SEMESTER.semester_year,
      semester_number: SEMESTER.semester_number,
      cohorts: [{ target_department_id: 1, target_year_level: 2 }],
    },
    {
      session_id: 7,
      schedule_id,
      day_of_week: 2,
      start_time: "10:00",
      end_time: "12:00",
      course_name: "Theory of Computation",
      course_number: 20466,
      offering_id: 56,
      lecturer_internal_id: 107,
      group_number: 1,
      lecturer_name: "Dr. Donald Knuth",
      semester_year: SEMESTER.semester_year,
      semester_number: SEMESTER.semester_number,
      cohorts: [{ target_department_id: 1, target_year_level: 3 }],
    },
    {
      session_id: 8,
      schedule_id,
      day_of_week: 5,
      start_time: "08:00",
      end_time: "10:00",
      course_name: "Advanced Programming",
      course_number: 30111,
      offering_id: 57,
      lecturer_internal_id: 101,
      group_number: 1,
      lecturer_name: "Dr. Ada Lovelace",
      semester_year: SEMESTER.semester_year,
      semester_number: SEMESTER.semester_number,
      cohorts: [{ target_department_id: 2, target_year_level: 3 }],
    },
    {
      session_id: 9,
      schedule_id,
      day_of_week: 2,
      start_time: "14:00",
      end_time: "16:00",
      course_name: "Software Engineering",
      course_number: 31002,
      offering_id: 58,
      lecturer_internal_id: 103,
      group_number: 1,
      lecturer_name: "Dr. Grace Hopper",
      semester_year: SEMESTER.semester_year,
      semester_number: SEMESTER.semester_number,
      cohorts: [{ target_department_id: 1, target_year_level: 1 }],
    },
  ];
}
