const TOKEN_KEY = "aesthetica_token";
const USER_KEY = "aesthetica_user";

export const authStore = {
  getToken(): string | null {
    return localStorage.getItem(TOKEN_KEY);
  },
  setToken(token: string): void {
    localStorage.setItem(TOKEN_KEY, token);
  },
  clear(): void {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },
  getUserId(): string | null {
    return localStorage.getItem(USER_KEY);
  },
  setUserId(userId: string): void {
    localStorage.setItem(USER_KEY, userId);
  },
};
