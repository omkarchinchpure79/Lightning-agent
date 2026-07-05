"use client";

/**
 * College Compare — a lightweight, session-style "add to compare" list
 * (same interaction model as 91mobiles' phone-compare tray: pick 2-4 items
 * from anywhere in the app, a floating tray tracks the picks, "Compare Now"
 * opens a side-by-side page). Deliberately localStorage-only, not tied to a
 * counsellor account or student profile — this is a quick lookup tool, not
 * saved advising output (that's what Bookmarks/Shortlist are for).
 */

import { useState, useEffect, useCallback } from "react";

export interface CompareCollege {
  code: string;
  name: string;
}

export const MAX_COMPARE = 4;
export const MIN_COMPARE = 2;

const STORAGE_KEY = "edupath_compare_v1";
const SYNC_EVENT = "edupath_compare_sync";

export function readCompareList(): CompareCollege[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as CompareCollege[]) : [];
  } catch {
    return [];
  }
}

function writeCompareList(items: CompareCollege[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    window.dispatchEvent(new CustomEvent(SYNC_EVENT));
  } catch {
    /* storage unavailable — no-op */
  }
}

export function useCompare() {
  const [items, setItems] = useState<CompareCollege[]>([]);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setItems(readCompareList());
    setHydrated(true);
    const onSync = () => setItems(readCompareList());
    window.addEventListener("storage", onSync);
    window.addEventListener(SYNC_EVENT, onSync);
    return () => {
      window.removeEventListener("storage", onSync);
      window.removeEventListener(SYNC_EVENT, onSync);
    };
  }, []);

  const add = useCallback((college: CompareCollege) => {
    const current = readCompareList();
    if (current.some((c) => c.code === college.code)) return;
    if (current.length >= MAX_COMPARE) return;
    writeCompareList([...current, college]);
  }, []);

  const remove = useCallback((code: string) => {
    writeCompareList(readCompareList().filter((c) => c.code !== code));
  }, []);

  const toggle = useCallback((college: CompareCollege) => {
    const current = readCompareList();
    if (current.some((c) => c.code === college.code)) {
      writeCompareList(current.filter((c) => c.code !== college.code));
    } else if (current.length < MAX_COMPARE) {
      writeCompareList([...current, college]);
    }
  }, []);

  const clear = useCallback(() => writeCompareList([]), []);

  const isComparing = useCallback(
    (code: string) => items.some((c) => c.code === code),
    [items]
  );

  return {
    items,
    add,
    remove,
    toggle,
    clear,
    isComparing,
    count: items.length,
    canAddMore: items.length < MAX_COMPARE,
    hydrated,
  };
}
