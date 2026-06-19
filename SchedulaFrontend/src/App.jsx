import { useState } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from '/vite.svg'
import './App.css'
import { Routes, Route, Navigate } from "react-router-dom";
import LoginPage from "./pages/Login/LoginPage.jsx";
import LecturerDashboard from "./pages/HomePage/LecturerHome1.jsx";
import ConstraintsWritePage from "./pages/Constraints/ConstraintsWritePage.jsx";
import ConstraintsManagePage from "./pages/Constraints/ConstraintsManagePage.jsx";
import LecturerLayout from "./components/LecturerLayout.jsx";
import SchedulePage from './pages/Schedule/SchedulePage.jsx';
import SecretaryDashboard from "./pages/HomePage/SecretaryHome.jsx";
import SecretaryLayout from "./components/SecretaryLayout.jsx";
import SecretarySetupPage from './pages/Setup/SecretarySetupPage.jsx';
import SecretarySchedulePage from './pages/Schedule/SecretarySchedulePage.jsx';
import SecretaryAssignmentsPage from './pages/Schedule/SecretaryAssignmentsPage.jsx';
import SecretaryFairnessPage from './pages/Fairness/SecretaryFairnessPage.jsx';
import SecretaryBreakingConstraintsPage from './pages/Constraints/SecretaryBreakingConstraintsPage.jsx';
import SecretaryAllConstraintsPage from './pages/Constraints/SecretaryAllConstraintsPage.jsx';


// import LecturerDashboard from "./pages/LecturerHome2.jsx";

function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="/login" element={<LoginPage />} />

      <Route path="/lecturer" element={<LecturerLayout />}>
        <Route path="home" element={<LecturerDashboard />} />
        <Route path="constraints" element={<Navigate to="write" replace />} />
        <Route path="constraints/write" element={<ConstraintsWritePage />} />
        <Route path="constraints/manage" element={<ConstraintsManagePage />} />
        <Route path="schedule" element={<SchedulePage />} />
      </Route>

      <Route path="/secretary" element={<SecretaryLayout />}>
        <Route path="home" element={<SecretaryDashboard />} />
        <Route path="semester-setup" element={<SecretarySetupPage />} />
        {/* <Route path="schedule-manager" element={<SecretarySchedulePage />} /> */}
        <Route path="schedule-manager" element={<Navigate to="overview" replace />} />
        <Route path="schedule-manager/overview" element={<SecretarySchedulePage />} />
        <Route path="schedule-manager/assignments" element={<SecretaryAssignmentsPage />} />
        <Route path="fairness" element={<SecretaryFairnessPage />} />
        <Route path="constraints" element={<SecretaryAllConstraintsPage />} />
        <Route path="breaking-constraints" element={<SecretaryBreakingConstraintsPage />} />
        <Route path="all-constraints" element={<SecretaryAllConstraintsPage />} />
      </Route>

    </Routes>
  );
}
export default App

