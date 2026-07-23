import { useEffect, useState } from "react";

/** True when the document tab is visible — use to pause background polling. */
export function usePageVisible(): boolean {
  const [visible, setVisible] = useState(
    () => typeof document !== "undefined" && document.visibilityState === "visible",
  );

  useEffect(() => {
    const onChange = () => setVisible(document.visibilityState === "visible");
    document.addEventListener("visibilitychange", onChange);
    return () => document.removeEventListener("visibilitychange", onChange);
  }, []);

  return visible;
}
