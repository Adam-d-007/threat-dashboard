import { useEffect, useState } from "react";

export type Theme = "dark" | "light";

const KEY = "theme";

function initial(): Theme {
  try {
    return localStorage.getItem(KEY) === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

/** Dark by default; the choice is remembered per browser when storage allows it. */
export function useTheme(): [Theme, (t: Theme) => void] {
  const [theme, setTheme] = useState<Theme>(initial);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem(KEY, theme);
    } catch {
      // Not remembering the choice is fine.
    }
  }, [theme]);
  return [theme, setTheme];
}
