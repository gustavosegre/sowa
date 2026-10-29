import {
  ChevronDown,
  ChevronRight,
  FolderInput,
  FolderOpen,
  Moon,
  Plus,
  Sun,
  Trash2,
  Workflow,
} from "lucide-react";
import { useMemo, useState } from "react";

import { useCreateProject, useDeleteProject, useMoveProject, useProjects } from "@/api/hooks";
import type { Project } from "@/api/types";
import { Button, Dialog, Field, Input, Spinner } from "@/components/ui";
import { Logo } from "@/components/Logo";
import { t } from "@/i18n/pt-BR";
import { fmtDateTime } from "@/lib/utils";
import { useUiStore } from "@/stores/uiStore";

import { SignOutButton } from "./SignOutButton";

const WORKSPACES_LIST = "sowa-workspaces";

/** Workspaces in alphabetical order, then the projects without one (as Flowa groups pipelines). */
function groupByWorkspace(projects: Project[]): { name: string | null; projects: Project[] }[] {
  const groups = new Map<string, Project[]>();
  const loose: Project[] = [];
  for (const p of projects) {
    if (p.workspace) groups.set(p.workspace, [...(groups.get(p.workspace) ?? []), p]);
    else loose.push(p);
  }
  const named = [...groups.keys()]
    .sort((a, b) => a.localeCompare(b, "pt-BR"))
    .map((name) => ({ name, projects: groups.get(name) ?? [] }));
  return loose.length ? [...named, { name: null, projects: loose }] : named;
}

function ProjectCard({
  project: p,
  onOpen,
  onMove,
  onDelete,
}: {
  project: Project;
  onOpen: () => void;
  onMove: () => void;
  onDelete: () => void;
}) {
  return (
    <li className="group flex flex-col gap-2 rounded-lg border bg-card p-4 shadow-sm transition-shadow hover:shadow-md">
      <button type="button" className="flex cursor-pointer flex-col gap-1 text-left" onClick={onOpen}>
        <span className="truncate text-[14px] font-semibold">{p.name}</span>
        <span className="text-xs text-muted-foreground">
          {t.projects.nodes(p.node_count)} · {t.projects.updated(fmtDateTime(p.updated_at))}
        </span>
      </button>
      <div className="flex gap-1">
        <Button size="sm" variant="outline" onClick={onOpen}>
          <FolderOpen /> {t.projects.open}
        </Button>
        <span className="flex-1" />
        <Button
          size="sm"
          variant="ghost"
          className="opacity-0 group-focus-within:opacity-100 group-hover:opacity-100"
          aria-label={`${t.projects.move}: ${p.name}`}
          onClick={onMove}
        >
          <FolderInput />
        </Button>
        <Button
          size="sm"
          variant="ghost"
          className="opacity-0 group-focus-within:opacity-100 group-hover:opacity-100"
          aria-label={`${t.common.delete} ${p.name}`}
          onClick={onDelete}
        >
          <Trash2 />
        </Button>
      </div>
    </li>
  );
}

