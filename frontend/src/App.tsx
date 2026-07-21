import { BrowserRouter } from "react-router-dom";
import { AuthProvider } from "./providers/AuthProvider";
import { ThemeProvider } from "./providers/ThemeProvider";
import { AppRoutes } from "./routes";
import { applyTheme, resolveInitialTheme } from "./lib/theme";

// Avoid flash of wrong theme before React mounts.
applyTheme(resolveInitialTheme());

export default function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}
