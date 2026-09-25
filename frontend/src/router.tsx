import { QueryClient } from "@tanstack/react-query";
import { createRouter } from "@tanstack/react-router";

import { routeTree } from "./routeTree.gen";

export const getRouter = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        // Every page refetches on mount anyway; a short stale window just
        // stops a single navigation firing the same request twice.
        staleTime: 5_000,
        retry: 1,
      },
    },
  });

  return createRouter({
    routeTree,
    context: { queryClient },
    scrollRestoration: true,
    defaultPreloadStaleTime: 0,
    defaultNotFoundComponent: () => (
      <div className="glass-panel mx-auto mt-16 max-w-md p-8 text-center">
        <p className="eyebrow">404</p>
        <h1 className="mt-2 font-display text-3xl font-semibold">Nothing on this shelf</h1>
        <p className="mt-2 text-sm text-muted-foreground">That page doesn't exist or has moved.</p>
        <a href="/" className="mt-6 inline-block rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground">
          Back to the kitchen
        </a>
      </div>
    ),
  });
};

declare module "@tanstack/react-router" {
  interface Register {
    router: ReturnType<typeof getRouter>;
  }
}
