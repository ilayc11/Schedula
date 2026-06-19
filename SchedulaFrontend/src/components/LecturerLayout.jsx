import { Outlet } from "react-router-dom";
import HeaderBar from "../components/HeaderBar";
import Sidebar from "../components/Sidebar";
import "../pages/HomePage/LecturerHome1.css";
import { useState } from "react";


// function LecturerLayout() {
//   const [sidebarOpen, setSidebarOpen] = useState(true);
//   return (
//     <div className="app-shell">
//       <HeaderBar />

//       <div className="main-layout">
//         <Sidebar
//           sidebarOpen={sidebarOpen}
//           onToggle={() => setSidebarOpen((v) => !v)}
//         />
//         <main className="main-content">
//           <Outlet />
//         </main>
//       </div>
//     </div>
//   );
// }

export default function LecturerLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(true);

  return (
    <div className={`app-shell ${sidebarOpen ? "" : "sidebar-collapsed"}`}>
      <HeaderBar />

      <div className="main-layout">
        <Sidebar
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