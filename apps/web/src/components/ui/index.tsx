/* shadcn/ui-style primitives (Radix + Tailwind), kept in one module for the small set we use. */
import { cva, type VariantProps } from "class-variance-authority";
import { Check, ChevronDown, X } from "lucide-react";
import {
  Checkbox as CheckboxPrimitive,
  Dialog as DialogPrimitive,
  DropdownMenu as Menu,
  Popover as PopoverPrimitive,
  Slot,
  Switch as SwitchPrimitive,
  Tooltip as TooltipPrimitive,
} from "radix-ui";
import * as React from "react";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-md text-[13px] font-medium transition-colors disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0 cursor-pointer",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:brightness-110 shadow-sm",
        outline: "border border-input bg-card hover:bg-muted",
        ghost: "hover:bg-muted",
        danger: "bg-danger text-white hover:brightness-110",
        subtle: "bg-muted hover:bg-accent",
      },
      size: {
        default: "h-8 px-3",
        sm: "h-7 px-2 text-xs",
        icon: "size-8",
        iconSm: "size-6 [&_svg]:size-3.5",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, type = "button", asChild = false, ...props }, ref) =>
    asChild ? (
      <Slot.Root ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />
    ) : (
      <button ref={ref} type={type} className={cn(buttonVariants({ variant, size }), className)} {...props} />
    ),
);
Button.displayName = "Button";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "h-8 w-full min-w-0 rounded-md border border-input bg-card px-2.5 text-[13px] outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring/40 disabled:opacity-50",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      "w-full rounded-md border border-input bg-card px-2.5 py-1.5 text-[13px] outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring/40",
      className,
    )}
    {...props}
  />
));
Textarea.displayName = "Textarea";

export interface SelectOption<V extends string = string> {
  value: V;
  label: string;
}

/** Native select: fast, accessible and keyboard friendly for dense config panels. */
export function Select<V extends string>({
  value,
  onChange,
  options,
  className,
  placeholder,
  ...rest
}: {
  value: V | "" | null | undefined;
  onChange: (v: V) => void;
  options: readonly SelectOption<V>[];
  className?: string;
  placeholder?: string;
} & Omit<React.SelectHTMLAttributes<HTMLSelectElement>, "value" | "onChange">) {
  return (
    <div className={cn("relative min-w-0", className)}>
      <select
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value as V)}
        className="h-8 w-full min-w-0 cursor-pointer appearance-none truncate rounded-md border border-input bg-card pl-2.5 pr-7 text-[13px] outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
        {...rest}
      >
        {placeholder !== undefined && (
          <option value="" disabled>
            {placeholder}
          </option>
        )}
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
    </div>
  );
}

export function Label({ className, ...props }: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return <label className={cn("text-xs font-medium text-muted-foreground", className)} {...props} />;
}

/** Label + control. The <label> wraps the control so it gets an accessible name. */
export function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: React.ReactNode;
  hint?: string;
}) {
  return (
    <label className="flex min-w-0 flex-col gap-1">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      {children}
      {hint && <span className="text-[11px] text-muted-foreground">{hint}</span>}
    </label>
  );
}

export function Switch({
  checked,
  onCheckedChange,
  label,
}: {
  checked: boolean;
  onCheckedChange: (v: boolean) => void;
  label?: string;
}) {
  const id = React.useId();
  return (
    <div className="flex items-center gap-2">
      <SwitchPrimitive.Root
        id={id}
        checked={checked}
        onCheckedChange={onCheckedChange}
        className="relative h-4.5 w-8 shrink-0 cursor-pointer rounded-full bg-input transition-colors data-[state=checked]:bg-primary"
      >
        <SwitchPrimitive.Thumb className="block size-3.5 translate-x-0.5 rounded-full bg-white shadow transition-transform data-[state=checked]:translate-x-4" />
      </SwitchPrimitive.Root>
      {label && (
        <label htmlFor={id} className="cursor-pointer text-[13px]">
          {label}
        </label>
      )}
    </div>
  );
}

export function Checkbox({
  checked,
  onCheckedChange,
  label,
  className,
}: {
  checked: boolean;
  onCheckedChange: (v: boolean) => void;
  label?: React.ReactNode;
  className?: string;
}) {
  const id = React.useId();
  return (
    <div className={cn("flex min-w-0 items-center gap-2", className)}>
      <CheckboxPrimitive.Root
        id={id}
        checked={checked}
        onCheckedChange={(v) => onCheckedChange(v === true)}
        className="flex size-4 shrink-0 cursor-pointer items-center justify-center rounded border border-input bg-card data-[state=checked]:border-primary data-[state=checked]:bg-primary"
      >
        <CheckboxPrimitive.Indicator>
          <Check className="size-3 text-white" strokeWidth={3} />
        </CheckboxPrimitive.Indicator>
      </CheckboxPrimitive.Root>
      {label !== undefined && (
        <label htmlFor={id} className="min-w-0 cursor-pointer truncate text-[13px]">
          {label}
        </label>
      )}
    </div>
  );
}

