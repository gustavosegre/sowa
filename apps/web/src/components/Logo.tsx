import logo from "@/assets/logo.png";
import { t } from "@/i18n/pt-BR";
import { cn } from "@/lib/utils";

/** The SOWA mark (rounded tile). `size` in px; the image is 192px, sharp up to 3x.
 *  `decorative` when the name is already written next to it. */
export function Logo({
  size = 32,
  decorative = false,
  className,
}: {
  size?: number;
  decorative?: boolean;
  className?: string;
}) {
  return (
    <img
      src={logo}
      alt={decorative ? "" : t.app.name}
      width={size}
      height={size}
      draggable={false}
      className={cn("shrink-0 select-none", className)}
    />
  );
}
