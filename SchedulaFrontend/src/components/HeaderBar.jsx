import "./HeaderBar.css";
import { useMemo } from "react";

function readStoredUser() {
  try {
    const raw = localStorage.getItem("user_data");
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function initialsFrom(user) {
  const first = (user?.first_name || "").trim();
  const last = (user?.last_name || "").trim();
  const a = (first[0] || "").toUpperCase();
  const b = (last[0] || "").toUpperCase();
  return (a + b).trim() || a || "U";
}

function displayNameFrom(user) {
  const first = (user?.first_name || "").trim();
  const last = (user?.last_name || "").trim();
  const full = `${first} ${last}`.trim();
  return full || user?.user_name || "User";
}

function HeaderBar() {
  const user = useMemo(() => readStoredUser(), []);
  const initials = initialsFrom(user);
  const displayName = displayNameFrom(user);

  return (
    <header className="header-bar">
      <div className="header-left">
        <div className="header-logo">S</div>
        <span className="header-title">Schedula Faculty Portal</span>
      </div>

      <div className="header-right">
        <div className="header-user">
          <div className="header-avatar">{initials}</div>
          <span className="header-username">{displayName}</span>
        </div>
      </div>
    </header>
  );
}

export default HeaderBar;