export function ProjectsPage({ onOpen }: { onOpen: (id: string) => void }) {
  const { data, isLoading, error } = useProjects();
  const create = useCreateProject();
  const move = useMoveProject();
  const del = useDeleteProject();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [workspace, setWorkspace] = useState("");
  const [moving, setMoving] = useState<Project | null>(null);
  const [target, setTarget] = useState("");
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const ui = useUiStore();

  const groups = useMemo(() => groupByWorkspace(data ?? []), [data]);
  const workspaces = groups.flatMap((g) => (g.name ? [g.name] : []));
  const grouped = workspaces.length > 0;

  const submit = () => {
    create.mutate(
      { name: name.trim() || t.projects.defaultName, workspace: workspace.trim() || null },
      {
        onSuccess: (p) => {
          setOpen(false);
          setName("");
          onOpen(p.id);
        },
      },
    );
  };

  const submitMove = () => {
    if (!moving) return;
    move.mutate({ id: moving.id, workspace: target.trim() || null }, { onSuccess: () => setMoving(null) });
  };

  const toggle = (key: string) =>
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  const cards = (projects: Project[]) => (
    <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {projects.map((p) => (
        <ProjectCard
          key={p.id}
          project={p}
          onOpen={() => onOpen(p.id)}
          onMove={() => {
            setMoving(p);
            setTarget(p.workspace ?? "");
          }}
          onDelete={() => window.confirm(t.projects.confirmDelete(p.name)) && del.mutate(p.id)}
        />
      ))}
    </ul>
  );

  return (
    <div className="min-h-full bg-background">
      <header className="border-b bg-card">
        <div className="mx-auto flex max-w-5xl items-center gap-3 px-6 py-4">
          <Logo size={36} decorative />
          <div className="flex-1">
            <h1 className="text-[17px] font-semibold">{t.app.name}</h1>
            <p className="text-xs text-muted-foreground">{t.app.tagline}</p>
          </div>
          <Button variant="ghost" size="icon" onClick={ui.toggleTheme} aria-label={t.editor.theme}>
            {ui.theme === "dark" ? <Sun /> : <Moon />}
          </Button>
          <SignOutButton />
          <Button onClick={() => setOpen(true)}>
            <Plus /> {t.projects.new}
          </Button>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-6">
        <h2 className="mb-3 text-[13px] font-semibold uppercase tracking-wide text-muted-foreground">
          {t.projects.title}
        </h2>
        {isLoading && <Spinner />}
        {error && <p className="text-danger">{error.message}</p>}
        {data?.length === 0 && (
          <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed p-12 text-center">
            <Workflow className="size-8 text-primary" />
            <p className="max-w-sm text-muted-foreground">{t.projects.empty}</p>
            <Button onClick={() => setOpen(true)}>
              <Plus /> {t.projects.new}
            </Button>
          </div>
        )}
        {!grouped && cards(data ?? [])}
        {grouped && (
          <div className="flex flex-col gap-5">
            {groups.map((g) => {
              const key = g.name ?? "";
              const isOpen = !collapsed.has(key);
              return (
                <section key={key} aria-label={g.name ?? t.projects.noWorkspace}>
                  <button
                    type="button"
                    aria-expanded={isOpen}
                    onClick={() => toggle(key)}
                    className="mb-2 flex cursor-pointer items-center gap-1.5 rounded-md text-[14px] font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 [&_svg]:size-4"
                  >
                    {isOpen ? <ChevronDown aria-hidden /> : <ChevronRight aria-hidden />}
                    {g.name ?? t.projects.noWorkspace}
                    <span className="text-xs font-normal text-muted-foreground">
                      {t.projects.workspaceCount(g.projects.length)}
                    </span>
                  </button>
                  {isOpen && cards(g.projects)}
                </section>
              );
            })}
          </div>
        )}
      </main>
      <datalist id={WORKSPACES_LIST}>
        {workspaces.map((w) => (
          <option key={w} value={w} />
        ))}
      </datalist>
      <Dialog
        open={open}
        onOpenChange={setOpen}
        title={t.projects.new}
        footer={
          <>
            <Button variant="outline" onClick={() => setOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button onClick={submit} disabled={create.isPending}>
              {create.isPending && <Spinner />}
              {t.common.confirm}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-3">
          <Input
            autoFocus
            value={name}
            placeholder={t.projects.defaultName}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
            aria-label={t.projects.newName}
          />
          <Field label={t.projects.workspace} hint={t.projects.workspaceHint}>
            <Input
              value={workspace}
              list={WORKSPACES_LIST}
              onChange={(e) => setWorkspace(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submit()}
            />
          </Field>
        </div>
      </Dialog>
      <Dialog
        open={moving !== null}
        onOpenChange={(o) => !o && setMoving(null)}
        title={moving ? t.projects.moveTitle(moving.name) : ""}
        footer={
          <>
            <Button variant="outline" onClick={() => setMoving(null)}>
              {t.common.cancel}
            </Button>
            <Button onClick={submitMove} disabled={move.isPending}>
              {move.isPending && <Spinner />}
              {t.common.confirm}
            </Button>
          </>
        }
      >
        <Field label={t.projects.workspace} hint={t.projects.workspaceHint}>
          <Input
            autoFocus
            value={target}
            list={WORKSPACES_LIST}
            placeholder={t.projects.noWorkspace}
            onChange={(e) => setTarget(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submitMove()}
          />
        </Field>
      </Dialog>
    </div>
  );
}
