// src/components/dashboard/MyCoursesCard.jsx
import { useEffect, useState } from "react";
import { useMockMode } from "../context/MockModeContext.jsx";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
const LECTURER_PREFIX = import.meta.env.VITE_API_PREFIX_LECTURER || "/lecturer";
const API_BASE = API_BASE_URL + LECTURER_PREFIX;

// Mock data
const MOCK_COURSES = [
  {
    course_number: 20417,
    course_name: "Algorithms",
    group_number: 1,
    academic_year: 2026,
    semester: 1,
    role: "Lecturer",
  },
  {
    course_number: 20277,
    course_name: "Data Structures",
    group_number: 2,
    academic_year: 2026,
    semester: 1,
    role: "Lecturer",
  },
];

function MyCoursesCard() {
  const { useMock } = useMockMode();

  const [courses, setCourses] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;

    async function load() {
      setIsLoading(true);
      setError("");

      try {
        // Mock mode
        if (useMock) {
          await new Promise((resolve) => setTimeout(resolve, 300));
          if (!alive) return;
          setCourses(MOCK_COURSES);
          setIsLoading(false);
          return;
        }

        // Real mode
        const token = localStorage.getItem("access_token");
        if (!token) {
          throw new Error("Not authenticated");
        }

        const res = await fetch(`${API_BASE}/dashboard/my_courses`, {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!res.ok) {
          const data = await res.json().catch(() => null);
          throw new Error(data?.detail || `Error ${res.status}`);
        }

        const data = await res.json();
        if (!alive) return;
        setCourses(Array.isArray(data) ? data : []);
      } catch (e) {
        if (!alive) return;
        setError(e.message || "Failed to load courses");
      } finally {
        if (alive) setIsLoading(false);
      }
    }

    load();
    return () => {
      alive = false;
    };
  }, [useMock]);

  // Loading state
  if (isLoading) {
    return (
      <div className="card">
        <h2 style={{ marginTop: 0, marginBottom: "12px" }}>My Courses</h2>
        <p style={{ margin: 0, color: "var(--color-text-muted, #888)" }}>Loading...</p>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="card">
        <h2 style={{ marginTop: 0, marginBottom: "12px" }}>My Courses</h2>
        <p style={{ margin: 0, color: "var(--color-error, #e74c3c)" }}>{error}</p>
      </div>
    );
  }

  // Empty state
  if (courses.length === 0) {
    return (
      <div className="card">
        <h2 style={{ marginTop: 0, marginBottom: "12px" }}>My Courses</h2>
        <p style={{ margin: 0, color: "var(--color-text-muted, #888)" }}>
          No courses assigned yet.
        </p>
      </div>
    );
  }

  return (
    <div className="card">
      <h2 style={{ marginTop: 0, marginBottom: "12px" }}>My Courses</h2>
      <ul style={{ margin: 0, paddingLeft: "18px" }}>
        {courses.map((course, idx) => (
          <li key={`${course.course_number}-${course.group_number}-${idx}`}>
            {course.course_number}, {course.course_name}
            {course.group_number && ` (Group ${course.group_number})`}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default MyCoursesCard;
