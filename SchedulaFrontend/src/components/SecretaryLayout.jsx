import { Outlet } from "react-router-dom";
import HeaderBar from "../components/HeaderBar";
import SecretarySidebar from "../components/SecretarySidebar";
import "../pages/HomePage/LecturerHome1.css";
import { useState } from "react";


function SecretaryLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(true);

  return (
    <div className={`app-shell ${sidebarOpen ? "sidebar-open" : "sidebar-collapsed"}`}>
      <HeaderBar />

      <div className="main-layout">
        <SecretarySidebar
          sidebarOpen={sidebarOpen}
          onToggle={() => setSidebarOpen((v) => !v)}
        />
        <main className="main-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
export default SecretaryLayout;
