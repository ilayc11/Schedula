// src/pages/LoginPage.jsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import "./LoginPage.css";
import IntroAnimation from "../../components/IntroAnimation";
import { consumeSessionMessage } from "../../utils/sessionExpiry.js";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";


function LoginPage() {
  const [username, setUsername] = useState("");
  const [idNumber, setIdNumber] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [introFinished, setIntroFinished] = useState(false);

  const navigate = useNavigate();

  // Show a friendly banner when the user was redirected here after their
  // session expired (set by the global fetch interceptor).
  useEffect(() => {
    const message = consumeSessionMessage();
    if (message) setNotice(message);
  }, []);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setNotice("");

    const cleanUsername = username.trim();
    const cleanId = idNumber.trim();

    if (!cleanUsername || !cleanId) {
      setError("Please fill in both username and ID number");
      return;
    }

    if (!/^\d{9}$/.test(cleanId)) {
      setError("ID number must be 9 digits");
      return;
    }

    setIsSubmitting(true);

    try {
      /* ========= REAL API LOGIN ========= */
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_name: cleanUsername,
          user_id: cleanId,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        setError(data?.detail || "Login failed");
        setIsSubmitting(false);
        return;
      }

      const data = await res.json();

      const token = data?.token?.access_token;
      const userData = data?.token?.user_data;

      if (!token || !userData) {
        setError("Login response is missing token or user data");
        setIsSubmitting(false);
        return;
      }

      localStorage.setItem("access_token", token);
      localStorage.setItem("user_data", JSON.stringify(userData));

      if (userData.role === "L") {
        navigate("/lecturer/home", { replace: true });
      } else {
        navigate("/secretary/home", { replace: true });
      }
      /* ================================= */

    } catch {
      setError("Unexpected error during login");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="login-bg">
      {!introFinished && <IntroAnimation onFinish={() => setIntroFinished(true)} />}

      <div className={`login-container ${introFinished ? "fade-in" : "hidden"}`}>
        <div className="login-card-glass">
          <div className="login-avatar-circle">
            <span className="login-avatar-icon">👤</span>
          </div>

          <h1 className="login-title-en">Login</h1>
          <p className="login-subtitle-en">Schedula - Lecturer Scheduling System</p>

          <form onSubmit={handleSubmit} className="login-form">
            {notice && <p className="login-notice">{notice}</p>}
            <div className="input-wrapper">
              <span className="input-icon">👤</span>
              <input
                type="text"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                className="login-input"
                placeholder="Username"
                disabled={isSubmitting}
              />
            </div>

            <div className="input-wrapper">
              <span className="input-icon">🆔</span>
              <input
                type="text"
                value={idNumber}
                onChange={(event) => setIdNumber(event.target.value)}
                className="login-input"
                placeholder="ID number"
                disabled={isSubmitting}
              />
            </div>

            {error && <p className="login-error">{error}</p>}

            <button type="submit" className="login-button-main" disabled={isSubmitting}>
              {isSubmitting ? "Logging in..." : "Login"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

export default LoginPage;
