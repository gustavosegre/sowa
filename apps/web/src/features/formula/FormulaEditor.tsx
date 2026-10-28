import {
  autocompletion,
  closeBrackets,
  completionKeymap,
  type Completion,
  type CompletionContext,
  type CompletionResult,
} from "@codemirror/autocomplete";
import { defaultKeymap, history, historyKeymap } from "@codemirror/commands";
import { forceLinting, linter, lintGutter, type Diagnostic } from "@codemirror/lint";
import { EditorState } from "@codemirror/state";
import {
  Decoration,
  EditorView,
  MatchDecorator,
  ViewPlugin,
  keymap,
  placeholder as cmPlaceholder,
  type DecorationSet,
  type ViewUpdate,
} from "@codemirror/view";
import { useEffect, useRef, useState } from "react";

import { checkFormula, useFunctions } from "@/api/hooks";
import type { Column, FormulaCheck, FunctionInfo } from "@/api/types";
import { Spinner } from "@/components/ui";
import { TypeIcon } from "@/components/TypeIcon";
import { t } from "@/i18n/pt-BR";
import { cn } from "@/lib/utils";
import { usePipelineStore } from "@/stores/pipelineStore";

const TOKEN =
  /(\{[^{}]*\})|(\[(?:[^\]]|\]\])*\])|("(?:[^"]|"")*")|([A-Za-z_À-ɏ][A-Za-z0-9_.À-ɏ]*)(?=\s*\()|(\d+(?:[.,]\d+)?)/g;
const CLASSES = ["tok-param", "tok-column", "tok-string", "tok-function", "tok-number"];

const highlighter = new MatchDecorator({
  regexp: TOKEN,
  decoration: (m) => {
    const idx = [1, 2, 3, 4, 5].findIndex((g) => m[g] !== undefined);
    return Decoration.mark({ class: CLASSES[idx] ?? "" });
  },
});

const highlightPlugin = ViewPlugin.fromClass(
  class {
    decorations: DecorationSet;
    constructor(view: EditorView) {
      this.decorations = highlighter.createDeco(view);
    }
    update(u: ViewUpdate) {
      this.decorations = highlighter.updateDeco(u, this.decorations);
    }
  },
  { decorations: (v) => v.decorations },
);

export interface FormulaEditorProps {
  value: string;
  onChange: (v: string) => void;
  columns: Column[];
  locale: "pt-BR" | "en-US";
  context?: "row" | "aggregate";
  groupKeys?: string[];
  /** When set, the formula is checked against this node's input in the current pipeline. */
  nodeId?: string;
  placeholder?: string;
  className?: string;
  ariaLabel?: string;
}

