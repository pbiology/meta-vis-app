import { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { useDisplayFilterIds, useTaxonLists } from "../../hooks/queries/useTaxonLists";
import type { TaxonListSummary } from "../../api/types";

const NO_IDS: ReadonlySet<number> = new Set();

export interface DisplayFilters {
  /** Every display-filter list, for the menu. */
  lists: TaxonListSummary[];
  /** The user's active list ids (their saved preference). */
  activeIds: string[];
  activeLists: TaxonListSummary[];
  setActiveIds: (next: string[]) => Promise<void>;
  /** Taxa to hide now: empty while paused, loading or failed. */
  hiddenIds: ReadonlySet<number>;
  isError: boolean;
  /** "Show all" for this table only; the saved preference is untouched. */
  paused: boolean;
  setPaused: (paused: boolean) => void;
}

/** The user's display-filter state for one taxonomy table. */
export function useDisplayFilters(): DisplayFilters {
  const { preferences, setPreferences } = useAuth();
  const [paused, setPaused] = useState(false);
  const listsQ = useTaxonLists("display_filter");
  const activeIds = preferences.active_display_filters ?? [];
  const { hiddenIds, isError } = useDisplayFilterIds(activeIds);

  const lists = listsQ.data ?? [];
  return {
    lists,
    activeIds,
    activeLists: lists.filter((l) => activeIds.includes(l.list_id)),
    setActiveIds: (next) => setPreferences({ active_display_filters: next }),
    hiddenIds: paused ? NO_IDS : hiddenIds,
    isError: isError || listsQ.isError,
    paused,
    setPaused,
  };
}
