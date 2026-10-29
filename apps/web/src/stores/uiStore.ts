import { create } from "zustand";
import { persist } from "zustand/middleware";

export type SaveStatus = "saved" | "saving" | "dirty" | "error";

interface UiState {
  theme: "light" | "dark";
  previewHeight: number;
  previewCollapsed: boolean;
  compareMode: boolean;
  profileColumn: string | null;
  paletteOpen: boolean;
  wizard: { open: boolean; replaceSourceId?: string; file?: File };
  saveStatus: SaveStatus;

  toggleTheme: () => void;
  setPreviewHeight: (h: number) => void;
  togglePreview: () => void;
  setCompare: (v: boolean) => void;
  setProfileColumn: (c: string | null) => void;
  setPaletteOpen: (v: boolean) => void;
  openWizard: (opts?: { replaceSourceId?: string; file?: File }) => void;
  closeWizard: () => void;
  setSaveStatus: (s: SaveStatus) => void;
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      theme: window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light",
      previewHeight: 300,
      previewCollapsed: false,
      compareMode: false,
      profileColumn: null,
      paletteOpen: false,
      wizard: { open: false },
      saveStatus: "saved",

      toggleTheme: () => set((s) => ({ theme: s.theme === "dark" ? "light" : "dark" })),
      setPreviewHeight: (h) => set({ previewHeight: Math.max(120, Math.min(h, window.innerHeight - 200)) }),
      togglePreview: () => set((s) => ({ previewCollapsed: !s.previewCollapsed })),
      setCompare: (v) => set({ compareMode: v }),
      setProfileColumn: (c) => set({ profileColumn: c }),
      setPaletteOpen: (v) => set({ paletteOpen: v }),
      openWizard: (opts) => set({ wizard: { open: true, ...opts } }),
      closeWizard: () => set({ wizard: { open: false } }),
      setSaveStatus: (s) => set({ saveStatus: s }),
    }),
    {
      name: "sowa-ui",
      partialize: (s) => ({
        theme: s.theme,
        previewHeight: s.previewHeight,
        previewCollapsed: s.previewCollapsed,
      }),
    },
  ),
);
