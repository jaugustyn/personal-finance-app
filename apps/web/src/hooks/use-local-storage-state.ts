"use client";

import { useEffect, useState, type Dispatch, type SetStateAction } from "react";

export function useLocalStorageState<T>(
  key: string,
  defaultValue: T,
): [T, Dispatch<SetStateAction<T>>] {
  const [value, setValue] = useState<T>(() => {
    if (typeof window === "undefined") return defaultValue;
    try {
      const stored = window.localStorage.getItem(key);
      return stored ? (JSON.parse(stored) as T) : defaultValue;
    } catch {
      return defaultValue;
    }
  });

  useEffect(() => {
    try {
      window.localStorage.setItem(key, JSON.stringify(value));
    } catch {
      // localStorage can be unavailable in private browsing or locked-down webviews.
    }
  }, [key, value]);

  return [value, setValue];
}
