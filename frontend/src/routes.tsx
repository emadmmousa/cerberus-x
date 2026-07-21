import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { RequireAuth } from "./components/RequireAuth";
import { Admin } from "./views/Admin";
import { AiLab } from "./views/AiLab";
import { Login } from "./views/Login";
import { MissionDetail } from "./views/MissionDetail";
import { Missions } from "./views/Missions";
import { NewMission } from "./views/NewMission";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/missions" replace />} />
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
      <Route path="*" element={<Navigate to="/missions" replace />} />
    </Routes>
  );
}
