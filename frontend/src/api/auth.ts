import client from "./client";
import type { LoginResponse, User } from "./types";

export async function login(username: string, password: string): Promise<LoginResponse> {
  // FastAPI OAuth2PasswordRequestForm expects form data, not JSON
  const formData = new URLSearchParams();
  formData.append("username", username);
  formData.append("password", password);

  const res = await client.post<LoginResponse>("/auth/login", formData, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  return res.data;
}

export async function getMe(): Promise<User> {
  const res = await client.get<User>("/auth/me");
  return res.data;
}
