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

const LIGHT: Partial<Theme> = {
  accentColor: "#c2410c",
  accentLight: "rgba(194, 65, 12, 0.12)",
  textDark: "#1f2430",
  textMedium: "#5b6070",
  textLight: "#9aa0ad",
  textHeader: "#3a3f4c",
  bgCell: "#ffffff",
  bgCellMedium: "#f7f8fa",
  bgHeader: "#f5f6f8",
  bgHeaderHasFocus: "#eceef2",
  bgHeaderHovered: "#eceef2",
  borderColor: "rgba(115, 120, 135, 0.18)",
  horizontalBorderColor: "rgba(115, 120, 135, 0.12)",
  fontFamily: "Inter, ui-sans-serif, system-ui, Segoe UI, sans-serif",
  baseFontStyle: "12.5px",
  headerFontStyle: "600 12px",
  editorFontSize: "12.5px",
};

const DARK: Partial<Theme> = {
  ...LIGHT,
  accentColor: "#f97316",
  accentLight: "rgba(249, 115, 22, 0.18)",
  textDark: "#e7e9ee",
  textMedium: "#a7acb8",
  textLight: "#6f7584",
  textHeader: "#d5d8df",
  bgCell: "#1d2028",
  bgCellMedium: "#22252e",
  bgHeader: "#252832",
  bgHeaderHasFocus: "#2e323d",
  bgHeaderHovered: "#2e323d",
  borderColor: "rgba(200, 205, 220, 0.12)",
  horizontalBorderColor: "rgba(200, 205, 220, 0.08)",
};

const HIGHLIGHT_LIGHT = { bgHeader: "#fdebd7", bgCell: "#fffaf4" };
const HIGHLIGHT_DARK = { bgHeader: "#4a2f1a", bgCell: "#262119" };

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
          themeOverride: { textDark: dark ? "#4b5160" : "#c3c7d0" },
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
