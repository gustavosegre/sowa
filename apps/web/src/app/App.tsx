import { QueryClient, QueryClientProvider, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";

import { UNAUTHENTICATED_EVENT } from "@/api/client";
import { useAuthStatus } from "@/api/hooks";
import { Spinner, TooltipProvider } from "@/components/ui";
import { Editor } from "@/features/editor/Editor";
import { useUiStore } from "@/stores/uiStore";

import { LoginPage } from "./LoginPage";
import { ProjectsPage } from "./ProjectsPage";

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 1 } },
});

/** Minimal routing: `?p=<project id>` opens the editor. */
function useProjectParam(): [string | null, (id: string | null) => void] {
  const read = () => new URLSearchParams(window.location.search).get("p");
  const [id, setId] = useState<string | null>(read);
  useEffect(() => {
    const onPop = () => setId(read());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  const go = (next: string | null) => {
    const url = next ? `?p=${encodeURIComponent(next)}` : window.location.pathname;
    window.history.pushState(null, "", url);
    setId(next);
  };
  return [id, go];
}

/** Login screen until there is a session (when login is enabled on the server). */
function AuthGate({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const { data: status, isLoading, error } = useAuthStatus();
  useEffect(() => {
    const onExpired = () => void qc.invalidateQueries({ queryKey: ["auth"] });
    window.addEventListener(UNAUTHENTICATED_EVENT, onExpired);
    return () => window.removeEventListener(UNAUTHENTICATED_EVENT, onExpired);
  }, [qc]);
  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner className="size-6 text-primary" />
      </div>
    );
  }
  if (error) return <p className="p-6 text-danger">{error.message}</p>;
  if (status?.auth_enabled && !status.user) return <LoginPage setup={status.setup_required} />;
  return children;
}

export function App() {
  const [projectId, go] = useProjectParam();
  const theme = useUiStore((s) => s.theme);
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <AuthGate>
          {projectId ? (
            <Editor projectId={projectId} onBack={() => go(null)} />
          ) : (
            <ProjectsPage onOpen={go} />
          )}
        </AuthGate>
      </TooltipProvider>
    </QueryClientProvider>
  );
}
