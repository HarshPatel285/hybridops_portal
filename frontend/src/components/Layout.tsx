import {
  BarChart3,
  Boxes,
  CirclePlay,
  FileText,
  Gauge,
  GitCompareArrows,
  Grid2X2,
  Leaf,
  Settings,
  SlidersHorizontal
} from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { BrandMark } from "./BrandMark";

const links = [
  ["/", "Overview", Gauge],
  ["/workloads", "Workload Forecast", BarChart3],
  ["/carbon", "Carbon Intelligence", Leaf],
  ["/scenarios", "Scenario Builder", SlidersHorizontal],
  ["/runs", "Optimization Runs", CirclePlay],
  ["/placements", "Task Placement", Grid2X2],
  ["/reports", "Reports", FileText]
] as const;

export function Layout() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <BrandMark />
        <nav>
          {links.map(([path, label, Icon]) => (
            <NavLink key={path} to={path} end={path === "/"}>
              <Icon size={20} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <NavLink className="admin-link" to="/admin">
          <Settings size={20} />
          <span>Admin Configuration</span>
        </NavLink>
      </aside>
      <main className="workspace">
        <header className="topbar">
          <div className="topbar-title">
            <Boxes size={18} />
            <span>Hybrid Mainframe-Cloud Platform</span>
          </div>
          <div className="topbar-actions">
            <button className="icon-button" title="Compare scenarios"><GitCompareArrows size={19} /></button>
            <div className="avatar">HP</div>
            <span className="user-name">Administrator</span>
          </div>
        </header>
        <div className="page-container">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

