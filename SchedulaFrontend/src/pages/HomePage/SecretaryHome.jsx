// import "./SecretaryHome.css";
import "../HomePage/LecturerHome1.css";

import SystemStatusCard from "../../components/SystemStatusCard";
import SolverStatusCard from "../../components/SolverStatusCard";
import CollaborationStatsCard from "../../components/CollaborationStatsCard";
import { useState } from "react";


function SecretaryDashboard() {
     // TODO: Get current semester from API or context
  // const currentSemesterYear = 2025;
  // const currentSemesterNumber = 1;
  const [activeSemester, setActiveSemester] = useState(null);


  // return (
  //   <section className="main-content">
  //     <h1 style={{ marginTop: 0, marginBottom: "16px" }}>Dashboard</h1>
  //     <SystemStatusCard userRole="secretary" onSemesterLoaded={setActiveSemester} />
  //     <SolverStatusCard 
  //       semesterYear={activeSemester?.semester_year} 
  //       semesterNumber={activeSemester?.semester_number} 
  //       userRole="secretary" 
  //     />
  //     <CollaborationStatsCard
  //       semesterYear={activeSemester?.year}
  //       semesterNumber={activeSemester?.number}
  //       semesterStatus={activeSemester?.status}
  //     />
  //   </section>
  // );
    return (
    <section className="main-content secretary-dashboard-page">
      <div className="dashboard-hero">
        <p className="dashboard-eyebrow">Smart Academic Scheduling</p>
        <h1>Dashboard</h1>
        <p className="dashboard-subtitle">
          Here’s what’s happening with your scheduling system.
        </p>
      </div>

      <div className="dashboard-stack">
        <SystemStatusCard userRole="secretary" onSemesterLoaded={setActiveSemester} />

        <SolverStatusCard
          semesterYear={activeSemester?.semester_year}
          semesterNumber={activeSemester?.semester_number}
          userRole="secretary"
        />

        <CollaborationStatsCard
          semesterYear={activeSemester?.year}
          semesterNumber={activeSemester?.number}
          semesterStatus={activeSemester?.status}
        />
      </div>
    </section>
  );
}

export default SecretaryDashboard;