import { NavLink, useNavigate } from "react-router-dom";
import "./Sidebar.css";

function Sidebar({ sidebarOpen, onToggle }) {
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
          to="/lecturer/home"
          end
          title={!sidebarOpen ? "Dashboard" : undefined}
          className={({ isActive }) =>
            `sidebar-item ${isActive ? "active" : ""}`
          }
        >
          <span className="sidebar-icon">🏠</span>
          <span className="sidebar-label">Dashboard</span>
        </NavLink>

        <NavLink
          to="/lecturer/constraints"
          title={!sidebarOpen ? "My Constraints" : undefined}
          className={({ isActive }) =>
            `sidebar-item ${isActive ? "active" : ""}`
          }
        >
          <span className="sidebar-icon">📝</span>
          <span className="sidebar-label">My Constraints</span>
        </NavLink>

        <div className="sidebar-subnav">
          <NavLink
            to="/lecturer/constraints/write"
            end
            title={!sidebarOpen ? "Write constraints" : undefined}
            className={({ isActive }) =>
              `sidebar-subitem ${isActive ? "active" : ""}`
            }
          >
            <span className="sidebar-icon">✍️</span>
            <span className="sidebar-label">Write constraints</span>
          </NavLink>

          <NavLink
            to="/lecturer/constraints/manage"
            title={!sidebarOpen ? "View and edit constraints" : undefined}
            className={({ isActive }) =>
              `sidebar-subitem ${isActive ? "active" : ""}`
            }
          >
            <span className="sidebar-icon">📋</span>
            <span className="sidebar-label">View and edit constraints</span>
          </NavLink>
        </div>

        <NavLink
          to="/lecturer/schedule"
          title={!sidebarOpen ? "My Schedule" : undefined}
          className={({ isActive }) =>
            `sidebar-item ${isActive ? "active" : ""}`
          }
        >
          <span className="sidebar-icon">🗓️</span>
          <span className="sidebar-label">My Schedule</span>
        </NavLink>
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

export default Sidebar;
