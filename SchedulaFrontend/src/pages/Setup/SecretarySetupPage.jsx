// src/pages/Setup/SecretarySetupPage.jsx
// import { useEffect, useMemo, useState } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useMockMode } from "../../context/MockModeContext.jsx";
import "./SecretarySetupPage.css";
import StatusToast from "../../components/StatusToast.jsx";
import {
  ArrowLeft,
  CalendarDays,
  GraduationCap,
  Info,
  ShieldCheck,
  UploadCloud,
} from "lucide-react";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
const SECRETARY_PREFIX = import.meta.env.VITE_API_PREFIX_SECRETARY || "/secretary";
const API_BASE = `${API_BASE_URL}${SECRETARY_PREFIX}/semesters`;
const SETUP_API_BASE = `${API_BASE_URL}${SECRETARY_PREFIX}/setup`;

const PERIOD_OPTIONS = [
  { value: "SET", label: "Setup" },
  { value: "SUB", label: "Constraint Submission" },
  { value: "REV", label: "Review" },
  { value: "CHA", label: "Changes Period" },
  { value: "PUB", label: "Published" },
];

const SEMESTER_OPTIONS = [
  { value: 1, label: "Fall" },
  { value: 2, label: "Spring" },
  { value: 3, label: "Summer" },
];

const CURRENT_YEAR = new Date().getFullYear();
const FUTURE_YEARS_OPTIONS = Array.from({ length: 6 }, (_, i) => CURRENT_YEAR + i);

function getToken() { return localStorage.getItem("access_token"); }
function safeInt(v, fallback = null) {
  const n = Number(v);
  return Number.isFinite(n) ? Math.floor(n) : fallback;
}
function formatApiDateToDisplay(value) {
  if (!value) return "";
  const [year, month, day] = value.split("-");
  if (!year || !month || !day) return "";
  return `${day}/${month}/${year}`;
}

function displayDateToApi(value) {
  const [day, month, year] = value.split("/");
  if (day?.length === 2 && month?.length === 2 && year?.length === 4) {
    return `${year}-${month}-${day}`;
  }
  return null;
}

function normalizeDateInput(value) {
  const digits = value.replace(/\D/g, "").slice(0, 8);

  if (digits.length <= 2) {
    return digits;
  }

  if (digits.length <= 4) {
    return `${digits.slice(0, 2)}/${digits.slice(2)}`;
  }

  return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
}

