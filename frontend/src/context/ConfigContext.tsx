import { createContext, useContext, useEffect, useMemo, useState, ReactNode } from "react";
import { fetchAppConfig } from "../api/config";

// Fallback used during the initial fetch so TaxonomyTable renders correctly
// before the server responds. Values must stay in sync with constants.py.
const FALLBACK_HOST_IDS = new Set<number>([0, 1, 131567, 9606]);

interface ConfigContextValue {
  hostTaxonIds: Set<number>;
}

const ConfigContext = createContext<ConfigContextValue>({ hostTaxonIds: FALLBACK_HOST_IDS });

export function ConfigProvider({ children }: Readonly<{ children: ReactNode }>) {
  const [hostTaxonIds, setHostTaxonIds] = useState<Set<number>>(FALLBACK_HOST_IDS);

  useEffect(() => {
    fetchAppConfig()
      .then((cfg) => setHostTaxonIds(new Set(cfg.host_taxon_ids)))
      .catch(() => {
        // Server unreachable — keep the fallback so the UI stays functional.
      });
  }, []);

  const value = useMemo(() => ({ hostTaxonIds }), [hostTaxonIds]);

  return <ConfigContext.Provider value={value}>{children}</ConfigContext.Provider>;
}

export function useAppConfig(): ConfigContextValue {
  return useContext(ConfigContext);
}
