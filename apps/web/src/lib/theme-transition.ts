const THEME_TRANSITION_CLASS = "theme-transitioning";
const THEME_TRANSITION_MS = 190;

let transitionTimeout: number | undefined;

export function withThemeTransition(changeTheme: () => void) {
  if (typeof document === "undefined") {
    changeTheme();
    return;
  }

  const root = document.documentElement;
  root.classList.add(THEME_TRANSITION_CLASS);
  window.clearTimeout(transitionTimeout);
  changeTheme();
  transitionTimeout = window.setTimeout(() => {
    root.classList.remove(THEME_TRANSITION_CLASS);
  }, THEME_TRANSITION_MS);
}
