import { createContext, useContext } from "react";

export const ProjectContext = createContext<string | null>(null);

export function useProjectId(): string | null {
  return useContext(ProjectContext);
}
