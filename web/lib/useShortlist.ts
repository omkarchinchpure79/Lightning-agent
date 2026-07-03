"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "./useAuth";
import {
  getCounselorShortlist,
  addCollegeToShortlist,
  removeCollegeFromShortlist,
  type CounselorShortlistItem,
} from "./api";

export interface ShortlistCollege {
  code: string;
  name: string;
  city: string | null;
  score: number | null;
  institution_type: string | null;
  imageUrl: string | null;
}

// ── localStorage path (anonymous users) ──────────────────────────────────────

const STORAGE_KEY = "edupath_shortlist_v1";
const SYNC_EVENT = "edupath_shortlist_sync";

export function readLocalShortlist(): ShortlistCollege[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as ShortlistCollege[]) : [];
  } catch {
    return [];
  }
}

function writeLocalShortlist(items: ShortlistCollege[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    window.dispatchEvent(new CustomEvent(SYNC_EVENT));
  } catch {}
}

function apiItemToCollege(item: CounselorShortlistItem): ShortlistCollege {
  return {
    code: item.college_code,
    name: item.college_name ?? "",
    city: item.city,
    score: item.score,
    institution_type: item.institution_type,
    imageUrl: null,
  };
}

// ── Main hook ─────────────────────────────────────────────────────────────────

export function useShortlist() {
  const { isLoggedIn, loading: authLoading } = useAuth();
  const [items, setItems] = useState<ShortlistCollege[]>([]);
  const [apiLoaded, setApiLoaded] = useState(false);

  useEffect(() => {
    if (authLoading) return;

    if (isLoggedIn) {
      setApiLoaded(false);
      getCounselorShortlist()
        .then((rows) => {
          setItems(rows.map(apiItemToCollege));
          setApiLoaded(true);
        })
        .catch(() => setApiLoaded(true));
    } else {
      setItems(readLocalShortlist());

      const onSync = () => setItems(readLocalShortlist());
      window.addEventListener("storage", onSync);
      window.addEventListener(SYNC_EVENT, onSync);
      return () => {
        window.removeEventListener("storage", onSync);
        window.removeEventListener(SYNC_EVENT, onSync);
      };
    }
  }, [isLoggedIn, authLoading]);

  const toggle = useCallback(
    async (college: ShortlistCollege) => {
      if (isLoggedIn) {
        const exists = items.some((c) => c.code === college.code);
        if (exists) {
          setItems((prev) => prev.filter((c) => c.code !== college.code));
          await removeCollegeFromShortlist(college.code).catch(() => {
            setItems((prev) => [...prev, college]);
          });
        } else {
          setItems((prev) => [...prev, college]);
          await addCollegeToShortlist({
            college_code: college.code,
            college_name: college.name,
            city: college.city,
            score: college.score,
            institution_type: college.institution_type,
          }).catch(() => {
            setItems((prev) => prev.filter((c) => c.code !== college.code));
          });
        }
      } else {
        const current = readLocalShortlist();
        const exists = current.some((c) => c.code === college.code);
        const next = exists
          ? current.filter((c) => c.code !== college.code)
          : [...current, college];
        writeLocalShortlist(next);
        setItems(next);
      }
    },
    [isLoggedIn, items]
  );

  const remove = useCallback(
    async (code: string) => {
      if (isLoggedIn) {
        setItems((prev) => prev.filter((c) => c.code !== code));
        await removeCollegeFromShortlist(code).catch(() => {});
      } else {
        const next = readLocalShortlist().filter((c) => c.code !== code);
        writeLocalShortlist(next);
        setItems(next);
      }
    },
    [isLoggedIn]
  );

  const isSaved = useCallback(
    (code: string) => items.some((c) => c.code === code),
    [items]
  );

  return { items, toggle, remove, isSaved, count: items.length, apiLoaded };
}
