import client from "./client";
import type { TaxonList, TaxonListEntry, TaxonListKind } from "./types";

export interface NewTaxonListEntry {
  taxonId: number;
  reason?: string | null;
  /** Only accepted by lists whose kind uses it; the backend rejects it elsewhere. */
  minReads?: number;
}

/** Fields present are changed; `reason: null` clears the reason. */
export interface TaxonListEntryChanges {
  reason?: string | null;
  minReads?: number;
}

function entriesPath(listId: string): string {
  return `/taxon-lists/${encodeURIComponent(listId)}/entries`;
}

export async function getTaxonLists(kind: TaxonListKind | null = null): Promise<TaxonList[]> {
  const res = await client.get<TaxonList[]>("/taxon-lists", { params: kind ? { kind } : {} });
  return res.data;
}

export async function getTaxonListEntries(
  listId: string,
  superkingdom: string | null = null
): Promise<TaxonListEntry[]> {
  const res = await client.get<TaxonListEntry[]>(entriesPath(listId), {
    params: superkingdom ? { superkingdom } : {},
  });
  return res.data;
}

export async function addTaxonListEntry(
  listId: string,
  { taxonId, reason, minReads }: NewTaxonListEntry
): Promise<TaxonListEntry> {
  const body: Record<string, unknown> = { taxon_id: taxonId };
  if (reason !== undefined) body.reason = reason;
  if (minReads !== undefined) body.min_reads = minReads;
  const res = await client.post<TaxonListEntry>(entriesPath(listId), body);
  return res.data;
}

export async function updateTaxonListEntry(
  listId: string,
  taxonId: number,
  { reason, minReads }: TaxonListEntryChanges
): Promise<TaxonListEntry> {
  // Only send keys the caller set: the backend treats a present `null` as "clear".
  const body: Record<string, unknown> = {};
  if (reason !== undefined) body.reason = reason;
  if (minReads !== undefined) body.min_reads = minReads;
  const res = await client.patch<TaxonListEntry>(`${entriesPath(listId)}/${taxonId}`, body);
  return res.data;
}

export async function removeTaxonListEntry(listId: string, taxonId: number): Promise<void> {
  await client.delete(`${entriesPath(listId)}/${taxonId}`);
}
