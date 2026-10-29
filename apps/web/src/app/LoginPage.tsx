import { useQueryClient } from "@tanstack/react-query";
import { LogIn } from "lucide-react";
import { useState, type SyntheticEvent } from "react";

import { api, ApiError, errorIssue, unwrap } from "@/api/client";
import { clearToken, setToken } from "@/api/token";
import { IssueItem } from "@/components/IssueList";
import { Button, Field, Input } from "@/components/ui";
import { Logo } from "@/components/Logo";
import { t } from "@/i18n/pt-BR";

/** Asks for the access token (as Flowa does) when the stored one is missing or wrong. */
export function LoginPage() {
  const qc = useQueryClient();
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const submit = async (e: SyntheticEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setToken(value);
      const status = unwrap(await api.GET("/auth/status"));
      if (!status.authenticated) {
        clearToken();
        setError(new ApiError({ code: "UNAUTHENTICATED", message: t.auth.wrong }, 401));
        return;
      }
      // Drop everything cached without the token and refetch what is on screen.
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
        className="flex w-full max-w-md flex-col gap-4 rounded-xl border bg-card p-6 shadow-sm"
      >
        <div className="flex items-center gap-3">
          <Logo size={40} decorative />
          <h1 className="text-[16px] font-semibold">{t.auth.title}</h1>
        </div>
        <p className="text-[13px] text-muted-foreground">{t.auth.help}</p>
        <Field label={t.auth.token} hint={t.auth.where}>
          <Input
            type="password"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={t.auth.placeholder}
            autoComplete="off"
            autoFocus
            required
          />
        </Field>
        {error !== null && <IssueItem issue={errorIssue(error)} />}
        <Button type="submit" disabled={busy || !value.trim()}>
          <LogIn /> {t.auth.submit}
        </Button>
      </form>
    </div>
  );
}
