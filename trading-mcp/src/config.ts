import { z } from 'zod';
import { Config } from './types/index.js';
import dotenv from 'dotenv';

/**
 * Configuration module for Trading MCP Server
 * Handles environment variable loading and validation
 */

// Load environment variables
dotenv.config();

/**
 * Zod schema for configuration validation
 * Ensures all configuration values are properly typed and optional where appropriate
 */
const ConfigSchema = z.object({
  openaiApiKey: z.string().optional(),
  reddit: z.object({
    clientId: z.string().optional(),
    clientSecret: z.string().optional(),
    username: z.string().optional(),
    password: z.string().optional(),
  }).optional(),
});

/**
 * Main configuration object
 * Parses and validates environment variables
 */
export const config: Config = ConfigSchema.parse({
  openaiApiKey: process.env.OPENAI_API_KEY,
  reddit: {
    clientId: process.env.REDDIT_CLIENT_ID,
    clientSecret: process.env.REDDIT_CLIENT_SECRET,
    username: process.env.REDDIT_USERNAME,
    password: process.env.REDDIT_PASSWORD,
  },
});

/**
 * Helper function to check if Reddit API is configured
 * @returns {boolean} True if all required Reddit credentials are available
 */
export const isRedditConfigured = (): boolean => {
  return !!(
    config.reddit?.clientId &&
    config.reddit?.clientSecret &&
    config.reddit?.username &&
    config.reddit?.password
  );
};

/**
 * Helper function to check if OpenAI API is configured
 * @returns {boolean} True if OpenAI API key is available
 */
export const isOpenAIConfigured = (): boolean => {
  return !!config.openaiApiKey;
};
