"use client";

import { useEffect, useState } from "react";
import { AppHelpDialog } from "@/components/app-help-dialog";

const GUIDE_VERSION = "1";
const GUIDE_STORAGE_KEY = "finance-guide-version";

/** Opens the quick guide once per browser profile, after the app is unlocked. */
export function FirstRunGuide() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let frameId: number | undefined;

    try {
      if (window.localStorage.getItem(GUIDE_STORAGE_KEY) === GUIDE_VERSION) {
        return;
      }

      // Mark before opening so refreshes and lock/unlock remounts do not reopen it.
      window.localStorage.setItem(GUIDE_STORAGE_KEY, GUIDE_VERSION);
      frameId = window.requestAnimationFrame(() => setOpen(true));
    } catch {
      // The manual entry point in Settings remains available.
    }

    return () => {
      if (frameId !== undefined) window.cancelAnimationFrame(frameId);
    };
  }, []);

  return <AppHelpDialog open={open} onOpenChange={setOpen} />;
}
