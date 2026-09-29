import client from "./client";
import type {
  BulkAddReport,
  TaxonList,
  TaxonListEntry,
  TaxonListEntryPage,
  TaxonListKind,
  TaxonListSummary,
} from "./types";

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
  return `${listPath(listId)}/entries`;
}

export interface NewTaxonList {
  kind: TaxonListKind;
  name: string;
  description?: string | null;
}

/** Fields present are changed; `description: null` clears it. */
export interface TaxonListChanges {
  name?: string;
  description?: string | null;
}

function listPath(listId: string): string {
  return `/taxon-lists/${encodeURIComponent(listId)}`;
}

export async function getTaxonLists(
  kind: TaxonListKind | null = null
): Promise<TaxonListSummary[]> {
  const res = await client.get<TaxonListSummary[]>("/taxon-lists", {
    params: kind ? { kind } : {},
  });
  return res.data;
}

export async function createTaxonList(list: NewTaxonList): Promise<TaxonList> {
  const res = await client.post<TaxonList>("/taxon-lists", list);
  return res.data;
}

export async function updateTaxonList(
  listId: string,
  changes: TaxonListChanges
): Promise<TaxonList> {
  const res = await client.patch<TaxonList>(listPath(listId), changes);
  return res.data;
}

export async function deleteTaxonList(listId: string): Promise<void> {
  await client.delete(listPath(listId));
}

/** Largest page the backend serves (routers/taxon_lists.py MAX_ENTRIES_PAGE). */
export const MAX_ENTRIES_PAGE = 10_000;

export interface EntryPageParams {
  offset?: number;
  limit?: number;
  /** Taxon id, or part of the name. */
  q?: string | null;
  superkingdom?: string | null;
}

export async function getTaxonListEntryPage(
  listId: string,
  { offset = 0, limit = 100, q = null, superkingdom = null }: EntryPageParams = {}
): Promise<TaxonListEntryPage> {
  const params: Record<string, unknown> = { offset, limit };
  if (q) params.q = q;
  if (superkingdom) params.superkingdom = superkingdom;
  const res = await client.get<TaxonListEntryPage>(entriesPath(listId), { params });
  return res.data;
}

/** Thrown instead of returning part of a list that exceeds one full page. */
export class TaxonListTooLargeError extends Error {
  constructor(listId: string, total: number) {
    super(
      `List ${listId} has ${total} taxa — more than the ${MAX_ENTRIES_PAGE} this view can show.`
    );
    this.name = "TaxonListTooLargeError";
  }
}

/**
 * Every entry of a list, for views that need them all at once. Fails rather
 * than return a partial list when the list is larger than one page.
 */
export async function getAllTaxonListEntries(
  listId: string,
  superkingdom: string | null = null
): Promise<TaxonListEntry[]> {
  const page = await getTaxonListEntryPage(listId, { limit: MAX_ENTRIES_PAGE, superkingdom });
  if (page.total > page.items.length) throw new TaxonListTooLargeError(listId, page.total);
  return page.items;
}

/** Every taxon id on a list, uncapped. */
export async function getTaxonListTaxonIds(listId: string): Promise<number[]> {
  const res = await client.get<{ taxon_ids: number[] }>(`${listPath(listId)}/taxon-ids`);
  return res.data.taxon_ids;
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

export interface BulkAddTaxonListEntries {
  taxonIds: number[];
  reason?: string | null;
  /** Preview only: report where each id would go without writing anything. */
  dryRun: boolean;
}

/**
 * Add many taxa at once. A real run is all-or-nothing: if any id would be
 * rejected the backend answers 422 with a fresh report and writes nothing.
 */
export async function bulkAddTaxonListEntries(
  listId: string,
  { taxonIds, reason, dryRun }: BulkAddTaxonListEntries
): Promise<BulkAddReport> {
  const body: Record<string, unknown> = { taxon_ids: taxonIds, dry_run: dryRun };
  if (reason !== undefined) body.reason = reason;
  const res = await client.post<BulkAddReport>(`${entriesPath(listId)}/bulk`, body);
  return res.data;
}
