"use client";

import {
  useCallback,
  useSyncExternalStore,
  type Dispatch,
  type SetStateAction,
} from "react";

type StoredValue = string | number | boolean;
type Validator<T extends StoredValue> = (value: unknown) => value is T;
type Options<T extends StoredValue> = { validate?: Validator<T> };
type StoredState<T extends StoredValue> = [T, Dispatch<SetStateAction<T>>];

const LOCAL_STORAGE_EVENT = "finance:local-storage-change";
const memoryValues = new Map<string, StoredValue>();

export function useLocalStorageState<T extends StoredValue>(
  key: string,
  defaultValue: T,
  options: { validate: Validator<T> },
): StoredState<T>;
export function useLocalStorageState(
  key: string,
  defaultValue: string,
  options?: Options<string>,
): StoredState<string>;
export function useLocalStorageState(
  key: string,
  defaultValue: number,
  options?: Options<number>,
): StoredState<number>;
export function useLocalStorageState(
  key: string,
  defaultValue: boolean,
  options?: Options<boolean>,
): StoredState<boolean>;
export function useLocalStorageState<T extends StoredValue>(
  key: string,
  defaultValue: T,
  options?: Options<T>,
): StoredState<T> {
  const validate = options?.validate;
  const read = useCallback(
    () => readStoredValue(key, defaultValue, validate),
    [defaultValue, key, validate],
  );
  const subscribe = useCallback(
    (onStoreChange: () => void) => {
      const onStorage = (event: StorageEvent) => {
        if (event.key === key) {
          memoryValues.delete(key);
          onStoreChange();
        }
      };
      const onLocalChange = (event: Event) => {
        if ((event as CustomEvent<string>).detail === key) onStoreChange();
      };

      window.addEventListener("storage", onStorage);
      window.addEventListener(LOCAL_STORAGE_EVENT, onLocalChange);
      return () => {
        window.removeEventListener("storage", onStorage);
        window.removeEventListener(LOCAL_STORAGE_EVENT, onLocalChange);
      };
    },
    [key],
  );
  const value = useSyncExternalStore(subscribe, read, () => defaultValue);

  const setValue = useCallback<Dispatch<SetStateAction<T>>>(
    (nextValue) => {
      const currentValue = read();
      const resolved =
        typeof nextValue === "function"
          ? (nextValue as (current: T) => T)(currentValue)
          : nextValue;
      const safeValue = isValidValue(resolved, defaultValue, validate)
        ? resolved
        : defaultValue;

      memoryValues.set(key, safeValue);
      try {
        window.localStorage.setItem(key, JSON.stringify(safeValue));
      } catch {
        // Storage can be unavailable in private browsing or locked-down webviews.
      }
      window.dispatchEvent(
        new CustomEvent<string>(LOCAL_STORAGE_EVENT, { detail: key }),
      );
    },
    [defaultValue, key, read, validate],
  );

  return [value, setValue];
}

export function storedValueOneOf<const T extends StoredValue>(
  values: readonly T[],
): Validator<T> {
  return (value: unknown): value is T => values.includes(value as T);
}

export function storedNumberBetween(min: number, max: number): Validator<number> {
  return (value: unknown): value is number =>
    typeof value === "number" &&
    Number.isFinite(value) &&
    value >= min &&
    value <= max;
}

function readStoredValue<T extends StoredValue>(
  key: string,
  defaultValue: T,
  validate?: Validator<T>,
): T {
  const memoryValue = memoryValues.get(key);
  if (isValidValue(memoryValue, defaultValue, validate)) return memoryValue;

  try {
    const stored = window.localStorage.getItem(key);
    if (stored === null) return defaultValue;
    const parsed: unknown = JSON.parse(stored);
    return isValidValue(parsed, defaultValue, validate) ? parsed : defaultValue;
  } catch {
    return defaultValue;
  }
}

function isValidValue<T extends StoredValue>(
  value: unknown,
  defaultValue: T,
  validate?: Validator<T>,
): value is T {
  if (validate) return validate(value);
  if (typeof value !== typeof defaultValue) return false;
  return typeof value !== "number" || Number.isFinite(value);
}
