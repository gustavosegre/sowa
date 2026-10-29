import {
  DataEditor,
  GridCellKind,
  GridColumnIcon,
  type GridCell,
  type GridColumn,
  type Item,
  type Rectangle,
  type Theme,
} from "@glideapps/glide-data-grid";
import { useCallback, useMemo } from "react";

import type { PreviewPage } from "@/api/hooks";
import { PAGE_SIZE } from "@/api/hooks";
import type { Column, LogicalType } from "@/api/types";
import { useUiStore } from "@/stores/uiStore";

import { formatCell } from "./format";

const ICON: Record<LogicalType, GridColumnIcon> = {
  text: GridColumnIcon.HeaderString,
  integer: GridColumnIcon.HeaderNumber,
  decimal: GridColumnIcon.HeaderNumber,
  boolean: GridColumnIcon.HeaderBoolean,
  date: GridColumnIcon.HeaderDate,
  datetime: GridColumnIcon.HeaderDate,
  time: GridColumnIcon.HeaderTime,
  other: GridColumnIcon.HeaderCode,
};

// Canvas-rendered, so the grid takes colors, not CSS variables: keep in sync with index.css.
const LIGHT: Partial<Theme> = {
  accentColor: "#805ad5",
  accentLight: "rgba(128, 90, 213, 0.12)",
  textDark: "#13241f",
  textMedium: "#586661",
  textLight: "#98a29e",
  textHeader: "#2a3a35",
  bgCell: "#ffffff",
  bgCellMedium: "#f8f6fc",
  bgHeader: "#f4f1fa",
  bgHeaderHasFocus: "#ebe6f4",
  bgHeaderHovered: "#ebe6f4",
  borderColor: "rgba(88, 102, 97, 0.18)",
  horizontalBorderColor: "rgba(88, 102, 97, 0.12)",
  fontFamily: "Inter, ui-sans-serif, system-ui, Segoe UI, sans-serif",
  baseFontStyle: "12.5px",
  headerFontStyle: "600 12px",
  editorFontSize: "12.5px",
};

const DARK: Partial<Theme> = {
  ...LIGHT,
  accentColor: "#c4b5fd",
  accentFg: "#063d32",
  accentLight: "rgba(196, 181, 253, 0.16)",
  textDark: "#f4f1fa",
  textMedium: "#9db0a9",
  textLight: "#62756f",
  textHeader: "#dde3e0",
  bgCell: "#0a241f",
  bgCellMedium: "#0d2a24",
  bgHeader: "#0f2e28",
  bgHeaderHasFocus: "#163a33",
  bgHeaderHovered: "#163a33",
  borderColor: "rgba(196, 220, 210, 0.12)",
  horizontalBorderColor: "rgba(196, 220, 210, 0.08)",
};

// New/changed columns (comparison mode): a Lima tint.
const HIGHLIGHT_LIGHT = { bgHeader: "#e4f4d0", bgCell: "#f6fbef" };
const HIGHLIGHT_DARK = { bgHeader: "#24451a", bgCell: "#10301f" };

export interface DataGridProps {
  columns: Column[];
  pages: PreviewPage[];
  highlight?: Set<string>;
  width?: number | string;
  onHeaderMenu?: (col: Column, bounds: Rectangle) => void;
  onCellMenu?: (col: Column, value: unknown, bounds: Rectangle) => void;
  onNeedMore?: () => void;
}

export function DataGrid({ columns, pages, highlight, onHeaderMenu, onCellMenu, onNeedMore }: DataGridProps) {
  const dark = useUiStore((s) => s.theme === "dark");
  const rows = pages.reduce((n, p) => n + p.rows, 0);

  // Arrow columns are looked up by name (the server projection keeps names and order).
  const vectors = useMemo(
    () => pages.map((p) => columns.map((c) => p.table.getChild(c.name))),
    [pages, columns],
  );

  const gridColumns = useMemo<GridColumn[]>(
    () =>
      columns.map((c) => ({
        id: c.name,
        title: c.name,
        icon: ICON[c.type],
        hasMenu: Boolean(onHeaderMenu),
        width: Math.min(260, Math.max(90, c.name.length * 8 + 48)),
        themeOverride: highlight?.has(c.name) ? (dark ? HIGHLIGHT_DARK : HIGHLIGHT_LIGHT) : undefined,
      })),
    [columns, highlight, dark, onHeaderMenu],
  );

  const valueAt = useCallback(
    ([col, row]: Item): unknown => {
      const page = Math.floor(row / PAGE_SIZE);
      return vectors[page]?.[col]?.get(row % PAGE_SIZE) ?? null;
    },
    [vectors],
  );

  const getCellContent = useCallback(
    (cell: Item): GridCell => {
      const c = columns[cell[0]];
      const v = valueAt(cell);
      const type = c?.type ?? "text";
      if (v === null || v === undefined) {
        return {
          kind: GridCellKind.Text,
          data: "",
          displayData: "∅",
          allowOverlay: false,
          contentAlign: type === "integer" || type === "decimal" ? "right" : "left",
          themeOverride: { textDark: dark ? "#3f5751" : "#c6cdca" },
        };
      }
      const text = formatCell(v, type);
      return {
        kind: GridCellKind.Text,
        data: text,
        displayData: text,
        allowOverlay: true,
        readonly: true,
        contentAlign: type === "integer" || type === "decimal" ? "right" : "left",
      };
    },
    [columns, valueAt, dark],
  );

  return (
    <DataEditor
      columns={gridColumns}
      rows={rows}
      getCellContent={getCellContent}
      getCellsForSelection
      theme={dark ? DARK : LIGHT}
      width="100%"
      height="100%"
      rowMarkers="number"
      smoothScrollX
      smoothScrollY
      rowHeight={28}
      headerHeight={32}
      onHeaderMenuClick={(col, bounds) => {
        const c = columns[col];
        if (c && onHeaderMenu) onHeaderMenu(c, bounds);
      }}
      onHeaderClicked={(col, e) => {
        const c = columns[col];
        if (c && onHeaderMenu) onHeaderMenu(c, e.bounds);
      }}
      onCellContextMenu={(cell, e) => {
        const c = columns[cell[0]];
        if (!c || !onCellMenu) return;
        e.preventDefault();
        onCellMenu(c, valueAt(cell), e.bounds);
      }}
      onVisibleRegionChanged={(r) => {
        if (onNeedMore && r.y + r.height >= rows - 50) onNeedMore();
      }}
    />
  );
}
