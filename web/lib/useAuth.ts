"use client";

import { createContext, useContext } from "react";

export interface Counselor {
  counselor_id: number;
  name: string;
  email: string;
}

export interface AuthContextValue {
  counselor: Counselor | null;
  isLoggedIn: boolean;
  loading: boolean;
  login: (token: string, counselor: Counselor) => void;
  logout: () => void;
}

export const TOKEN_KEY = "edupath_token";

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export const AuthContext = createContext<AuthContextValue>({
  counselor: null,
  isLoggedIn: false,
  loading: true,
  login: () => {},
  logout: () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}
