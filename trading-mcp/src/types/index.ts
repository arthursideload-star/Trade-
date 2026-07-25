/**
 * TypeScript type definitions for Trading MCP Server
 * Contains interfaces for stock data, API responses, and configuration
 */

/**
 * Result from stock screening operations
 * Contains basic information about stocks matching screening criteria
 */
export interface ScreeningResult {
  ticker: string;
  company: string;
  sector: string;
  industry: string;
  country: string;
  marketCap: string;
  pe: string;
  price: string;
  change: string;
  volume: string;
}

/**
 * Configuration for advanced filtering
 * Allows specification of different filter categories
 */
export interface FilterConfig {
  technical?: string[];
  fundamental?: string[];
  descriptive?: string[];
  performance?: string[];
}

/**
 * Comprehensive fundamental metrics for a stock
 * Contains financial ratios, performance indicators, and valuation metrics
 */
export interface FundamentalMetrics {
  ticker: string;
  rsi14?: string;
  sma200?: string;
  pe?: string;
  forwardPE?: string;
  peg?: string;
  currentRatio?: string;
  insiderOwn?: string;
  shortFloat?: string;
  profitMargin?: string;
  marketCap?: string;
  epsGrowth?: string;
  salesGrowth?: string;
  debtToEquity?: string;
  priceToBook?: string;
  returnOnEquity?: string;
}

/**
 * Individual insider trading transaction
 * Represents a single buy/sell transaction by a company insider
 */
export interface InsiderTransaction {
  insider: string;
  relationship: string;
  date: string;
  transactionType: string;
  cost: string;
  shares: string;
  value: string;
  sharesTotal: string;
}

/**
 * Complete insider activity summary for a stock
 * Contains all recent transactions and metadata
 */
export interface InsiderActivity {
  ticker: string;
  transactions: InsiderTransaction[];
  totalTransactions: number;
}

/**
 * Individual Reddit post data
 * Contains post metadata and content for sentiment analysis
 */
export interface RedditPost {
  title: string;
  author: string;
  score: number;
  numComments: number;
  url: string;
  createdUtc: string;
  subreddit: string;
  selftext: string;
}

/**
 * Result from Reddit search operations
 * Contains posts and search metadata
 */
export interface RedditSearchResult {
  posts: RedditPost[];
  totalFound: number;
  searchQuery: string;
}

/**
 * Individual news article data
 * Contains article content and analysis metadata
 */
export interface NewsArticle {
  headline: string;
  summary: string;
  source: string;
  url: string;
  publishedAt: string;
  sentiment?: 'positive' | 'negative' | 'neutral';
  impactScore?: number;
}

/**
 * Complete news analysis for a stock
 * Contains articles and AI-powered analysis results
 */
export interface NewsAnalysis {
  ticker: string;
  articles: NewsArticle[];
  overallSentiment: 'positive' | 'negative' | 'neutral';
  keyThemes: string[];
  marketImpact: 'high' | 'medium' | 'low';
}

/**
 * Configuration interface for the application
 * Defines optional API credentials and settings
 */
export interface Config {
  openaiApiKey?: string;
  reddit?: {
    clientId?: string;
    clientSecret?: string;
    username?: string;
    password?: string;
  };
}

export interface PutCallRatioData {
  expirationDate: string;
  putVolume: number;
  callVolume: number;
  putCallVolumeRatio: number;
  putOpenInterest: number;
  callOpenInterest: number;
  putCallOIRatio: number;
  totalVolume: number;
  totalOpenInterest: number;
}

export interface PutCallRatioAnalysis {
  ticker: string;
  currentPrice?: string;
  overallPutCallVolumeRatio: number;
  overallPutCallOIRatio: number;
  totalPutVolume: number;
  totalCallVolume: number;
  totalPutOI: number;
  totalCallOI: number;
  ratiosByDate: PutCallRatioData[];
  analysis: {
    sentiment: 'bullish' | 'bearish' | 'neutral';
    interpretation: string;
    keyInsights: string[];
  };
  validationResult: {
    isValid: boolean;
    warnings: string[];
  };
}
