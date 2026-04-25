export const controlTones = ['primary', 'secondary', 'success', 'danger'] as const;
export type ControlTone = (typeof controlTones)[number];

export const controlSizes = ['sm', 'md', 'lg'] as const;
export type ControlSize = (typeof controlSizes)[number];

export const buttonVariants = ['primary', 'secondary', 'success', 'danger', 'ghost'] as const;
export type ButtonVariant = (typeof buttonVariants)[number];
