import { BrowserRouter } from "react-router-dom";
import { AuthProvider } from "./providers/AuthProvider";
import { ShellLayoutProvider } from "./providers/ShellLayoutProvider";
import { ThemeProvider } from "./providers/ThemeProvider";
import { AppRoutes } from "./routes";
import {
  applySidebarCollapsed,
  resolveInitialSidebarCollapsed,
} from "./lib/shellLayout";
import { applyTheme, resolveInitialTheme } from "./lib/theme";

// Avoid flash of wrong theme / sidebar width before React mounts.
applyTheme(resolveInitialTheme());
applySidebarCollapsed(resolveInitialSidebarCollapsed());

export default function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <ShellLayoutProvider>
          <AuthProvider>
            <AppRoutes />
          </AuthProvider>
        </ShellLayoutProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}
