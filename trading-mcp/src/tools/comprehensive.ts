import { z } from 'zod';
import { FinvizAdapter } from '../adapters/finviz.js';
import { BarchartAdapter } from '../adapters/barchart.js';
import { OpenAIAdapter } from '../adapters/openai.js';
import { RedditAdapter } from '../adapters/reddit.js';
import { isRedditConfigured, isOpenAIConfigured } from '../config.js';
import { calculateInsiderSentiment } from './insider.js';

const ComprehensiveAnalysisSchema = z.object({
  ticker: z.string(),
});

// Define types for analysis results
type AnalysisResult = 
  | { type: string; data: any; error?: never }
  | { type: string; error: string; data?: never };

export async function comprehensiveStockAnalysis(args: unknown) {
  try {
    const { ticker } = ComprehensiveAnalysisSchema.parse(args);
    
    const results: any = {
      ticker: ticker.toUpperCase(),
      timestamp: new Date().toISOString(),
      analyses: {},
      errors: [],
      summary: {
        bullish_factors: [],
        bearish_factors: [],
        neutral_factors: [],
      },
    };

    // Initialize adapters
    const finviz = new FinvizAdapter();
    const barchart = new BarchartAdapter();
    const openai = isOpenAIConfigured() ? new OpenAIAdapter() : null;
    const reddit = isRedditConfigured() ? new RedditAdapter() : null;

    // Execute all analyses in parallel
    const analysisPromises: Promise<AnalysisResult>[] = [];

    // 1. Fundamental Analysis
    analysisPromises.push(
      finviz.getFundamentals(ticker)
        .then(data => ({ type: 'fundamentals', data }))
        .catch(error => ({ type: 'fundamentals', error: error.message }))
    );

    // 2. Insider Activity Analysis
    analysisPromises.push(
      finviz.getInsiderActivity(ticker)
        .then(insiderActivity => {
          const sentiment = calculateInsiderSentiment(insiderActivity.transactions, 90, 10000);
          return { type: 'insider', data: { ...insiderActivity, sentiment } };
        })
        .catch(error => ({ type: 'insider', error: error.message }))
    );

    // 3. Put/Call Ratio Analysis
    analysisPromises.push(
      barchart.getPutCallRatio(ticker)
        .then(data => ({ type: 'options', data }))
        .catch(error => ({ type: 'options', error: error.message }))
    );

    // 4. News Analysis (if OpenAI is configured)
    if (openai) {
      analysisPromises.push(
        Promise.all([
          openai.getLatestNews(ticker, 7, 10, true),
          openai.getMarketContext(ticker),
        ])
          .then(([newsAnalysis, marketContext]) => ({
            type: 'news',
            data: { newsAnalysis, marketContext }
          }))
          .catch(error => ({ type: 'news', error: error.message }))
      );
    }

    // 5. Reddit Sentiment Analysis (if both Reddit and OpenAI are configured)
    if (reddit && openai) {
      analysisPromises.push(
        reddit.searchPosts(ticker, ['stocks', 'wallstreetbets', 'investing'], 'week', 25, 'hot')
          .then(async (searchResult) => {
            if (searchResult.posts.length > 0) {
              const sentiment = await openai.analyzeSocialSentiment(searchResult.posts.slice(0, 20));
              return {
                type: 'social',
                data: { posts: searchResult.posts, sentiment }
              };
            }
            return { 
              type: 'social', 
              data: { posts: [], sentiment: null } 
            };
          })
          .catch(error => ({ type: 'social', error: error.message }))
      );
    }

    // Wait for all analyses to complete
    const analysisResults = await Promise.all(analysisPromises);

    // Process results
    analysisResults.forEach((result: AnalysisResult) => {
      if (result.error) {
        results.errors.push(`${result.type}: ${result.error}`);
      } else {
        results.analyses[result.type] = result.data;
      }
    });

    // Calculate Financial Health Score if fundamentals are available
    if (results.analyses.fundamentals) {
      try {
        const healthScore = calculateHealthScore(results.analyses.fundamentals);
        results.analyses.health_score = healthScore;
      } catch (error) {
        results.errors.push(`health_score: ${error instanceof Error ? error.message : 'Unknown error'}`);
      }
    }

    // Generate Summary Insights
    generateSummaryInsights(results);

    return {
      content: [
        {
          type: "text" as const,
          text: JSON.stringify(results, null, 2),
        },
      ],
    };
  } catch (error) {
    return {
      content: [
        {
          type: "text" as const,
          text: `Error in comprehensive analysis: ${error instanceof Error ? error.message : 'Unknown error'}`,
        },
      ],
      isError: true,
    };
  }
}

