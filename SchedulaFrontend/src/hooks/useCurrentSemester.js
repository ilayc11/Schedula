// src/hooks/useCurrentSemester.js
//
// Fetches the current active semester from the secretary dashboard endpoint
// (GET /secretary/dashboard/semester_info) so filters can default to the
// "current semester year" instead of the calendar year.
//
// Usage:
//   const { semesterYear } = useCurrentSemester({ enabled: !useMock });
//
// When `enabled` is false (e.g. mock mode) the hook does not hit the network
// and leaves `semesterYear` as null so callers can fall back to their own
// default. The fetch failing (no active semester, network error) is treated
// the same way: callers keep their fallback.

import { useEffect, useState } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
const SECRETARY_PREFIX = import.meta.env.VITE_API_PREFIX_SECRETARY || "/secretary";
const API_BASE = API_BASE_URL + SECRETARY_PREFIX;

function authHeaders() {
  const token = localStorage.getItem("access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function useCurrentSemester({ enabled = true } = {}) {
  const [semester, setSemester] = useState(null); // { year, number }
  const [loading, setLoading] = useState(Boolean(enabled));

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }

    let alive = true;
    setLoading(true);

    (async () => {
      try {
        const res = await fetch(`${API_BASE}/dashboard/semester_info`, {
          method: "GET",
          headers: { "Content-Type": "application/json", ...authHeaders() },
        });
        if (!res.ok) return; // 404 (no active semester) or other -> keep fallback
        const data = await res.json().catch(() => null);
        if (!alive || !data || data.semester_year == null) return;
        setSemester({
          year: Number(data.semester_year),
          number: Number(data.semester_number),
        });
      } catch {
        // Network/parse error: leave semester null so callers fall back.
      } finally {
        if (alive) setLoading(false);
      }
    })();

    return () => {
      alive = false;
    };
  }, [enabled]);

  return {
    semester,
    semesterYear: semester?.year ?? null,
    semesterNumber: semester?.number ?? null,
    loading,
  };
}

export default useCurrentSemester;
