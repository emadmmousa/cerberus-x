import { useState } from "react";
import { ExploitOps } from "./views/ExploitOps";
import { MissionControl } from "./views/MissionControl";
import { MsfConsole } from "./views/MsfConsole";

type View = "mission" | "exploit" | "console";

const TABS: { id: View; label: string }[] = [
  { id: "mission", label: "Mission Control" },
  { id: "exploit", label: "Exploit Ops" },
  { id: "console", label: "MSF Console" },
];

export default function App() {
  const [view, setView] = useState<View>("mission");
  const [target, setTarget] = useState("");

  return (
    <div className="app-shell">
      <nav className="app-nav">
        <span className="app-nav__brand">CERBERUS-X</span>
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`app-nav__tab${view === tab.id ? " app-nav__tab--active" : ""}`}
            onClick={() => setView(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>
      <main className="app-main">
        {view === "mission" && (
          <MissionControl target={target} onTargetChange={setTarget} />
        )}
        {view === "exploit" && <ExploitOps />}
        {view === "console" && <MsfConsole />}
      </main>
    </div>
  );
}
