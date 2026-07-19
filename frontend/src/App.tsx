import { useState } from "react";
import { EventLog } from "./views/EventLog";
import { ExploitOps } from "./views/ExploitOps";
import { Findings } from "./views/Findings";
import { MissionLaunch } from "./views/MissionLaunch";
import { MsfConsole } from "./views/MsfConsole";

type View = "mission" | "findings" | "exploit" | "console" | "events";

const TABS: { id: View; label: string }[] = [
  { id: "mission", label: "Mission" },
  { id: "findings", label: "Findings" },
  { id: "exploit", label: "Exploit Ops" },
  { id: "console", label: "MSF Console" },
  { id: "events", label: "Event Log" },
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
          <MissionLaunch target={target} onTargetChange={setTarget} />
        )}
        {view === "findings" && (
          <Findings target={target} onTargetChange={setTarget} />
        )}
        {view === "exploit" && <ExploitOps />}
        {view === "console" && <MsfConsole />}
        {view === "events" && <EventLog />}
      </main>
    </div>
  );
}
