import { NavLink, useNavigate } from "react-router-dom";
import "./Sidebar.css";

function SecretarySidebar({ sidebarOpen, onToggle }) {
  const navigate = useNavigate();

  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
  const AUTH_PREFIX = import.meta.env.VITE_API_PREFIX_AUTH || "/auth";
  const AUTH_BASE = API_BASE_URL + AUTH_PREFIX;

  const handleLogout = async () => {
    const token = localStorage.getItem("access_token");

    try {
      if (token) {
        await fetch(`${AUTH_BASE}/logout`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        }).catch(() => {});
      }
    } finally {
      localStorage.removeItem("access_token");
      localStorage.removeItem("user_data");
      navigate("/login", { replace: true });
    }
  };

  return (
    <aside className={`sidebar ${!sidebarOpen ? "sidebar-collapsed" : ""}`}>
      <button
        className="sidebar-toggle"
        onClick={onToggle}
        aria-label="Toggle sidebar"
      >
        {sidebarOpen ? "◀" : "▶"}
      </button>

      {sidebarOpen && <div className="sidebar-title">MENU</div>}

      <nav className="sidebar-nav">
        <NavLink
          to="/secretary/home"
          end
          title={!sidebarOpen ? "Dashboard" : undefined}
          className={({ isActive }) => `sidebar-item ${isActive ? "active" : ""}`}
        >
          <span className="sidebar-icon">🏠</span>
          <span className="sidebar-label">Dashboard</span>
        </NavLink>

        <NavLink
          to="/secretary/schedule-manager"
          title={!sidebarOpen ? "Schedule Manager" : undefined}
          className={({ isActive }) => `sidebar-item ${isActive ? "active" : ""}`}
        >
          <span className="sidebar-icon">🗂️</span>
          <span className="sidebar-label">Schedule Manager</span>
        </NavLink>

        <div className="sidebar-subnav">
          <NavLink
            to="/secretary/schedule-manager/overview"
            end
            title={!sidebarOpen ? "Overview" : undefined}
            className={({ isActive }) => `sidebar-subitem ${isActive ? "active" : ""}`}
          >
            <span className="sidebar-icon">📌</span>
            <span className="sidebar-label">Overview</span>
          </NavLink>

          <NavLink
            to="/secretary/schedule-manager/assignments"
            title={!sidebarOpen ? "Assignments" : undefined}
            className={({ isActive }) => `sidebar-subitem ${isActive ? "active" : ""}`}
          >
            <span className="sidebar-icon">📚</span>
            <span className="sidebar-label">Assignments</span>
          </NavLink>
        </div>

        <NavLink
          to="/secretary/fairness"
          title={!sidebarOpen ? "Fairness Review" : undefined}
          className={({ isActive }) => `sidebar-item ${isActive ? "active" : ""}`}
        >
          <span className="sidebar-icon">⚖️</span>
          <span className="sidebar-label">Fairness Review</span>
        </NavLink>

        <NavLink
          to="/secretary/constraints"
          title={!sidebarOpen ? "All Constraints" : undefined}
          className={({ isActive }) => `sidebar-item ${isActive ? "active" : ""}`}
        >
          <span className="sidebar-icon">📋</span>
          <span className="sidebar-label">All Constraints</span>
        </NavLink>

        {/* <NavLink
          to="/secretary/breaking-constraints"
          title={!sidebarOpen ? "Breaking Constraints" : undefined}
          className={({ isActive }) => `sidebar-item ${isActive ? "active" : ""}`}
        >
          <span className="sidebar-icon">🧩</span>
          <span className="sidebar-label">Breaking Constraints</span>
        </NavLink> */}

        <NavLink
          to="/secretary/semester-setup"
          title={!sidebarOpen ? "Semester Setup" : undefined}
          className={({ isActive }) => `sidebar-item ${isActive ? "active" : ""}`}
        >
          <span className="sidebar-icon">🛠️</span>
          <span className="sidebar-label">Semester Setup</span>
        </NavLink>

        {/* <NavLink
          to="/secretary/reports"
          title={!sidebarOpen ? "View Reports" : undefined}
          className={({ isActive }) => `sidebar-item ${isActive ? "active" : ""}`}
        >
          <span className="sidebar-icon">📈</span>
          <span className="sidebar-label">View Reports</span>
        </NavLink> */}
      </nav>

      <div className="sidebar-footer">
        <button
          className="sidebar-logout"
          onClick={handleLogout}
          title={!sidebarOpen ? "Logout" : undefined}
        >
          <span className="sidebar-icon">🚪</span>
          <span className="sidebar-label">Logout</span>
        </button>
      </div>
    </aside>
  );
}

export default SecretarySidebar;
