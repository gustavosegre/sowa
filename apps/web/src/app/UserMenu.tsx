import { useQueryClient } from "@tanstack/react-query";
import { LogOut, UserPlus, UserRound } from "lucide-react";
import { useState } from "react";

import { errorIssue } from "@/api/client";
import { createUser, logout, useAuthStatus, useUsers } from "@/api/hooks";
import { IssueItem } from "@/components/IssueList";
import {
  Button,
  Dialog,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  Field,
  Input,
} from "@/components/ui";
import { t } from "@/i18n/pt-BR";

function NewUserDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const { data: users } = useUsers(open);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [done, setDone] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  const save = async () => {
    setError(null);
    try {
      const u = await createUser(username.trim(), password);
      setDone(u.username);
      setUsername("");
      setPassword("");
      await qc.invalidateQueries({ queryKey: ["users"] });
    } catch (e) {
      setError(e);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => !o && onClose()}
      title={t.auth.users}
      description={t.auth.sharedWorkspace}
      footer={
        <Button onClick={() => void save()} disabled={!username.trim() || !password}>
          <UserPlus /> {t.auth.createUser}
        </Button>
      }
    >
      <div className="flex flex-col gap-3">
        <ul className="flex flex-wrap gap-1">
          {users?.map((u) => (
            <li key={u.id} className="rounded-md bg-muted px-2 py-0.5 text-[12px]">
              {u.username}
            </li>
          ))}
        </ul>
        <Field label={t.auth.username}>
          <Input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="off" />
        </Field>
        <Field label={t.auth.password} hint={t.auth.passwordHint}>
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
          />
        </Field>
        {done && <p className="text-[12px] text-success">{t.auth.userCreated(done)}</p>}
        {error !== null && <IssueItem issue={errorIssue(error)} />}
      </div>
    </Dialog>
  );
}

/** Logged-in user: create users, log out. Hidden when login is disabled. */
export function UserMenu() {
  const qc = useQueryClient();
  const { data: status } = useAuthStatus();
  const [usersOpen, setUsersOpen] = useState(false);
  const user = status?.user;
  if (!user) return null;
  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            aria-label={t.auth.menu(user.username)}
            className="flex h-8 cursor-pointer items-center gap-1.5 rounded-md px-2 text-[13px] font-medium hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 [&_svg]:size-4"
          >
            <UserRound aria-hidden /> {user.username}
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuLabel>{user.username}</DropdownMenuLabel>
          <DropdownMenuItem onSelect={() => setUsersOpen(true)}>
            <UserPlus /> {t.auth.newUser}
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onSelect={() => void logout().then(() => qc.resetQueries())}>
            <LogOut /> {t.auth.logout}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      {usersOpen && <NewUserDialog open onClose={() => setUsersOpen(false)} />}
    </>
  );
}