export function Badge({
  className,
  tone = "neutral",
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & {
  tone?: "neutral" | "danger" | "warning" | "success" | "primary";
}) {
  const tones = {
    neutral: "bg-muted text-muted-foreground",
    danger: "bg-danger-soft text-danger",
    warning: "bg-warning-soft text-[color-mix(in_oklch,var(--warning)_70%,black)] dark:text-warning",
    success: "bg-[color-mix(in_oklch,var(--success)_15%,transparent)] text-success",
    primary: "bg-accent text-primary",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium",
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}

/* ---------------------------------------------------------------- Dialog */

export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  className,
  footer,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
  footer?: React.ReactNode;
}) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/40 backdrop-blur-[1px]" />
        <DialogPrimitive.Content
          className={cn(
            "fixed left-1/2 top-1/2 z-50 flex max-h-[90vh] w-[min(560px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 flex-col rounded-lg border bg-card shadow-xl outline-none",
            className,
          )}
        >
          <div className="flex items-start justify-between gap-4 border-b px-5 py-3.5">
            <div>
              <DialogPrimitive.Title className="text-[15px] font-semibold">{title}</DialogPrimitive.Title>
              {description ? (
                <DialogPrimitive.Description className="mt-0.5 text-xs text-muted-foreground">
                  {description}
                </DialogPrimitive.Description>
              ) : (
                <DialogPrimitive.Description className="sr-only">{title}</DialogPrimitive.Description>
              )}
            </div>
            <DialogPrimitive.Close asChild>
              <Button variant="ghost" size="iconSm" aria-label="Fechar">
                <X />
              </Button>
            </DialogPrimitive.Close>
          </div>
          <div className="min-h-0 flex-1 overflow-auto px-5 py-4">{children}</div>
          {footer && <div className="flex justify-end gap-2 border-t px-5 py-3">{footer}</div>}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

/* ---------------------------------------------------------------- Dropdown menu */

export const DropdownMenu = Menu.Root;
export const DropdownMenuTrigger = Menu.Trigger;

export function DropdownMenuContent({
  className,
  children,
  ...props
}: React.ComponentProps<typeof Menu.Content>) {
  return (
    <Menu.Portal>
      <Menu.Content
        sideOffset={4}
        className={cn("z-50 min-w-44 rounded-md border bg-card p-1 shadow-lg", className)}
        {...props}
      >
        {children}
      </Menu.Content>
    </Menu.Portal>
  );
}

export function DropdownMenuItem({ className, ...props }: React.ComponentProps<typeof Menu.Item>) {
  return (
    <Menu.Item
      className={cn(
        "flex cursor-pointer select-none items-center gap-2 rounded px-2 py-1.5 text-[13px] outline-none data-[disabled]:opacity-50 data-[highlighted]:bg-muted [&_svg]:size-3.5 [&_svg]:text-muted-foreground",
        className,
      )}
      {...props}
    />
  );
}

export function DropdownMenuLabel({ className, ...props }: React.ComponentProps<typeof Menu.Label>) {
  return (
    <Menu.Label
      className={cn("px-2 py-1 text-[11px] font-medium text-muted-foreground", className)}
      {...props}
    />
  );
}

export function DropdownMenuSeparator() {
  return <Menu.Separator className="my-1 h-px bg-border" />;
}

/* ---------------------------------------------------------------- Popover & Tooltip */

export const Popover = PopoverPrimitive.Root;
export const PopoverTrigger = PopoverPrimitive.Trigger;
export const PopoverAnchor = PopoverPrimitive.Anchor;

export function PopoverContent({
  className,
  ...props
}: React.ComponentProps<typeof PopoverPrimitive.Content>) {
  return (
    <PopoverPrimitive.Portal>
      <PopoverPrimitive.Content
        sideOffset={4}
        className={cn("z-50 rounded-md border bg-card p-3 shadow-lg outline-none", className)}
        {...props}
      />
    </PopoverPrimitive.Portal>
  );
}

export function Tooltip({
  content,
  children,
  side = "bottom",
}: {
  content: React.ReactNode;
  children: React.ReactNode;
  side?: "top" | "bottom" | "left" | "right";
}) {
  return (
    <TooltipPrimitive.Root delayDuration={400}>
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
          side={side}
          sideOffset={4}
          className="z-50 max-w-xs rounded bg-foreground px-2 py-1 text-[11px] text-background shadow"
        >
          {content}
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}

export const TooltipProvider = TooltipPrimitive.Provider;

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      role="status"
      aria-label="Carregando"
      className={cn(
        "inline-block size-3.5 animate-spin rounded-full border-2 border-current border-t-transparent",
        className,
      )}
    />
  );
}

export function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="rounded border bg-muted px-1 font-mono text-[10px] text-muted-foreground">{children}</kbd>
  );
}

export function SectionTitle({ children, action }: { children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between">
      <h3 className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{children}</h3>
      {action}
    </div>
  );
}
