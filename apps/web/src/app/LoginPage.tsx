import { useQueryClient } from "@tanstack/react-query";
import { LogIn } from "lucide-react";
import { useState, type SyntheticEvent } from "react";

import { errorIssue } from "@/api/client";
import { login, setupFirstUser } from "@/api/hooks";
import { IssueItem } from "@/components/IssueList";
import { Button, Field, Input } from "@/components/ui";
import { t } from "@/i18n/pt-BR";

/** Login, or creation of the first user when there is none yet. */
export function LoginPage({ setup }: { setup: boolean }) {
  const qc = useQueryClient();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const submit = async (e: SyntheticEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await (setup ? setupFirstUser : login)(username.trim(), password);
      // Another user may be logging in: drop everything cached and refetch what is on screen.
      await qc.resetQueries();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-full items-center justify-center bg-background p-4">
      <form
        onSubmit={(e) => void submit(e)}
        className="flex w-full max-w-sm flex-col gap-4 rounded-xl border bg-card p-6 shadow-sm"
      >
        <div className="flex items-center gap-3">
          <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-[15px] font-bold text-primary-foreground">
            F
          </span>
          <h1 className="text-[16px] font-semibold">{setup ? t.auth.setupTitle : t.auth.loginTitle}</h1>
        </div>
        {setup && <p className="text-[12px] text-muted-foreground">{t.auth.setupHint}</p>}
        <Field label={t.auth.username}>
          <Input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            autoFocus
            required
          />
        </Field>
        <Field label={t.auth.password} hint={setup ? t.auth.passwordHint : undefined}>
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={setup ? "new-password" : "current-password"}
            required
          />
        </Field>
        {error !== null && <IssueItem issue={errorIssue(error)} />}
        <Button type="submit" disabled={busy || !username.trim() || !password}>
          <LogIn /> {setup ? t.auth.create : t.auth.login}
        </Button>
      </form>
    </div>
  );
}
