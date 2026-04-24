import type { ButtonVariant, ControlSize, ControlTone } from './types';

const joinClasses = (...parts: Array<string | false | null | undefined>) =>
	parts.filter(Boolean).join(' ');

const sharedControlBase =
	'w-full rounded-[var(--radius-panel)] border bg-surface px-4 text-sm text-text shadow-sm outline-none transition duration-200 placeholder:text-text-muted/80 focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-canvas disabled:cursor-not-allowed disabled:opacity-60';

const controlToneClasses: Record<ControlTone, string> = {
	primary:
		'border-border focus-visible:border-primary focus-visible:ring-primary/40 hover:border-primary/60',
	secondary:
		'border-border focus-visible:border-text-muted focus-visible:ring-text-muted/30 hover:border-text-muted/60',
	success:
		'border-success/50 focus-visible:border-success focus-visible:ring-success/35 hover:border-success',
	danger:
		'border-danger/60 focus-visible:border-danger focus-visible:ring-danger/35 hover:border-danger'
};

const controlSizeClasses: Record<ControlSize, string> = {
	sm: 'min-h-10 py-2.5',
	md: 'min-h-11 py-3',
	lg: 'min-h-12 py-3.5 text-base'
};

const buttonBase =
	'inline-flex items-center justify-center gap-2 rounded-[var(--radius-pill)] font-medium transition duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-canvas disabled:pointer-events-none disabled:opacity-55';

const buttonVariantClasses: Record<ButtonVariant, string> = {
	primary: 'bg-primary text-canvas hover:bg-primary/90 focus-visible:ring-primary/45',
	secondary:
		'border border-border bg-surface-elevated text-text hover:border-text-muted/70 hover:bg-surface',
	success: 'bg-success text-canvas hover:bg-success/90 focus-visible:ring-success/40',
	danger: 'bg-danger text-canvas hover:bg-danger/90 focus-visible:ring-danger/40',
	ghost: 'text-text-muted hover:bg-surface-elevated hover:text-text'
};

const buttonSizeClasses: Record<ControlSize, string> = {
	sm: 'min-h-9 px-3 text-sm',
	md: 'min-h-10 px-4 text-sm',
	lg: 'min-h-12 px-5 text-base'
};

export const getControlClasses = ({ tone, size }: { tone: ControlTone; size: ControlSize }) =>
	joinClasses(sharedControlBase, controlToneClasses[tone], controlSizeClasses[size]);

export const getButtonClasses = ({
	variant,
	size,
	fullWidth
}: {
	variant: ButtonVariant;
	size: ControlSize;
	fullWidth: boolean;
}) =>
	joinClasses(
		buttonBase,
		buttonVariantClasses[variant],
		buttonSizeClasses[size],
		fullWidth && 'w-full'
	);
