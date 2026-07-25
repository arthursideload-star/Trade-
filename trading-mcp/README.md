# Trading MCP Server

A comprehensive Model Context Protocol (MCP) server for stock analysis and trading insights. This server provides advanced stock screening, fundamental analysis, insider trading data, social media sentiment, and news analysis capabilities.

## 🎬 Demo

https://github.com/user-attachments/assets/71995014-7cbb-48fa-80fb-f1f6d22fc91c

*See the Trading MCP Server in action - from stock screening to comprehensive analysis*

## 📋 MCP Configuration

Add this to your MCP configuration file (typically `~/.cursor/mcp.json` or your IDE's MCP settings):

```json
{
  "mcpServers": {
    "trading-mcp": {
      "command": "node",
      "args": ["/path/to/trading-mcp/dist/server.js"],
      "env": {
        "OPENAI_API_KEY": "sk-your-openai-api-key-here",
        "REDDIT_CLIENT_ID": "your-reddit-client-id",
        "REDDIT_CLIENT_SECRET": "your-reddit-client-secret",
        "REDDIT_USERNAME": "your-reddit-username",
        "REDDIT_PASSWORD": "your-reddit-password"
      }
    }
  }
}
```

## 🚀 Features

- **📊 Stock Screening**: Technical pattern recognition and advanced multi-criteria filtering
- **📈 Fundamental Analysis**: Comprehensive metrics, valuation comparison, and AI health scoring
- **🏢 Insider Trading**: Real-time insider activity tracking and sentiment analysis
- **📊 Options Analysis**: Put/call ratio data and options market sentiment analysis
- **💭 Social Media Research**: Reddit integration with AI-powered sentiment analysis
- **📰 News Analysis**: AI-curated news with market impact assessment
- **🎯 Comprehensive Analysis**: All-in-one stock analysis combining multiple data sources

## 📚 Available Tools

**Note:** 
- OpenAI API key is required for news analysis and social sentiment analysis
- Reddit credentials are required for social media research features

### Stock Screening Tools

#### `screen_stocks_advanced_filters`
Advanced stock screening using Finviz filters with support for technical patterns, fundamental criteria, and multi-parameter filtering. Returns stocks matching specific criteria with key metrics.

**Parameters:**
- `filters` (object): Finviz format filters. Use "f" for basic filters, "o" for ordering. Example: `{"f": "cap_large,fa_pe_profitable,ta_pattern_channeldown", "o": "marketcap"}`
- `limit` (number, default: 50): Maximum results to return

### Fundamental Analysis Tools

#### `get_fundamental_stock_metrics`
Retrieves comprehensive financial metrics including P/E ratios, PEG, ROE, debt ratios, growth rates, and profitability margins.

**Parameters:**
- `ticker` (string, required): Stock ticker symbol
- `metrics` (array, optional): Specific metrics to retrieve (returns all if not specified)

#### `compare_stock_valuations`
Compares valuation metrics across multiple stocks to identify relative value opportunities. Perfect for peer analysis and sector comparisons.

**Parameters:**
- `tickers` (array, required): Stock ticker symbols to compare
- `metrics` (array, default: ['pe', 'forwardPE', 'peg', 'priceToBook']): Valuation metrics to compare

#### `calculate_financial_health_score`
Calculates a comprehensive financial health score (0-100) based on profitability, liquidity, leverage, efficiency, and growth metrics with customizable weightings.

**Parameters:**
- `ticker` (string, required): Stock ticker symbol
- `weights` (object, optional): Custom weights for health factors
  - `profitability` (default: 0.3), `liquidity` (default: 0.2), `leverage` (default: 0.2), `efficiency` (default: 0.15), `growth` (default: 0.15)

### Insider Trading Tools

#### `analyze_insider_activity`
Monitors insider transactions and analyzes sentiment patterns. Returns transaction history with sentiment analysis and confidence scores.

**Parameters:**
- `ticker` (string, required): Stock ticker symbol
- `limit` (number, default: 10): Maximum transactions to return
- `transaction_types` (array, optional): Filter by transaction types
- `analysis_period` (number, default: 90): Analysis period in days
- `min_transaction_value` (number, default: 10000): Minimum transaction value threshold

### Options Analysis Tools

#### `get_put_call_ratio`
Retrieves put/call ratio data from Barchart to assess options market sentiment. Returns ratios by expiration with sentiment analysis.

**Parameters:**
- `ticker` (string, required): Stock ticker symbol

### Comprehensive Analysis Tools

#### `comprehensive_stock_analysis`
All-in-one stock analysis combining fundamental metrics, financial health scoring, insider analysis, options sentiment, news analysis, and social sentiment when configured.

**Parameters:**
- `ticker` (string, required): Stock ticker symbol to analyze

### Social Media Research Tools
*Requires Reddit API configuration*

#### `discover_trending_stocks`
Identifies stocks gaining attention across Reddit investing communities. Returns trending tickers with mention frequency and engagement metrics.

**Parameters:**
- `subreddits` (array, default: ['wallstreetbets', 'stocks']): Subreddits to analyze
- `limit` (number, default: 20): Maximum trending tickers to return

#### `analyze_reddit_sentiment`
*Requires both Reddit and OpenAI APIs*

Searches Reddit discussions and uses AI to analyze retail investor sentiment. Returns posts with sentiment analysis and confidence scores.

**Parameters:**
- `ticker` (string, required): Stock ticker symbol
- `subreddits` (array, default: ['stocks', 'wallstreetbets', 'investing', 'ValueInvesting']): Subreddits to search
- `time_filter` (string, default: 'week'): Time period ('hour', 'day', 'week', 'month', 'year')
- `limit` (number, default: 25): Maximum posts to retrieve
- `sort` (string, default: 'hot'): Sort order ('relevance', 'hot', 'top', 'new')
- `max_posts_for_sentiment` (number, default: 50): Posts to use for sentiment analysis
- `include_comments` (boolean, default: false): Include comments from specific post
- `post_id_for_comments` (string, optional): Post ID for comment retrieval
- `comment_limit` (number, default: 100): Maximum comments if including comments

### News Analysis Tools
*Requires OpenAI API configuration*

#### `analyze_news_and_market_context`
Combines news sentiment analysis, market impact assessment, and sector context analysis. Returns analyzed articles with sentiment scores and market predictions.

**Parameters:**
- `ticker` (string, required): Stock ticker symbol
- `days_back` (number, default: 7): Days to look back for news
- `max_articles` (number, default: 10): Maximum articles to analyze
- `include_sentiment` (boolean, default: true): Include sentiment analysis
- `sector` (string, optional): Stock sector for enhanced context
- `news_items` (array, optional): Specific headlines to analyze

## 🛠️ Installation & Setup

### Installation

1. **Clone and install dependencies:**
```bash
git clone <repository-url>
cd trading-mcp
npm install
```

2. **Build the project:**
```bash
npm run build
```

3. **Configure in your MCP client:**
Add the MCP configuration shown above to your MCP client settings with your API credentials.

## 🔧 Configuration

### Required APIs
- **OpenAI**: Required for news analysis and social sentiment analysis
- **Reddit**: Required for social media research features

### Getting API Keys

#### OpenAI API Key
1. Visit [OpenAI API](https://platform.openai.com/api-keys)
2. Create an account or sign in
3. Generate a new API key
4. Add to your MCP configuration as `OPENAI_API_KEY`

#### Reddit API Credentials
1. Visit [Reddit App Preferences](https://www.reddit.com/prefs/apps)
2. Click "Create App" or "Create Another App"
3. Choose "script" as the app type
4. Use a dummy redirect URI such as `http://localhost:8080`
5. Note your `client_id` and `client_secret`
6. Add your Reddit credentials to your MCP configuration

## 🏗️ Architecture

```
trading-mcp/
├── src/
│   ├── server.ts          # Main MCP server
│   ├── config.ts          # Configuration management
│   ├── types/             # TypeScript interfaces
│   │   └── index.ts
│   ├── adapters/          # External API adapters
│   │   ├── finviz.ts      # Finviz web scraping
│   │   ├── barchart.ts    # Barchart options data scraping
│   │   ├── reddit.ts      # Reddit API integration
│   │   └── openai.ts      # OpenAI API integration
│   └── tools/             # Tool implementations
│       ├── screening.ts   # Stock screening tools
│       ├── fundamentals.ts # Fundamental analysis
│       ├── insider.ts     # Insider trading analysis
│       ├── options.ts     # Options analysis tools
│       ├── social.ts      # Social media research
│       ├── news.ts        # News analysis
│       └── comprehensive.ts # Comprehensive analysis
├── dist/                  # Compiled JavaScript
├── package.json
├── tsconfig.json
└── README.md
```

## 🐛 Known Issues

- Finviz web scraping may occasionally fail due to rate limiting or site changes
- Barchart web scraping may occasionally fail due to site changes or rate limiting
- Reddit API has rate limits that may affect high-volume usage
- OpenAI API usage incurs costs based on tokens consumed

## 📊 Example Usage

Once configured, you can use the tools through your MCP-enabled client:

```
# Screen for stocks with specific technical patterns
Use screen_stocks_advanced_filters with filters: {"f": "ta_pattern_channeldown,cap_large,geo_usa"}

# Get comprehensive fundamental analysis
Use get_fundamental_stock_metrics for "AAPL" to see detailed financial data

# Compare multiple stocks
Use compare_stock_valuations for ["AAPL", "MSFT", "GOOGL"] to compare valuations

# Calculate financial health score
Use calculate_financial_health_score for "TSLA" to get AI-powered health assessment

# Analyze insider activity
Use analyze_insider_activity for "NVDA" to see insider trading patterns and sentiment

# Get options market sentiment
Use get_put_call_ratio for "SPY" to see put/call ratios and options sentiment

# Comprehensive analysis (all-in-one)
Use comprehensive_stock_analysis for "AMZN" to get complete multi-dimensional analysis

# Analyze social sentiment (requires Reddit + OpenAI)
Use analyze_reddit_sentiment for "GME" to see Reddit community sentiment

# Get trending stocks (requires Reddit)
Use discover_trending_stocks to find stocks gaining social media momentum

# Analyze news and market context (requires OpenAI)
Use analyze_news_and_market_context for "META" to get news analysis and market context
```

## ⚠️ Disclaimer

This software is for educational and research purposes only. It is not intended as financial advice. Always do your own research and consider consulting with a qualified financial advisor before making investment decisions.

The data provided by this server comes from third-party sources and may not always be accurate or up-to-date. Users should verify information independently before making any trading decisions.

Stock trading and investing involves risk, including the potential loss of principal. Past performance does not guarantee future results.

---

For questions or support, please open an issue on GitHub.
