import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { RequireAuth } from "./components/RequireAuth";
import { Admin } from "./views/Admin";
import { AiLab } from "./views/AiLab";
import { Landing } from "./views/Landing";
import { Login } from "./views/Login";
import { MissionDetail } from "./views/MissionDetail";
import { Missions } from "./views/Missions";
import { NewMission } from "./views/NewMission";
import { Privacy } from "./views/Privacy";
import { Signup } from "./views/Signup";
import { Terms } from "./views/Terms";

export function AppRoutes() {
  return (
    <Routes>
      {/* Public marketing + auth + legal */}
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/privacy" element={<Privacy />} />
      <Route path="/terms" element={<Terms />} />

      {/* Authenticated console */}
      <Route element={<AppShell />}>
        <Route
          path="/missions"
          element={
            <RequireAuth minRole="viewer">
              <Missions />
            </RequireAuth>
          }
        />
        <Route
          path="/missions/new"
          element={
            <RequireAuth minRole="operator">
              <NewMission />
            </RequireAuth>
          }
        />
        <Route
          path="/missions/:id"
          element={
            <RequireAuth minRole="viewer">
              <MissionDetail />
            </RequireAuth>
          }
        />
        <Route
          path="/ai-lab"
          element={
            <RequireAuth minRole="operator">
              <AiLab />
            </RequireAuth>
          }
        />
        <Route
          path="/admin"
          element={
            <RequireAuth minRole="viewer">
              <Admin />
            </RequireAuth>
          }
        />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
