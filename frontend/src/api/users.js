import client from "./client";

export async function getUsers() {
  const res = await client.get("/users");
  return res.data;
}

export async function createUser(username, password, role) {
  const res = await client.post("/users", { username, password, role });
  return res.data;
}

export async function updateUserRole(username, role) {
  const res = await client.patch(`/users/${username}/role`, { role });
  return res.data;
}

export async function updateUserPassword(username, password) {
  const res = await client.patch(`/users/${username}/password`, { password });
  return res.data;
}

export async function deleteUser(username) {
  const res = await client.delete(`/users/${username}`);
  return res.data;
}

export async function getMyStats() {
  const res = await client.get("/users/me/stats");
  return res.data;
}
