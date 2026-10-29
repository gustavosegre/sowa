import { useQueryClient } from "@tanstack/react-query";
import { LogOut } from "lucide-react";

import { useAuthStatus } from "@/api/hooks";
import { clearToken } from "@/api/token";
import { Button, Tooltip } from "@/components/ui";
import { t } from "@/i18n/pt-BR";

/** Forgets the access token in this browser. Hidden when login is off. */
export function SignOutButton() {
  const qc = useQueryClient();
  const { data: status } = useAuthStatus();
  if (!status?.auth_enabled) return null;
  return (
    <Tooltip content={t.auth.signOutHint}>
      <Button
        variant="ghost"
        size="icon"
        aria-label={t.auth.signOut}
        onClick={() => {
          clearToken();
          void qc.resetQueries();
        }}
      >
        <LogOut />
      </Button>
    </Tooltip>
  );
}