export default function SecretarySetupPage() {
  const { useMock } = useMockMode();
  const [allSemesters, setAllSemesters] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  // const [setPageError] = useState("");
  const [, setPageError] = useState("");
  // const [toast, setToast] = useState({ message: "", type: "" });
  const [toast, setToast] = useState({ open: false, message: "", type: "success", title: "" });


  const [selectedYear, setSelectedYear] = useState(null);
  const [selectedSemesterNumber, setSelectedSemesterNumber] = useState(null);
  const [isCreateMode, setIsCreateMode] = useState(false);
  
  const [draft, setDraft] = useState({
    semester_year: CURRENT_YEAR,
    semester_number: 1,
    status: "SET"
  });

  const dateInputRefs = useRef({});
  const [dateDrafts, setDateDrafts] = useState({});
  const [lecturersFile, setLecturersFile] = useState(null);
  const [coursesFile, setCoursesFile] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [createdSemester, setCreatedSemester] = useState(null);
  const [isUploading, setIsUploading] = useState(false);

  // const showToast = (message, type = "success") => {
  //   setToast({ message, type });
  //   setTimeout(() => setToast({ message: "", type: "" }), 3000);
  // };
  const showToast = (message, type = "success", title = "") => {
    setToast({ open: true, message, type, title });
  };

  const existingYears = useMemo(() => {
    const uniq = new Set(allSemesters.map((s) => s.semester_year).filter(Boolean));
    return Array.from(uniq).sort((a, b) => b - a);
  }, [allSemesters]);

  // אופציות לבחירה ב-Select
  const yearsOptions = useMemo(() => {
    if (isCreateMode) {
      const combined = new Set([...existingYears, ...FUTURE_YEARS_OPTIONS]);
      return Array.from(combined).sort((a, b) => b - a);
    }
    return existingYears;
  }, [isCreateMode, existingYears]);

  const semestersForSelectedYear = useMemo(() => {
    if (!selectedYear) return [];
    return allSemesters
      .filter((s) => s.semester_year === selectedYear)
      .sort((a, b) => (a.semester_number || 0) - (b.semester_number || 0));
  }, [allSemesters, selectedYear]);

  useEffect(() => {
    let alive = true;
    async function loadSemesters() {
      setIsLoading(true);
      try {
        let data = [];
        if (useMock) {
          await new Promise(r => setTimeout(r, 200));
          data = [{ semester_year: 2025, semester_number: 1, status: "SET", semester_start_date: "2025-10-01", semester_end_date: "2026-01-31" }];
        } else {
          const res = await fetch(`${API_BASE}/all`, {
            headers: { Authorization: `Bearer ${getToken()}` },
          });
          if (!res.ok) throw new Error("Failed to load semesters");
          data = await res.json();
        }

        if (!alive) return;
        setAllSemesters(data);
        
        if (data.length > 0) {
          const def = data[0];
          setSelectedYear(def.semester_year);
          setSelectedSemesterNumber(def.semester_number);
          setDraft(def);
          setIsCreateMode(false);
        } else {
          setIsCreateMode(true);
        }
      } catch (e) { if (alive) setPageError(e.message); }
      finally { if (alive) setIsLoading(false); }
    }
    loadSemesters();
    return () => { alive = false; };
  }, [useMock]);

  useEffect(() => {
    if (isCreateMode) return;
    const found = allSemesters.find(
      s => s.semester_year === selectedYear && s.semester_number === selectedSemesterNumber
    );
    if (found) setDraft(found);
  }, [selectedYear, selectedSemesterNumber, allSemesters, isCreateMode]);

  const updateField = (k, v) => setDraft(p => ({ ...p, [k]: v }));

  async function uploadSemesterAssignments() {
    if (!lecturersFile || !coursesFile) {
      throw new Error("Please upload both the lecturers assignments file and the courses file.");
    }

    const formData = new FormData();
    formData.append("lecturers_file", lecturersFile);
    formData.append("courses_file", coursesFile);

    // Send the files as multipart/form-data. Do NOT set Content-Type
    // manually: the browser must set it (with the multipart boundary) itself.
    const res = await fetch(`${SETUP_API_BASE}/load_assignments`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${getToken()}`,
      },
      body: formData,
    });

    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      const { detail } = errorData || {};
      const message =
        typeof detail === "string"
          ? detail
          : Array.isArray(detail)
          ? detail.map((d) => d?.msg).filter(Boolean).join(", ")
          : detail?.msg || "Failed to upload semester data.";
      throw new Error(message);
    }

    return res.json();
  }

  async function handleSave() {
    try {
      setIsSaving(true);
      const url = isCreateMode ? `${API_BASE}/` : `${API_BASE}/${draft.semester_year}/${draft.semester_number}`;
      const method = isCreateMode ? "POST" : "PUT";
      
      const res = await fetch(url, {
        method,
        headers: {
          Authorization: `Bearer ${getToken()}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(draft),
      });

      if (!res.ok) {
          const errorData = await res.json().catch(() => ({}));
          throw new Error(errorData.detail || "Save failed");
      }
      
      const saved = await res.json();

      if (isCreateMode) {
        setCreatedSemester(saved);
      }

      // if (isCreateMode && !useMock) {
      //   await uploadSemesterAssignments();
      // }

      if (isCreateMode) {
        setAllSemesters([saved, ...allSemesters]);
      } else {
        setAllSemesters(allSemesters.map(s => 
          (s.semester_year === saved.semester_year && s.semester_number === saved.semester_number) ? saved : s
        ));
      }

      setIsCreateMode(false);
      setSelectedYear(saved.semester_year);
      setSelectedSemesterNumber(saved.semester_number);
      showToast(isCreateMode ? "Semester created successfully." : "Changes saved successfully.", "success");
    } catch (e) {
      showToast(e.message, "error");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleUploadFiles() {
    try {
      setIsUploading(true);
      await uploadSemesterAssignments();
      showToast("Semester files uploaded successfully.", "success");
    } catch (e) {
      showToast(e.message, "error");
    } finally {
      setIsUploading(false);
    }
  }

  // function toDate(value) {
  //   if (!value) return null;
  //   return new Date(value);
  // }

  // function toApiDate(date) {
  //   if (!date) return "";
  //   const year = date.getFullYear();
  //   const month = String(date.getMonth() + 1).padStart(2, "0");
  //   const day = String(date.getDate()).padStart(2, "0");
  //   return `${year}-${month}-${day}`;
  // }

  return (
    <section className="content-container setup-page">
      {/* {toast.message && (
        <div className={`toast-notification ${toast.type}`}>
          {toast.message}
        </div>
      )} */}
      <StatusToast
        open={toast.open}
        type={toast.type}
        title={toast.title || (toast.type === "error" ? "Something went wrong" : "Saved")}
        message={toast.message}
        onClose={() => setToast({ open: false, message: "", type: "success", title: "" })}
      />

      <div className="setup-header">
        <div>
          <h1 className="setup-title">System Setup</h1>
          <p className="setup-subtitle">
            {isCreateMode
              ? "Create and configure a new academic semester in the scheduling system."
              : "Configure the academic semester and key dates for the scheduling system."}
          </p>
        </div>

        <button className="setup-top-action" onClick={() => setIsCreateMode(!isCreateMode)}>
          {isCreateMode && <ArrowLeft size={17} strokeWidth={2.2} />}
          <span>{isCreateMode ? "Back to Setup" : "Create New Semester"}</span>
        </button>
      </div>

      <div className={isCreateMode ? "setup-layout setup-layout-create" : "setup-layout"}>
        {isCreateMode && (
          <aside className="setup-steps-card">
            <div className="setup-step setup-step-active">
              <span className="setup-step-number">1</span>
              <div>
                <strong>Selection</strong>
                <p>Choose the basic details for your semester.</p>
              </div>
            </div>

            <div className="setup-step">
              <span className="setup-step-number">2</span>
              <div>
                <strong>Configuration</strong>
                <p>Set important dates and deadlines.</p>
              </div>
            </div>

            <div className="setup-step">
              <span className="setup-step-number">3</span>
              <div>
                <strong>Data Upload</strong>
                <p>Upload lecturers and courses files.</p>
              </div>
            </div>

          </aside>
        )}

        <div className="setup-main-column">  

      
      <div className="card setup-card">
        <div className="setup-section-head">
          <div className="setup-section-icon">
            <CalendarDays size={20} strokeWidth={2.2} />
          </div>
          <div>
            <h2 className="setup-card-title">1. Selection</h2>
            <p className="setup-card-subtitle">Choose the basic details for your semester.</p>
          </div>
        </div>
        {/* <h2 className="setup-card-title">1. Selection</h2> */}
        <div className="setup-select-grid">
          <label className="setup-field">
            <span>Year</span>
            <select 
              value={isCreateMode ? draft.semester_year : (selectedYear || "")} 
              onChange={e => {
                const val = safeInt(e.target.value);
                if (isCreateMode) updateField("semester_year", val);
                else setSelectedYear(val);
              }}
            >
              {yearsOptions.map(y => <option key={y} value={y}>{y}</option>)}
            </select>
          </label>

          <label className="setup-field">
            <span>Semester</span>
            <select 
              value={isCreateMode ? draft.semester_number : (selectedSemesterNumber || "")}
              onChange={e => {
                const val = safeInt(e.target.value);
                if (isCreateMode) updateField("semester_number", val);
                else setSelectedSemesterNumber(val);
              }}
            >
              {isCreateMode ? 
                SEMESTER_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>) :
                semestersForSelectedYear.map(s => (
                  <option key={s.semester_number} value={s.semester_number}>
                    {SEMESTER_OPTIONS.find(o => o.value === s.semester_number)?.label}
                  </option>
                ))
              }
              
            </select>
          </label>

          <label className="setup-field">
            <span>Status</span>
            <select value={draft.status} onChange={e => updateField("status", e.target.value)}>
              {PERIOD_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </label>
        </div>
      </div>

      <div className="card setup-card">
        <div className="setup-section-head">
          <div className="setup-section-icon">
            <CalendarDays size={20} strokeWidth={2.2} />
          </div>
          <div>
            <h2 className="setup-card-title">2. Configuration</h2>
            <p className="setup-card-subtitle">Set important dates and deadlines.</p>
          </div>
        </div>
        {/* <h2 className="setup-card-title">2. Configuration</h2> */}
        <div className="setup-form-grid">
          {[
            { id: 'semester_start_date', label: 'Start' }, { id: 'semester_end_date', label: 'End' },
            { id: 'constraint_start_date', label: 'Constraints Open' }, { id: 'constraint_end_date', label: 'Constraints Close' },
            { id: 'change_period_start', label: 'Changes Start' }, { id: 'change_period_end', label: 'Changes End' }
          ].map(f => (
            <label key={f.id} className="setup-field">
              <span>{f.label}</span>
              <div className="setup-date-control">
              <input
                type="text"
                placeholder="dd/mm/yyyy"
                maxLength={10}
                inputMode="numeric"
                value={dateDrafts[f.id] ?? formatApiDateToDisplay(draft[f.id])}
                onChange={(e) => {
                  const value = normalizeDateInput(e.target.value);
                  setDateDrafts((prev) => ({ ...prev, [f.id]: value }));

                  const apiDate = displayDateToApi(value);
                  if (apiDate) {
                    updateField(f.id, apiDate);
                  }

                  if (value === "") {
                    updateField(f.id, "");
                  }
                }}
              />

              <button
                type="button"
                className="setup-calendar-button"
                onClick={() => {
                  const input = dateInputRefs.current[f.id];
                  if (input?.showPicker) input.showPicker();
                  else input?.click();
                }}
                aria-label={`Choose ${f.label} date`}
              >
                <CalendarDays size={18} strokeWidth={2.2} />
              </button>

              <input
                ref={(el) => {
                  dateInputRefs.current[f.id] = el;
                }}
                className="native-date-picker-hidden"
                type="date"
                value={draft[f.id] || ""}
                onChange={(e) => {
                  updateField(f.id, e.target.value);
                  setDateDrafts((prev) => ({
                    ...prev,
                    [f.id]: formatApiDateToDisplay(e.target.value),
                  }));
                }}
              />
            </div>
      
            </label>
          ))}
        </div>
        {/* <div className="setup-footer">

        </div> */}
        <div className="setup-footer">
          <button
            className="setup-create-final"
            onClick={handleSave}
            disabled={isLoading || isSaving}
          >
            {isSaving
              ? (isCreateMode ? "Creating..." : "Saving...")
              : (isCreateMode ? "Create Semester" : "Save Changes")}
          </button>
        </div>
        {/* {isCreateMode && !createdSemester && (
          <div className="setup-footer">
            <button
              className="setup-create-final"
              onClick={handleSave}
              disabled={isLoading || isSaving}
            >
              {isSaving ? "Creating..." : "Create Semester"}
            </button>
          </div>
        )} */}
      </div>
    {/* {isCreateMode && createdSemester && ( */}
    {(createdSemester || !isCreateMode) && (
        <div className="card setup-card">
          {/* <h2 className="setup-card-title">3. Semester Data Upload</h2> */}
          <div className="setup-section-head">
            <div className="setup-section-icon">
              <UploadCloud size={20} strokeWidth={2.2} />
            </div>
            <div>
              <h2 className="setup-card-title">3. Data Upload</h2>
              <p className="setup-card-subtitle">Upload the required files for this semester.</p>
            </div>
          </div>

          <div className="setup-form-grid">
            <label className="setup-field upload-field">
            <span>Lecturers Assignments File</span>

            <div className="upload-box">
              <input
                id="lecturers-file"
                type="file"
                accept=".xlsx,.xls"
                onChange={(e) => setLecturersFile(e.target.files?.[0] || null)}
              />

              <label htmlFor="lecturers-file" className="upload-button">
                Choose File
              </label>

              <span className="upload-file-name">
                {lecturersFile ? lecturersFile.name : "No file selected"}
              </span>
            </div>
          </label>

          <label className="setup-field upload-field">
            <span>Courses File</span>

            <div className="upload-box">
              <input
                id="courses-file"
                type="file"
                accept=".xlsx,.xls"
                onChange={(e) => setCoursesFile(e.target.files?.[0] || null)}
              />

              <label htmlFor="courses-file" className="upload-button">
                Choose File
              </label>

              <span className="upload-file-name">
                {coursesFile ? coursesFile.name : "No file selected"}
              </span>
            </div>
          </label>

           
          </div>
        </div>
      )}
    

      </div>
      </div>
      <div className="setup-footer">
        <button
          className="setup-create-final"
          onClick={handleUploadFiles}
          disabled={isUploading || !lecturersFile || !coursesFile}
        >
          {isUploading ? "Uploading..." : "Upload Files"}
        </button>
      </div>
    </section>
  );
}