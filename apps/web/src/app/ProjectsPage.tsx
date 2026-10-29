import { FolderOpen, Moon, Plus, Sun, Trash2, Workflow } from "lucide-react";
import { useState } from "react";

import { useCreateProject, useDeleteProject, useProjects } from "@/api/hooks";
import { Button, Dialog, Input, Spinner } from "@/components/ui";
import { t } from "@/i18n/pt-BR";
import { fmtDateTime } from "@/lib/utils";
import { useUiStore } from "@/stores/uiStore";

import { UserMenu } from "./UserMenu";

export function ProjectsPage({ onOpen }: { onOpen: (id: string) => void }) {
  const { data, isLoading, error } = useProjects();
  const create = useCreateProject();
  const del = useDeleteProject();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const ui = useUiStore();

  const submit = () => {
    create.mutate(name.trim() || t.projects.defaultName, {
      onSuccess: (p) => {
        setOpen(false);
        setName("");
        onOpen(p.id);
      },
    });
  };

  return (
    <div className="min-h-full bg-background">
      <header className="border-b bg-card">
        <div className="mx-auto flex max-w-5xl items-center gap-3 px-6 py-4">
          <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-[15px] font-bold text-primary-foreground">
            F
          </span>
          <div className="flex-1">
            <h1 className="text-[17px] font-semibold">{t.app.name}</h1>
            <p className="text-xs text-muted-foreground">{t.app.tagline}</p>
          </div>
          <Button variant="ghost" size="icon" onClick={ui.toggleTheme} aria-label={t.editor.theme}>
            {ui.theme === "dark" ? <Sun /> : <Moon />}
          </Button>
          <UserMenu />
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
        <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {data?.map((p) => (
            <li
              key={p.id}
              className="group flex flex-col gap-2 rounded-lg border bg-card p-4 shadow-sm transition-shadow hover:shadow-md"
            >
              <button
                type="button"
                className="flex cursor-pointer flex-col gap-1 text-left"
                onClick={() => onOpen(p.id)}
              >
                <span className="truncate text-[14px] font-semibold">{p.name}</span>
                <span className="text-xs text-muted-foreground">
                  {t.projects.nodes(p.node_count)} · {t.projects.updated(fmtDateTime(p.updated_at))}
                  {p.owner ? ` · ${t.projects.by(p.owner)}` : ""}
                </span>
              </button>
              <div className="flex gap-1">
                <Button size="sm" variant="outline" onClick={() => onOpen(p.id)}>
                  <FolderOpen /> {t.projects.open}
                </Button>
                <span className="flex-1" />
                <Button
                  size="sm"
                  variant="ghost"
                  className="opacity-0 group-hover:opacity-100"
                  aria-label={`${t.common.delete} ${p.name}`}
                  onClick={() => window.confirm(t.projects.confirmDelete(p.name)) && del.mutate(p.id)}
                >
                  <Trash2 />
                </Button>
              </div>
            </li>
          ))}
        </ul>
      </main>
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
        <Input
          autoFocus
          value={name}
          placeholder={t.projects.defaultName}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          aria-label={t.projects.newName}
        />
      </Dialog>
    </div>
  );
}
