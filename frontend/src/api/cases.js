// src/api/cases.js

import client from "./client";

export async function getCases({
  page = 1,
  search = "",
  reviewed = null,
  analysisType = null,
} = {}) {
  const params = { page, search };
  if (reviewed && reviewed !== "all") {
    params.reviewed = reviewed;
  }
  if (analysisType && analysisType !== "all") {
    params.analysis_type = analysisType;
  }
  const res = await client.get("/cases", { params });
  return res.data;
}

export async function getCase(caseId) {
  const res = await client.get(`/cases/${caseId}`);
  return res.data;
}

export async function getCaseSamples(caseId, type = null) {
  const params = type ? { type } : {};
  const res = await client.get(`/cases/${caseId}/samples`, { params });
  return res.data;
}

export async function reviewCase(caseId, notes = null) {
  const res = await client.patch(`/cases/${caseId}/review`, { notes });
  return res.data;
}

export async function unreviewCase(caseId) {
  const res = await client.delete(`/cases/${caseId}/review`);
  return res.data;
}

export async function getCaseKronaUrl(caseId, classifier = "kraken2") {
  const resp = await client.get(`/cases/${caseId}/krona`, {
    params: { classifier },
    responseType: "blob",
  });
  return URL.createObjectURL(resp.data);
}

export async function addNote(caseId, text) {
  const res = await client.post(`/cases/${caseId}/notes`, { text });
  return res.data;
}

export async function deleteNote(caseId, noteIndex) {
  const res = await client.delete(`/cases/${caseId}/notes/${noteIndex}`);
  return res.data;
}

export async function deleteCase(caseId) {
  const res = await client.delete(`/cases/${caseId}`);
  return res.data;
}

export async function getCaseStats() {
  const res = await client.get("/cases/stats");
  return res.data;
}

export async function getPathogenCases() {
  const res = await client.get("/cases/pathogen_cases");
  return res.data;
}
