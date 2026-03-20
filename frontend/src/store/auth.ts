import { clearAccessToken, getAccessToken, setAccessToken } from "../api/client";

export const authStore = {
  getToken: getAccessToken,
  setToken: setAccessToken,
  clearToken: clearAccessToken
};