function calculateHealthScore(fundamentals: any) {
  const weights = {
    profitability: 0.3,
    liquidity: 0.2,
    leverage: 0.2,
    efficiency: 0.15,
    growth: 0.15,
  };

  let score = 50; // neutral start
  const components: any = {};

  // Profitability Score
  if (fundamentals.profitMargin) {
    const margin = parseFloat(fundamentals.profitMargin.replace('%', ''));
    if (!isNaN(margin)) {
      components.profitability = Math.min(100, Math.max(0, 50 + margin * 2));
    }
  }

  // Liquidity Score
  if (fundamentals.currentRatio) {
    const ratio = parseFloat(fundamentals.currentRatio);
    if (!isNaN(ratio)) {
      if (ratio >= 1.5 && ratio <= 3) {
        components.liquidity = 90;
      } else if (ratio >= 1 && ratio < 1.5) {
        components.liquidity = 70;
      } else if (ratio > 3) {
        components.liquidity = 60;
      } else {
        components.liquidity = 20;
      }
    }
  }

  // Leverage Score
  if (fundamentals.debtToEquity) {
    const debtToEquity = parseFloat(fundamentals.debtToEquity);
    if (!isNaN(debtToEquity)) {
      if (debtToEquity <= 0.3) {
        components.leverage = 90;
      } else if (debtToEquity <= 0.6) {
        components.leverage = 70;
      } else if (debtToEquity <= 1.0) {
        components.leverage = 50;
      } else {
        components.leverage = Math.max(10, 50 - (debtToEquity - 1) * 20);
      }
    }
  }

  // Calculate overall score
  const componentValues = Object.values(components) as number[];
  if (componentValues.length > 0) {
    score = componentValues.reduce((sum, val) => sum + val, 0) / componentValues.length;
  }

  let rating = 'Poor';
  if (score >= 80) rating = 'Excellent';
  else if (score >= 70) rating = 'Good';
  else if (score >= 60) rating = 'Fair';
  else if (score >= 40) rating = 'Below Average';

  return {
    overall_score: Math.round(score),
    rating,
    components,
  };
}

function generateSummaryInsights(results: any) {
  const { analyses, summary } = results;

  // Fundamental Analysis Insights
  if (analyses.fundamentals) {
    const fund = analyses.fundamentals;
    if (fund.pe && parseFloat(fund.pe) < 15) {
      summary.bullish_factors.push('Low P/E ratio indicates potential value');
    }
    if (fund.pe && parseFloat(fund.pe) > 30) {
      summary.bearish_factors.push('High P/E ratio may indicate overvaluation');
    }
    if (fund.debtToEquity && parseFloat(fund.debtToEquity) < 0.3) {
      summary.bullish_factors.push('Low debt-to-equity ratio shows financial stability');
    }
  }

  // Health Score Insights
  if (analyses.health_score) {
    const score = analyses.health_score.overall_score;
    if (score >= 80) {
      summary.bullish_factors.push(`Excellent financial health score (${score}/100)`);
    } else if (score >= 60) {
      summary.neutral_factors.push(`Adequate financial health score (${score}/100)`);
    } else {
      summary.bearish_factors.push(`Poor financial health score (${score}/100)`);
    }
  }

  // Insider Analysis Insights
  if (analyses.insider && analyses.insider.sentiment) {
    const sentiment = analyses.insider.sentiment.overall_sentiment;
    if (sentiment === 'bullish') {
      summary.bullish_factors.push('Insider sentiment is bullish - insiders are net buyers');
    } else if (sentiment === 'bearish') {
      summary.bearish_factors.push('Insider sentiment is bearish - insiders are net sellers');
    } else {
      summary.neutral_factors.push('Insider sentiment is neutral');
    }
  }

  // Options Analysis Insights
  if (analyses.options) {
    const putCallRatio = analyses.options.overallPutCallVolumeRatio;
    if (putCallRatio > 1.2) {
      summary.bearish_factors.push(`High put/call ratio (${putCallRatio.toFixed(2)}) indicates bearish options sentiment`);
    } else if (putCallRatio < 0.8) {
      summary.bullish_factors.push(`Low put/call ratio (${putCallRatio.toFixed(2)}) indicates bullish options sentiment`);
    } else {
      summary.neutral_factors.push(`Put/call ratio (${putCallRatio.toFixed(2)}) is in normal range`);
    }
  }

  // News Analysis Insights
  if (analyses.news && analyses.news.newsAnalysis) {
    const sentiment = analyses.news.newsAnalysis.overallSentiment;
    if (sentiment === 'positive') {
      summary.bullish_factors.push('Recent news sentiment is positive');
    } else if (sentiment === 'negative') {
      summary.bearish_factors.push('Recent news sentiment is negative');
    } else {
      summary.neutral_factors.push('Recent news sentiment is neutral');
    }
  }

  // Social Media Insights
  if (analyses.social && analyses.social.sentiment) {
    const sentiment = analyses.social.sentiment.overallSentiment;
    if (sentiment === 'bullish') {
      summary.bullish_factors.push('Reddit community sentiment is bullish');
    } else if (sentiment === 'bearish') {
      summary.bearish_factors.push('Reddit community sentiment is bearish');
    } else {
      summary.neutral_factors.push('Reddit community sentiment is neutral');
    }
  }

  // Overall Assessment
  const bullishCount = summary.bullish_factors.length;
  const bearishCount = summary.bearish_factors.length;
  
  if (bullishCount > bearishCount + 1) {
    summary.overall_sentiment = 'Bullish';
  } else if (bearishCount > bullishCount + 1) {
    summary.overall_sentiment = 'Bearish';
  } else {
    summary.overall_sentiment = 'Mixed/Neutral';
  }
} 