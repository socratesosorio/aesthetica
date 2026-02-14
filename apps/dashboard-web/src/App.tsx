import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { authStore } from "./lib/auth";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { LoginPage } from "./pages/LoginPage";
import { LookDetailPage } from "./pages/LookDetailPage";
import { LooksPage } from "./pages/LooksPage";
import { ProfilePage } from "./pages/ProfilePage";

function RequireAuth({ children }: { children: JSX.Element }) {
  const token = authStore.getToken();
  if (!token) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<Navigate to="/looks" replace />} />
        <Route path="looks" element={<LooksPage />} />
        <Route path="looks/:id" element={<LookDetailPage />} />
        <Route path="profile" element={<ProfilePage />} />
        <Route path="analytics" element={<AnalyticsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/looks" replace />} />
    </Routes>
  );
}
