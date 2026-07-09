const THEME_TRANSITION_CLASS = "theme-transitioning";
const THEME_FADE_CLASS = "theme-fading";
const THEME_TRANSITION_SUPPRESSION_MS = 120;
const THEME_FADE_MS = 170;

let transitionTimeout: number | undefined;
let fadeTimeout: number | undefined;
let transitionFrame: number | undefined;

export function withThemeTransition(changeTheme: () => void) {
  if (typeof document === "undefined") {
    changeTheme();
    return;
  }

  const root = document.documentElement;
  root.classList.add(THEME_TRANSITION_CLASS);
  root.classList.remove(THEME_FADE_CLASS);
  window.clearTimeout(transitionTimeout);
  window.clearTimeout(fadeTimeout);
  if (transitionFrame !== undefined) {
    window.cancelAnimationFrame(transitionFrame);
  }

  // Theme token swaps touch most of the page, so suppress transitions for one paint.
  void root.offsetHeight;
  root.classList.add(THEME_FADE_CLASS);
  changeTheme();

  transitionFrame = window.requestAnimationFrame(() => {
    transitionFrame = window.requestAnimationFrame(() => {
      root.classList.remove(THEME_TRANSITION_CLASS);
      transitionFrame = undefined;
    });
  });

  transitionTimeout = window.setTimeout(() => {
    root.classList.remove(THEME_TRANSITION_CLASS);
    transitionFrame = undefined;
  }, THEME_TRANSITION_SUPPRESSION_MS);

  fadeTimeout = window.setTimeout(() => {
    root.classList.remove(THEME_FADE_CLASS);
  }, THEME_FADE_MS);
}
