import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { authStore } from "../lib/auth";

export function Layout() {
  const navigate = useNavigate();

  return (
    <div className="app-shell">
      <header className="topbar">
        <Link to="/looks" className="brand">
          Aesthetica
        </Link>
        <button
          className="ghost-btn"
          onClick={() => {
            authStore.clear();
            navigate("/login");
          }}
        >
          Logout
        </button>
      </header>

      <main className="content">
        <Outlet />
      </main>

      <nav className="tabbar">
        <NavLink to="/looks">Looks</NavLink>
        <NavLink to="/profile">Profile</NavLink>
        <NavLink to="/analytics">Analytics</NavLink>
      </nav>
    </div>
  );
}
