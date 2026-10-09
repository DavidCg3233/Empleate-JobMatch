import { http } from "./http.js";

export function login(email, password) {
  return http("/auth/login", { method: "POST", body: { email, password }, auth: false });
}