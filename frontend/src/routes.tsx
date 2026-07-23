import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { PageLoader } from "./components/PageLoader";
import { RequireAuth } from "./components/RequireAuth";
import { Landing } from "./views/Landing";
import { Login } from "./views/Login";
import { Privacy } from "./views/Privacy";
import { Signup } from "./views/Signup";
import { Terms } from "./views/Terms";

const Admin = lazy(() => import("./views/Admin").then((m) => ({ default: m.Admin })));
const AiLab = lazy(() => import("./views/AiLab").then((m) => ({ default: m.AiLab })));
const MissionDetail = lazy(() =>
  import("./views/MissionDetail").then((m) => ({ default: m.MissionDetail })),
);
const Missions = lazy(() => import("./views/Missions").then((m) => ({ default: m.Missions })));
const Profile = lazy(() => import("./views/Profile").then((m) => ({ default: m.Profile })));
const NewMission = lazy(() =>
  import("./views/NewMission").then((m) => ({ default: m.NewMission })),
);

function Lazy({ children }: { children: ReactNode }) {
  return <Suspense fallback={<PageLoader />}>{children}</Suspense>;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/privacy" element={<Privacy />} />
      <Route path="/terms" element={<Terms />} />

      <Route element={<AppShell />}>
        <Route
          path="/missions"
          element={
            <RequireAuth minRole="viewer">
              <Lazy>
                <Missions />
              </Lazy>
            </RequireAuth>
          }
        />
        <Route
          path="/missions/new"
          element={
            <RequireAuth minRole="operator">
              <Lazy>
                <NewMission />
              </Lazy>
            </RequireAuth>
          }
        />
        <Route
          path="/missions/:id"
          element={
            <RequireAuth minRole="viewer">
              <Lazy>
                <MissionDetail />
              </Lazy>
            </RequireAuth>
          }
        />
        <Route
          path="/profile"
          element={
            <RequireAuth minRole="viewer">
              <Lazy>
                <Profile />
              </Lazy>
            </RequireAuth>
          }
        />
        <Route
          path="/ai-lab"
          element={
            <RequireAuth minRole="operator">
              <Lazy>
                <AiLab />
              </Lazy>
            </RequireAuth>
          }
        />
        <Route
          path="/ai-lab/:section"
          element={
            <RequireAuth minRole="operator">
              <Lazy>
                <AiLab />
              </Lazy>
            </RequireAuth>
          }
        />
        <Route
          path="/admin"
          element={
            <RequireAuth minRole="viewer">
              <Lazy>
                <Admin />
              </Lazy>
            </RequireAuth>
          }
        />
        <Route
          path="/admin/:section"
          element={
            <RequireAuth minRole="viewer">
              <Lazy>
                <Admin />
              </Lazy>
            </RequireAuth>
          }
        />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
