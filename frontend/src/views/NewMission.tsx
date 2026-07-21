import { Navigate } from "react-router-dom";

/** Bookmark-safe: manual form lives on /missions?mode=manual */
export function NewMission() {
  return <Navigate to="/missions?mode=manual" replace />;
}
