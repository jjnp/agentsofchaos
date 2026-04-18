import * as v from 'valibot';

const hexColorSchema = v.pipe(
	v.string(),
	v.regex(/^#(?:[0-9a-fA-F]{3}){1,2}$/, 'Expected a valid hex color')
);

const themeColorsSchema = v.object({
	canvas: hexColorSchema,
	surface: hexColorSchema,
	surfaceElevated: hexColorSchema,
	border: hexColorSchema,
	text: hexColorSchema,
	textMuted: hexColorSchema,
	primary: hexColorSchema,
	primaryAccent: hexColorSchema,
	success: hexColorSchema,
	warning: hexColorSchema,
	danger: hexColorSchema
});

export const themeColors = v.parse(themeColorsSchema, {
	canvas: '#0c0d0a',
	surface: '#12130f',
	surfaceElevated: '#15150f',
	border: '#27271c',
	text: '#d6d3b8',
	textMuted: '#7a7960',
	primary: '#e8d548',
	primaryAccent: '#baf246',
	success: '#baf246',
	warning: '#f1a457',
	danger: '#ff5f56'
});

export type ThemeColors = typeof themeColors;
export type ThemeColorName = keyof ThemeColors;

export const themeRadii = {
	panel: '1.5rem',
	pill: '999px'
} as const;

export type ThemeRadiusName = keyof typeof themeRadii;
