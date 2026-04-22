import { QueryClient } from "@tanstack/react-query";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 min — clinical data doesn't change frequently
      retry: 1, // one retry on transient failure
      refetchOnWindowFocus: false, // clinical app, don't surprise users
    },
  },
});

export default queryClient;
