import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { TooltipProvider } from "@/components/ui";
import { Editor } from "@/features/editor/Editor";
import { useUiStore } from "@/stores/uiStore";

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

export function App() {
  const [projectId, go] = useProjectParam();
  const theme = useUiStore((s) => s.theme);
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        {projectId ? <Editor projectId={projectId} onBack={() => go(null)} /> : <ProjectsPage onOpen={go} />}
      </TooltipProvider>
    </QueryClientProvider>
  );
}
