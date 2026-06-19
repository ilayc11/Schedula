# src/input_convertor/config.py
"""Column mappings for Excel -> DB converter."""

# Lecturers Excel columns
LECTURERS_COLUMNS = {
    "user_id":       "USER_ID",
    "id_number":     "ID_NUMBER",   # preferred identity; falls back to USER_ID if empty
    "first_name":    "FIRST_NAME",
    "last_name":     "LAST_NAME",
    "email":         "EMAIL",
    "department_id": "DEPARTMENT",
    "degree_level":  "DEGREE_LEVEL",
    "course":        "COURSE",
    "group_number":  "GROUP_NUMBER",
    "academic_year": "YEAR",
    "semester":      "SEMESTER",
}

# Deduplicated lecturers Excel columns (user fields only — no assignment data)
# Used by load_static_data to populate the users table independently of semester data.
LECTURERS_DEDU_COLUMNS = {
    "user_id":       "USER_ID",
    "id_number":     "ID_NUMBER",   # preferred identity; falls back to USER_ID if empty
    "first_name":    "FIRST_NAME",
    "last_name":     "LAST_NAME",
    "email":         "EMAIL",
    "department_id": "DEPARTMENT",
}

# Courses Excel columns
COURSES_COLUMNS = {
    "department":        "DEPARTMENT",
    "degree_level":      "DEGREE_LEVEL",
    "course":            "COURSE",
    "course_name":       "NAME",
    "credit_points":     "CREDIT_POINTS",
    "target_year_level": "Cohort_year",  # optional cohort attribute
}

LECTURER_ROLE = "L"
