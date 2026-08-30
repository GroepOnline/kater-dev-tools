import { z } from 'zod';

/**
 * Zod schema defining and validating all environment variables listed in .env.example.
 */
export const envSchema = z.object({
  PORT: z
    .string()
    .optional()
    .default('3000')
    .transform((val, ctx) => {
      const parsed = parseInt(val, 10);
      if (isNaN(parsed) || parsed <= 0 || parsed > 65535) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: `PORT must be a valid port number between 1 and 65535, received: ${val}`,
        });
        return z.NEVER;
      }
      return parsed;
    }),
  NODE_ENV: z
    .enum(['development', 'production', 'test'], {
      errorMap: () => ({ message: "NODE_ENV must be 'development', 'production', or 'test'" }),
    })
    .default('development'),
  KATER_AUTH_MODE: z
    .string()
    .min(1, 'KATER_AUTH_MODE cannot be empty')
    .default('none'),
  KATER_DEFAULT_PROFILE: z
    .string()
    .min(1, 'KATER_DEFAULT_PROFILE cannot be empty')
    .default('core'),
  KATER_PROFILE: z
    .string()
    .optional(),
  KATER_STORAGE_BACKEND: z
    .string()
    .min(1, 'KATER_STORAGE_BACKEND cannot be empty')
    .default('sqlite'),
  KATER_CORS_ORIGINS: z
    .string()
    .min(1, 'KATER_CORS_ORIGINS cannot be empty')
    .default('*'),
});

export type EnvConfig = z.infer<typeof envSchema>;

/**
 * Validates environment variables against the Zod schema.
 * Throws a formatted Error if any variable is missing or malformed.
 */
export function validateConfig(env: NodeJS.ProcessEnv = process.env): EnvConfig {
  const result = envSchema.safeParse(env);
  if (!result.success) {
    const errorDetails = result.error.issues
      .map((issue) => `  - ${issue.path.join('.') || 'root'}: ${issue.message}`)
      .join('\n');
    const errorMessage = `❌ Environment configuration validation failed:\n${errorDetails}`;
    console.error(errorMessage);
    throw new Error(errorMessage);
  }
  return result.data;
}

export const config: EnvConfig = validateConfig(process.env);
export default config;