export function FormulaEditor(props: FormulaEditorProps) {
  const host = useRef<HTMLDivElement>(null);
  const view = useRef<EditorView | null>(null);
  // Mutable refs read by CodeMirror callbacks, so the editor is created only once.
  const live = useRef(props);
  live.current = props;
  const fns = useFunctions().data;
  const fnsRef = useRef<FunctionInfo[]>([]);
  fnsRef.current = fns ?? [];
  const [check, setCheck] = useState<FormulaCheck | null>(null);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    if (!host.current) return;
    const complete = (ctx: CompletionContext): CompletionResult | null => {
      const { columns, context = "row", locale } = live.current;
      const brace = ctx.matchBefore(/\{[^{}]*$/);
      if (brace) {
        const params = usePipelineStore.getState().pipeline.settings.params;
        return {
          from: brace.from,
          options: params.map((p) => ({
            label: `{${p.name}}`,
            type: "constant",
            detail: `${t.types[p.type] ?? p.type} = ${String(p.value ?? "")}`,
          })),
          validFor: /^\{[^{}]*$/,
        };
      }
      const bracket = ctx.matchBefore(/\[[^\]]*$/);
      if (bracket) {
        const after = ctx.state.sliceDoc(ctx.pos, ctx.pos + 1);
        return {
          from: bracket.from,
          options: columns.map((c) => ({
            label: `[${c.name}]`,
            type: "variable",
            detail: t.types[c.type],
            apply: after === "]" ? `[${c.name}` : `[${c.name}]`,
          })),
          validFor: /^\[[^\]]*$/,
        };
      }
      const word = ctx.matchBefore(/[A-Za-z_À-ɏ][A-Za-z0-9_.À-ɏ]*$/);
      if (!word || (word.from === word.to && !ctx.explicit)) return null;
      const options: Completion[] = [];
      for (const f of fnsRef.current) {
        if (f.context === "aggregate" && context !== "aggregate") continue;
        const name = locale === "en-US" ? (f.aliases[0] ?? f.name) : f.name;
        options.push({
          label: name,
          type: "function",
          detail: locale === "en-US" ? f.signature_en : f.signature,
          info: `${f.description}\nEx.: ${f.example}`,
          apply: `${name}(`,
          boost: f.excel ? 1 : 0,
        });
      }
      for (const c of columns) {
        options.push({
          label: c.name,
          type: "variable",
          detail: t.types[c.type],
          apply: `[${c.name}]`,
          boost: 2,
        });
      }
      return { from: word.from, options, validFor: /^[A-Za-z0-9_.À-ɏ]*$/ };
    };

    const lint = async (v: EditorView): Promise<Diagnostic[]> => {
      const { locale, context = "row", groupKeys = [], nodeId, columns } = live.current;
      // Always the latest graph: a node added a moment ago must already be known.
      const pipeline = usePipelineStore.getState().pipeline;
      const formula = v.state.doc.toString();
      if (!formula.trim()) {
        setCheck(null);
        return [];
      }
      setChecking(true);
      try {
        const res = await checkFormula({
          formula,
          locale,
          context,
          group_keys: groupKeys,
          ...(nodeId ? { pipeline, node_id: nodeId } : { columns }),
        });
        setCheck(res);
        return res.issues
          .filter((i) => i.position)
          .map((i) => {
            const len = v.state.doc.length;
            const from = Math.min(i.position?.start ?? 0, len);
            const to = Math.min(Math.max(i.position?.end ?? from, from), len);
            return {
              from,
              to: to === from && to < len ? to + 1 : to,
              severity: "error" as const,
              message: i.message.replace(/^Erro na fórmula: /, ""),
            };
          });
      } catch {
        return [];
      } finally {
        setChecking(false);
      }
    };

    const v = new EditorView({
      parent: host.current,
      state: EditorState.create({
        doc: live.current.value,
        extensions: [
          history(),
          closeBrackets(),
          keymap.of([...completionKeymap, ...defaultKeymap, ...historyKeymap]),
          EditorView.lineWrapping,
          cmPlaceholder(live.current.placeholder ?? t.formula.placeholder),
          highlightPlugin,
          autocompletion({ override: [complete], icons: false }),
          linter(lint, { delay: 250 }),
          lintGutter({}),
          EditorView.contentAttributes.of({ "aria-label": live.current.ariaLabel ?? "Fórmula" }),
          EditorView.updateListener.of((u) => {
            if (u.docChanged) live.current.onChange(u.state.doc.toString());
          }),
          EditorView.theme({
            "&": { minHeight: "60px", border: "1px solid var(--input)", borderRadius: "6px" },
            "&.cm-focused": { borderColor: "var(--ring)" },
            ".cm-content": { padding: "6px 4px", caretColor: "var(--foreground)" },
            ".cm-gutters": { display: "none" },
          }),
        ],
      }),
    });
    view.current = v;
    return () => {
      v.destroy();
      view.current = null;
    };
  }, []);

  // Upstream changes (new/renamed columns) can fix or break the formula: check again.
  const columnsKey = props.columns.map((c) => `${c.name}:${c.type}`).join("|");
  useEffect(() => {
    if (view.current) forceLinting(view.current);
  }, [columnsKey]);

  // External updates (undo, locale re-render): replace the document.
  useEffect(() => {
    const v = view.current;
    if (v && v.state.doc.toString() !== props.value) {
      v.dispatch({ changes: { from: 0, to: v.state.doc.length, insert: props.value } });
    }
  }, [props.value]);

  const errors = check?.issues.filter((i) => i.severity === "error") ?? [];
  return (
    <div className={cn("flex flex-col gap-1.5", props.className)}>
      <div ref={host} />
      <div className="flex min-h-5 flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-muted-foreground">
        {checking && <Spinner className="size-3" />}
        {check?.ok && check.type && (
          <span className="inline-flex items-center gap-1">
            {t.formula.result}: <TypeIcon type={check.type} />
            <strong className="text-foreground">{check.type_label}</strong>
          </span>
        )}
        {check?.ok && check.examples.length > 0 && (
          <span className="min-w-0 truncate" title={check.examples.map((e) => e ?? "∅").join(" · ")}>
            {t.formula.examples}:{" "}
            {check.examples.slice(0, 6).map((e, i) => (
              <code key={i} className="mr-1 rounded bg-muted px-1 font-mono text-foreground">
                {e ?? "∅"}
              </code>
            ))}
          </span>
        )}
        {!checking && errors[0] && (
          <span className="text-danger">{errors[0].message.replace(/^Erro na fórmula: /, "")}</span>
        )}
      </div>
    </div>
  );
}
