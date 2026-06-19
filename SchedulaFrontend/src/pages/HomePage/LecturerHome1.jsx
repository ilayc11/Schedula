// src/pages/HomePage/LecturerHome1.jsx
import "./LecturerHome1.css";

import SystemStatusCard from "../../components/SystemStatusCard";
import LecturerConstraintsActions from "../../components/LecturerConstraintsActions";
import MyCoursesCard from "../../components/MyCoursesCard";
import TelegramLinkingCard from "../../components/TelegramLinkingCard";
import { useState } from "react";
import { useNavigate } from "react-router-dom";


// import SolverStatusCard from "../../components/SolverStatusCard";

function LecturerDashboard() {
    // const currentSemesterYear = 2025;
    // const currentSemesterNumber = 1;
    const [semester, setSemester] = useState(null);

    const navigate = useNavigate();
    const showScheduleCard = semester && (semester && (semester.status === "CHA" || semester.status === "PUB"));
    const scheduleLabel = semester?.status === "PUB" ? "final" : "temporary";

  return (
    <section className="main-content">
      <h1 className="page-title">Dashboard</h1>
      <SystemStatusCard userRole="lecturer" onSemesterLoaded={setSemester} />
      {/* { semester && (<LecturerConstraintsActions status={semester.status} />)} */}
      {semester && (
        <div className="lecturer-actions-polish">
          <LecturerConstraintsActions status={semester.status} />
        </div>
      )}
      
      {/* <SolverStatusCard 
        semesterYear={currentSemesterYear} 
        semesterNumber={currentSemesterNumber} 
      /> */}
      {showScheduleCard && (
    <div className="card">
      <h2 className="card-title">Schedule</h2>
       <p className="schedule-published-text">
        A schedule has been published for you ({scheduleLabel}).
      </p>
      <button
        type="button"
        className="button button-primary"
        onClick={() => navigate("/lecturer/schedule")}
      >
        View Schedule
      </button>
    </div>
  )}

  <div className="lecturer-courses-section">
    <MyCoursesCard />
  </div>
      {/* <TelegramLinkingCard /> */}
    </section>
  );
}

export default LecturerDashboard;
