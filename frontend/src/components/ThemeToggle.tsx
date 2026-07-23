import { useTheme } from "../providers/ThemeProvider";

type Props = {
  compact?: boolean;
};

export function ThemeToggle({ compact = false }: Props) {
  const { theme, toggle } = useTheme();
  const next = theme === "dark" ? "light" : "dark";

  return (
    <button
      type="button"
      className={`theme-toggle${compact ? " theme-toggle--compact" : ""}`}
      onClick={toggle}
      aria-label={`Switch to ${next} theme`}
      title={`Switch to ${next} theme`}
      aria-pressed={theme === "light"}
    >
      <span
        className={`theme-toggle__swatch theme-toggle__swatch--${theme}`}
        aria-hidden
      />
      {!compact && (
        <span className="theme-toggle__label">
          {theme === "dark" ? "Light" : "Dark"}
        </span>
      )}
    </button>
  );
}
