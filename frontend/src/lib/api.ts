import axios from "axios";

export const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "https://clickbuild.com/api/v1",
  timeout: 30000,
});

// Auto refresh token on 401
api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      try {
        const { useAuthStore } = await import("@/store/auth");
        const { refreshToken, setTokens, logout } = useAuthStore.getState();
        if (!refreshToken) { logout(); return Promise.reject(error); }

        const res = await axios.post(
          `${process.env.NEXT_PUBLIC_API_URL}/auth/refresh`,
          { refresh_token: refreshToken }
        );
        setTokens(res.data.access_token, res.data.refresh_token, res.data.user);
        original.headers["Authorization"] = `Bearer ${res.data.access_token}`;
        return api(original);
      } catch {
        const { useAuthStore } = await import("@/store/auth");
        useAuthStore.getState().logout();
      }
    }
    return Promise.reject(error);
  }
);
