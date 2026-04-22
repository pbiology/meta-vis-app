import client from "./client";

export async function login(username, password) {
  // FastAPI OAuth2PasswordRequestForm expects form data, not JSON
  const formData = new URLSearchParams();
  formData.append("username", username);
  formData.append("password", password);

  const res = await client.post("/auth/login", formData, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  return res.data;
}

export async function getMe() {
  const res = await client.get("/auth/me");
  return res.data;
}
