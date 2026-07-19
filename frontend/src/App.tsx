import { useState } from "react";
import { MissionControl } from "./views/MissionControl";

export default function App() {
  const [target, setTarget] = useState("");

  return (
    <div className="app-shell">
      <nav className="app-nav">
        <span className="app-nav__brand">CERBERUS-X</span>
      </nav>
      <main className="app-main">
        <MissionControl target={target} onTargetChange={setTarget} />
      </main>
    </div>
  );
}
