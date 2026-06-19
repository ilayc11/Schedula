// src/pages/LecturerHome2.jsx
import "./LecturerHome2.css";
import HeaderBar from "../components/HeaderBar";

function LecturerDashboard() {
  return (
    <div className="app-shell">
      <HeaderBar />

      {/* בלי סיידבר; לייאאוט חדש לדף נחיתה 2 */}
      <main className="home2-main">
        <section className="home2-content">
          <h1 className="dashboard-title">שלום, ד״ר ג׳ון דו</h1>
          <p className="dashboard-subtitle">מה תרצה לעשות היום</p>

          <div className="tile-grid">
            {/* כתיבת אילוצים / צ׳אט */}
            <button className="tile-card tile-blue">
              <div className="tile-icon">💬</div>
              <div className="tile-title">כתיבת אילוצים</div>
              <div className="tile-subtitle">
                שיחה עם הצ׳אט בוט בשפה חופשית
              </div>
            </button>

            {/* צפייה באילוצים שלי */}
            <button className="tile-card tile-green">
              <div className="tile-icon">📄</div>
              <div className="tile-title">האילוצים שלי</div>
              <div className="tile-subtitle">
                צפייה ועריכה של אילוצים שנשלחו
              </div>
            </button>

            {/* מערכת שעות */}
            <button className="tile-card tile-purple">
              <div className="tile-icon">📅</div>
              <div className="tile-title">מערכת שעות</div>
              <div className="tile-subtitle">
                תצוגת כל השיבוצים לסמסטר
              </div>
            </button>

            {/* מידע */}
            <button className="tile-card tile-yellow">
              <div className="tile-icon">ℹ️</div>
              <div className="tile-title">מידע</div>
              <div className="tile-subtitle">
                סטטוס מערכת, דדלייןים והסברים
              </div>
            </button>
          </div>
        </section>
      </main>
    </div>
  );
}

export default LecturerDashboard;
