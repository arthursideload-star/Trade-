#!/usr/bin/env node

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  Tool,
} from '@modelcontextprotocol/sdk/types.js';

import { advancedStockFilter } from './tools/screening.js';
import { getFundamentalMetrics, analyzeValuationMetrics, calculateFinancialHealthScore } from './tools/fundamentals.js';
import { analyzeInsiderActivity } from './tools/insider.js';
import { analyzeRedditSentiment, getTrendingTickers } from './tools/social.js';
import { analyzeNewsAndMarketContext } from './tools/news.js';
import { getPutCallRatio } from './tools/options.js';
import { comprehensiveStockAnalysis } from './tools/comprehensive.js';
import { isRedditConfigured, isOpenAIConfigured } from './config.js';

const server = new Server(
  {
    name: 'trading-mcp',
    version: '1.0.0',
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

const tools: Tool[] = [
  {
    name: 'screen_stocks_advanced_filters',
    description: 'Comprehensive stock screening using Finviz filters that supports technical patterns, fundamental criteria, and multi-parameter filtering. Use this when you need to find stocks matching specific investment criteria like channel down patterns, profitable companies, or large-cap stocks. The tool returns a ranked list of stocks with key metrics including market cap, P/E ratios, and current prices. Supports complex filter combinations for advanced screening strategies using Finviz format parameters.',
    inputSchema: {
      type: 'object',
      properties: {
        filters: {
          type: 'object',
          description: 'Advanced filter parameters using Finviz format. Use "f" for basic filters including technical patterns (comma-separated), "o" for ordering. Technical patterns should use ta_pattern_* format (e.g., ta_pattern_channeldown). Example: {"f": "cap_large,fa_pe_profitable,geo_usa,ta_pattern_channeldown", "o": "marketcap"}',
          default: {},
        },
        limit: {
          type: 'number',
          description: 'Maximum number of results to return',
          default: 50,
        },
      },
    },
  },

  {
    name: 'get_fundamental_stock_metrics',
    description: 'Comprehensive fundamental analysis tool that retrieves detailed financial metrics including P/E ratios, PEG, ROE, debt ratios, growth rates, and profitability margins. Use this when conducting deep fundamental analysis of individual stocks for investment decisions or valuation assessments. The tool returns complete financial data with key ratios, growth metrics, and profitability indicators. Supports selective metric retrieval for targeted analysis.',
    inputSchema: {
      type: 'object',
      properties: {
        ticker: {
          type: 'string',
          description: 'Stock ticker symbol',
        },
        metrics: {
          type: 'array',
          items: { type: 'string' },
          description: 'Specific metrics to retrieve (optional, returns all if not specified)',
        },
      },
      required: ['ticker'],
    },
  },
  {
    name: 'compare_stock_valuations',
    description: 'Relative valuation analysis tool that compares key valuation metrics across multiple stocks to identify undervalued or overvalued opportunities. Use this when performing peer analysis, sector comparisons, or evaluating multiple investment candidates side-by-side. The tool returns a comparative analysis with P/E, PEG, Price-to-Book ratios and highlights relative value opportunities. Essential for making informed investment decisions based on relative attractiveness.',
    inputSchema: {
      type: 'object',
      properties: {
        tickers: {
          type: 'array',
          items: { type: 'string' },
          description: 'Array of stock ticker symbols to compare',
        },
        metrics: {
          type: 'array',
          items: { type: 'string' },
          description: 'Valuation metrics to compare',
          default: ['pe', 'forwardPE', 'peg', 'priceToBook'],
        },
      },
      required: ['tickers'],
    },
  },
  {
    name: 'calculate_financial_health_score',
    description: 'Financial health analysis tool that calculates a comprehensive score based on profitability, liquidity, leverage, efficiency, and growth metrics. Use this when evaluating the overall financial strength of a company for investment decisions, risk assessment, or portfolio screening. Returns a weighted health score (0-100) with detailed breakdowns of each category, component analysis, and actionable insights. Allows custom weighting of different financial factors to match your investment strategy.',
    inputSchema: {
      type: 'object',
      properties: {
        ticker: {
          type: 'string',
          description: 'Stock ticker symbol',
        },
        weights: {
          type: 'object',
          description: 'Custom weights for different health factors',
          properties: {
            profitability: { type: 'number', default: 0.3 },
            liquidity: { type: 'number', default: 0.2 },
            leverage: { type: 'number', default: 0.2 },
            efficiency: { type: 'number', default: 0.15 },
            growth: { type: 'number', default: 0.15 },
          },
        },
      },
      required: ['ticker'],
    },
  },

  {
    name: 'analyze_insider_activity',
    description: 'Comprehensive insider trading analysis tool that monitors recent transactions and analyzes sentiment patterns. Retrieves buy/sell activity by executives, directors, and major shareholders, then evaluates trading patterns to determine overall insider confidence (bullish, bearish, neutral). Returns detailed transaction history with sentiment analysis, confidence scores, and key insights about insider motivation. Essential for identifying stocks with strong insider support or potential red flags.',
    inputSchema: {
      type: 'object',
      properties: {
        ticker: {
          type: 'string',
          description: 'Stock ticker symbol',
        },
        limit: {
          type: 'number',
          description: 'Maximum number of transactions to return for display',
          default: 10,
        },
        transaction_types: {
          type: 'array',
          items: { type: 'string' },
          description: 'Filter by transaction types (buy, sell, etc.)',
        },
        analysis_period: {
          type: 'number',
          description: 'Analysis period in days for sentiment calculation',
          default: 90,
        },
        min_transaction_value: {
          type: 'number',
          description: 'Minimum transaction value to include in sentiment analysis',
          default: 10000,
        },
      },
      required: ['ticker'],
    },
  },

  {
    name: 'get_put_call_ratio',
    description: 'Options market analysis tool that retrieves put/call ratio data from Barchart to assess market sentiment and options flow. Use this when analyzing options market sentiment, detecting potential market reversals, or understanding institutional hedging activity. The tool returns comprehensive put/call ratios for different expiration dates, volume and open interest data, and AI-powered sentiment analysis. Higher put/call ratios typically indicate bearish sentiment, while lower ratios suggest bullish sentiment. Essential for options traders and investors looking to gauge market sentiment.',
    inputSchema: {
      type: 'object',
      properties: {
        ticker: {
          type: 'string',
          description: 'Stock ticker symbol',
        },
      },
      required: ['ticker'],
    },
  },

  {
    name: 'comprehensive_stock_analysis',
    description: 'Ultimate comprehensive stock analysis tool that combines multiple analyses in parallel to provide a complete investment evaluation. Executes fundamental metrics, financial health scoring, insider trading analysis, put/call ratio analysis, and when configured, news analysis and Reddit sentiment analysis. Use this when you need a complete overview of a stock across all analysis dimensions for investment decision-making. Returns a formatted report with all analysis results, key insights, and investment summary.',
    inputSchema: {
      type: 'object',
      properties: {
        ticker: {
          type: 'string',
          description: 'Stock ticker symbol to analyze',
        },
      },
      required: ['ticker'],
    },
  },
];

if (isRedditConfigured()) {
  tools.push(
    {
      name: 'discover_trending_stocks',
      description: 'Social momentum detection tool that identifies stocks gaining significant attention and discussion volume across Reddit investing communities. Use this when looking for emerging investment opportunities, detecting viral stock movements, or identifying potential meme stock candidates before they peak. The tool returns ranked lists of trending tickers with mention frequency, sentiment indicators, and community engagement metrics. Perfect for staying ahead of retail investor trends and social media-driven market movements.',
      inputSchema: {
        type: 'object',
        properties: {
          subreddits: {
            type: 'array',
            items: { type: 'string' },
            description: 'Subreddits to analyze for trending tickers',
            default: ['wallstreetbets', 'stocks'],
          },
          limit: {
            type: 'number',
            description: 'Maximum number of trending tickers to return',
            default: 20,
          },
        },
      },
    }
  );
}

if (isOpenAIConfigured()) {
  tools.push(
    {
      name: 'analyze_news_and_market_context',
      description: 'Comprehensive news and market analysis tool that combines recent news sentiment analysis, market impact assessment, and broader sector context analysis. Use this when researching current events affecting a stock, evaluating news-driven price movements, or understanding how individual stocks fit into current market trends. Returns analyzed articles with sentiment scores, impact predictions, sector performance analysis, and macroeconomic context. Essential for making informed investment decisions based on current market conditions.',
      inputSchema: {
        type: 'object',
        properties: {
          ticker: {
            type: 'string',
            description: 'Stock ticker symbol',
          },
          days_back: {
            type: 'number',
            description: 'Number of days to look back for news',
            default: 7,
          },
          max_articles: {
            type: 'number',
            description: 'Maximum number of articles to analyze',
            default: 10,
          },
          include_sentiment: {
            type: 'boolean',
            description: 'Include sentiment analysis for each article',
            default: true,
          },
          sector: {
            type: 'string',
            description: 'Stock sector for enhanced context analysis (optional)',
          },
          news_items: {
            type: 'array',
            items: { type: 'string' },
            description: 'Specific news headlines or summaries to analyze for market impact (optional)',
          },
        },
        required: ['ticker'],
      },
    }
  );
}

if (isRedditConfigured() && isOpenAIConfigured()) {
  tools.push({
    name: 'analyze_reddit_sentiment',
    description: 'Comprehensive Reddit sentiment analysis tool that searches for stock discussions across multiple investing subreddits and uses AI to analyze retail investor sentiment. Combines Reddit post search, optional comment extraction, and advanced sentiment classification to gauge community opinion and engagement. Use this when assessing retail investor sentiment, detecting sentiment shifts, or validating investment decisions against community consensus. Returns posts, sentiment analysis with confidence scores, key themes, and community engagement metrics.',
    inputSchema: {
      type: 'object',
      properties: {
        ticker: {
          type: 'string',
          description: 'Stock ticker symbol',
        },
        subreddits: {
          type: 'array',
          items: { type: 'string' },
          description: 'Subreddits to search for discussions',
          default: ['stocks', 'wallstreetbets', 'investing', 'ValueInvesting'],
        },
        time_filter: {
          type: 'string',
          enum: ['hour', 'day', 'week', 'month', 'year'],
          description: 'Time period to search within',
          default: 'week',
        },
        limit: {
          type: 'number',
          description: 'Maximum number of posts to retrieve',
          default: 25,
        },
        sort: {
          type: 'string',
          enum: ['relevance', 'hot', 'top', 'new'],
          description: 'Sort order for results',
          default: 'hot',
        },
        max_posts_for_sentiment: {
          type: 'number',
          description: 'Maximum number of posts to use for sentiment analysis',
          default: 50,
        },
        include_comments: {
          type: 'boolean',
          description: 'Whether to include comments from a specific post',
          default: false,
        },
        post_id_for_comments: {
          type: 'string',
          description: 'Specific post ID to retrieve comments from (optional)',
        },
        comment_limit: {
          type: 'number',
          description: 'Maximum number of comments to retrieve if include_comments is true',
          default: 100,
        },
      },
      required: ['ticker'],
    },
  });
}

server.setRequestHandler(ListToolsRequestSchema, async () => {
  return { tools };
});

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      case 'screen_stocks_advanced_filters':
        return await advancedStockFilter(args);

      case 'get_fundamental_stock_metrics':
        return await getFundamentalMetrics(args);
      case 'compare_stock_valuations':
        return await analyzeValuationMetrics(args);
      case 'calculate_financial_health_score':
        return await calculateFinancialHealthScore(args);

      case 'analyze_insider_activity':
        return await analyzeInsiderActivity(args);

      case 'get_put_call_ratio':
        return await getPutCallRatio(args);

      case 'discover_trending_stocks':
        return await getTrendingTickers(args);

      case 'analyze_news_and_market_context':
        return await analyzeNewsAndMarketContext(args);

      case 'analyze_reddit_sentiment':
        return await analyzeRedditSentiment(args);

      case 'comprehensive_stock_analysis':
        return await comprehensiveStockAnalysis(args);

      default:
        return {
          content: [
            {
              type: "text" as const,
              text: `Unknown tool: ${name}`,
            },
          ],
          isError: true,
        };
    }
  } catch (error) {
    console.error(`Error executing tool ${name}:`, error);
    return {
      content: [
        {
          type: "text" as const,
          text: `Error executing ${name}: ${error instanceof Error ? error.message : 'Unknown error'}`,
        },
      ],
      isError: true,
    };
  }
});

async function main() {
  const transport = new StdioServerTransport();
  
  console.error('Trading MCP Server starting...');
  console.error(`Configured tools: ${tools.length}`);
  console.error(`Reddit configured: ${isRedditConfigured()}`);
  console.error(`OpenAI configured: ${isOpenAIConfigured()}`);
  
  await server.connect(transport);
  console.error('Trading MCP Server running');
}

process.on('SIGINT', () => {
  console.error('Trading MCP Server shutting down...');
  process.exit(0);
});

process.on('SIGTERM', () => {
  console.error('Trading MCP Server shutting down...');
  process.exit(0);
});

main().catch((error) => {
  console.error('Server failed to start:', error);
  process.exit(1);
});
