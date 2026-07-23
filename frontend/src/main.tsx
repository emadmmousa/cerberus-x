import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles/global.css";
import "./styles/prompt-deck.css";
import "./styles/chat-toolbar.css";
import "./styles/agent.css";
import "./styles/missions.css";
import "./styles/mission-detail.css";
import "./styles/admin.css";
import "./styles/profile.css";
import "./styles/pagination.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
