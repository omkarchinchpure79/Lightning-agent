"use client";

import { useState, useEffect, useCallback, type ReactNode } from "react";
import { AuthContext, TOKEN_KEY, type Counselor } from "./useAuth";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const COOKIE_MAX_AGE_DAYS = 30;

function setCookie(token: string) {
  document.cookie = `edupath_token=${token}; path=/; max-age=${COOKIE_MAX_AGE_DAYS * 86400}; SameSite=Lax`;
}

function clearCookie() {
  document.cookie = "edupath_token=; path=/; max-age=0";
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [counselor, setCounselor] = useState<Counselor | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) { clearCookie(); setLoading(false); return; }

    // Middleware only checks for cookie presence — keep it in sync with localStorage.
    setCookie(token);

    fetch(`${BASE}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data) setCounselor(data as Counselor);
        else {
          localStorage.removeItem(TOKEN_KEY);
          clearCookie();
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback((token: string, c: Counselor) => {
    localStorage.setItem(TOKEN_KEY, token);
    setCookie(token);
    setCounselor(c);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    clearCookie();
    setCounselor(null);
  }, []);

  return (
    <AuthContext.Provider value={{ counselor, isLoggedIn: !!counselor, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
