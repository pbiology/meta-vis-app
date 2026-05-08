# `hooks/queries`

Centralised TanStack Query hooks. All read/write data access in `pages/` and
`components/` should go through this directory — never call `api/*.ts` directly
from a component.

## Why

- **No silent errors.** Every read returns `{ data, isLoading, isError }`; the
  page surfaces `isError` (e.g. via `<DataWarning />`). The legacy
  `useEffect + .catch(() => {})` pattern is banned.
- **Consistent cache keys.** A single source of truth for query keys means
  invalidation after mutations is reliable. No more `["sample", id]` in one
  file and `["samples", id]` in another.
- **Mutations invalidate, not duplicate.** Mutations call
  `queryClient.invalidateQueries({ queryKey: domainKeys.all })` so the next
  read refetches; we do not maintain parallel `useState` lists alongside the
  cache.

## Conventions

### Files

One file per backend domain — matches `frontend/src/api/*.ts`. Add a new file
when adding a new domain; do not group unrelated resources.

### Key factories

Each file exports a `xxxKeys` object whose methods build the query key arrays.
Components must use these — never write `["sample", id]` inline.

```ts
export const sampleKeys = {
  all: ["samples"] as const,
  list: (params: GetSamplesParams) => ["samples", "list", params] as const,
  detail: (id: string) => ["samples", "detail", id] as const,
  profile: (id: string) => ["samples", id, "profile"] as const,
};
```

The `all` key is the broad invalidation target — passing it to
`invalidateQueries` invalidates every query whose key starts with `["samples"]`.

### Query hooks

Thin wrappers around `useQuery`. Default `enabled` is true; expose an `enabled`
option for queries that depend on prior results.

```ts
export function useSample(sampleId: string) {
  return useQuery({
    queryKey: sampleKeys.detail(sampleId),
    queryFn: () => getSample(sampleId),
  });
}
```

### Mutation hooks

Thin wrappers around `useMutation` that invalidate the relevant domain on
success. No optimistic updates — we do not have a rollback story today, and
clinical UIs should reflect server truth, not optimistic guesses.

```ts
export function useDeleteCase() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (caseId: string) => deleteCase(caseId),
    onSuccess: () => qc.invalidateQueries({ queryKey: caseKeys.all }),
  });
}
```

If a mutation affects multiple domains (e.g. ignorelist add invalidates both
`alerts` and `outbreaks`), invalidate each in `onSuccess`.

## Error rendering

Pages render an inline error UI when `isError` is true. Reuse the
`DataWarning` component in `SampleDetailContent.tsx` for warning-level
errors (page still partially usable) or a centred error block for
unrecoverable load failures. Never swallow the error.

## Defaults

Global defaults come from `src/queryClient.ts` — 5 min `staleTime`, retry once,
no refetch on window focus. Do not override unless you have a specific reason
documented in a comment.
