import { create } from "zustand";
import { persist } from "zustand/middleware";
import { api } from "@/lib/api";

interface User {
  id:       string;
  email:    string;
  name:     string;
  language: string;
  country:  string;
}

interface AuthState {
  user:         User | null;
  accessToken:  string | null;
  refreshToken: string | null;
  login:  (email: string, password: string) => Promise<void>;
  logout: () => void;
  setTokens: (access: string, refresh: string, user: User) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user:         null,
      accessToken:  null,
      refreshToken: null,

      setTokens: (access, refresh, user) => {
        set({ accessToken: access, refreshToken: refresh, user });
        api.defaults.headers.common["Authorization"] = `Bearer ${access}`;
      },

      login: async (email, password) => {
        const res = await api.post("/auth/login", { email, password });
        const { access_token, refresh_token, user } = res.data;
        get().setTokens(access_token, refresh_token, user);
      },

      logout: () => {
        set({ user: null, accessToken: null, refreshToken: null });
        delete api.defaults.headers.common["Authorization"];
      },
    }),
    {
      name: "clickbuild-auth",
      onRehydrateStorage: () => (state) => {
        if (state?.accessToken) {
          api.defaults.headers.common["Authorization"] = `Bearer ${state.accessToken}`;
        }
      },
    }
  )
);
