const THEME_TRANSITION_CLASS = "theme-transitioning";
const THEME_OVERLAY_CLASS = "theme-overlaying";
const THEME_TRANSITION_SUPPRESSION_MS = 120;
const THEME_OVERLAY_MS = 180;

let transitionTimeout: number | undefined;
let overlayTimeout: number | undefined;
let transitionFrame: number | undefined;

function themeSignature(root: HTMLElement) {
  const classes = root.className
    .split(/\s+/)
    .filter(Boolean)
    .filter(
      (className) =>
        className !== THEME_TRANSITION_CLASS &&
        className !== THEME_OVERLAY_CLASS,
    )
    .sort()
    .join(" ");

  return [
    classes,
    root.style.colorScheme,
  ].join("|");
}

export function withThemeTransition(changeTheme: () => void) {
  if (typeof document === "undefined") {
    changeTheme();
    return;
  }

  const root = document.documentElement;
  root.classList.add(THEME_TRANSITION_CLASS);
  root.classList.remove(THEME_OVERLAY_CLASS);
  window.clearTimeout(transitionTimeout);
  window.clearTimeout(overlayTimeout);
  if (transitionFrame !== undefined) {
    window.cancelAnimationFrame(transitionFrame);
  }

  const signatureBefore = themeSignature(root);
  let overlayStarted = false;
  const startOverlay = () => {
    if (overlayStarted) return;
    overlayStarted = true;
    root.classList.remove(THEME_OVERLAY_CLASS);
    void root.offsetHeight;
    root.classList.add(THEME_OVERLAY_CLASS);
    overlayTimeout = window.setTimeout(() => {
      root.classList.remove(THEME_OVERLAY_CLASS);
    }, THEME_OVERLAY_MS);
  };
  const observer = new MutationObserver(() => {
    if (themeSignature(root) !== signatureBefore) {
      observer.disconnect();
      startOverlay();
    }
  });
  observer.observe(root, {
    attributes: true,
    attributeFilter: ["class", "style"],
  });

  // Theme token swaps touch most of the page, so suppress transitions for one paint.
  void root.offsetHeight;
  changeTheme();
  if (themeSignature(root) !== signatureBefore) {
    observer.disconnect();
    startOverlay();
  } else {
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        observer.disconnect();
        startOverlay();
      });
    });
  }

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
}
