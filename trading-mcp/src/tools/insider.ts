import { z } from 'zod';
import { FinvizAdapter } from '../adapters/finviz.js';
import { InsiderTransaction } from '../types/index.js';

const InsiderActivitySchema = z.object({
  ticker: z.string(),
  limit: z.number().default(10),
  transaction_types: z.array(z.string()).optional(),
  analysis_period: z.number().default(90),
  min_transaction_value: z.number().default(10000),
});

/**
 * Utility class for processing insider transactions
 */
class InsiderTransactionProcessor {
  private transactions: InsiderTransaction[];
  private analysisPeriod: number;
  private minValue: number;

  constructor(transactions: InsiderTransaction[], analysisPeriod: number, minValue: number) {
    this.transactions = transactions;
    this.analysisPeriod = analysisPeriod;
    this.minValue = minValue;
  }

  /**
   * Filter transactions based on date and minimum value
   */
  getRelevantTransactions(): InsiderTransaction[] {
    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - this.analysisPeriod);
    
    return this.transactions.filter(transaction => {
      const transactionDate = parseTransactionDate(transaction.date);
      const transactionValue = parseTransactionValue(transaction.value);
      
      return transactionDate >= cutoffDate && Math.abs(transactionValue) >= this.minValue;
    });
  }

  /**
   * Categorize transactions into buys and sells
   */
  categorizeTransactions(relevantTransactions: InsiderTransaction[]) {
    const buyTransactions: InsiderTransaction[] = [];
    const sellTransactions: InsiderTransaction[] = [];
    let totalBuyValue = 0;
    let totalSellValue = 0;
    
    const insiderTypes: { [key: string]: { buys: number; sells: number; net_value: number } } = {};
    
    relevantTransactions.forEach(transaction => {
      const value = parseTransactionValue(transaction.value);
      const type = transaction.transactionType.toLowerCase();
      const relationship = transaction.relationship.toLowerCase();
      
      // Initialize insider type tracking
      if (!insiderTypes[relationship]) {
        insiderTypes[relationship] = { buys: 0, sells: 0, net_value: 0 };
      }
      
      if (isBuyTransaction(type)) {
        buyTransactions.push(transaction);
        totalBuyValue += Math.abs(value);
        insiderTypes[relationship].buys++;
        insiderTypes[relationship].net_value += Math.abs(value);
      } else if (isSellTransaction(type)) {
        sellTransactions.push(transaction);
        totalSellValue += Math.abs(value);
        insiderTypes[relationship].sells++;
        insiderTypes[relationship].net_value -= Math.abs(value);
      }
    });

    return {
      buyTransactions,
      sellTransactions,
      totalBuyValue,
      totalSellValue,
      insiderTypes,
    };
  }

  /**
   * Calculate sentiment based on transaction ratios
   */
  calculateSentiment(totalBuyValue: number, totalSellValue: number, transactionCount: number): {
    sentiment: 'bullish' | 'bearish' | 'neutral';
    confidence: 'high' | 'medium' | 'low';
  } {
    const totalValue = totalBuyValue + totalSellValue;
    const buyRatio = totalValue > 0 ? totalBuyValue / totalValue : 0;
    
    let sentiment: 'bullish' | 'bearish' | 'neutral';
    let confidence: 'high' | 'medium' | 'low';
    
    // Determine sentiment
    if (buyRatio >= 0.7) {
      sentiment = 'bullish';
    } else if (buyRatio <= 0.3) {
      sentiment = 'bearish';
    } else {
      sentiment = 'neutral';
    }
    
    // Determine confidence
    if (transactionCount >= 10 && totalValue >= 1000000) {
      confidence = 'high';
    } else if (transactionCount >= 5 && totalValue >= 500000) {
      confidence = 'medium';
    } else {
      confidence = 'low';
    }

    return { sentiment, confidence };
  }
}

export async function analyzeInsiderActivity(args: unknown) {
  try {
    const { ticker, limit, transaction_types, analysis_period, min_transaction_value } = InsiderActivitySchema.parse(args);
    
    const finviz = new FinvizAdapter();
    const insiderActivity = await finviz.getInsiderActivity(ticker);
    
    // Filter by transaction types if specified
    let filteredTransactions = insiderActivity.transactions;
    if (transaction_types && transaction_types.length > 0) {
      filteredTransactions = insiderActivity.transactions.filter(transaction =>
        transaction_types.some(type => 
          transaction.transactionType.toLowerCase().includes(type.toLowerCase())
        )
      );
    }
    
    // Limit results for display
    const limitedTransactions = filteredTransactions.slice(0, limit);
    
    // Calculate sentiment analysis using all transactions (not limited)
    const sentiment = calculateInsiderSentiment(insiderActivity.transactions, analysis_period, min_transaction_value);
    
    return {
      content: [
        {
          type: "text" as const,
          text: JSON.stringify({
            ticker: ticker.toUpperCase(),
            transactions: limitedTransactions,
            total_transactions: limitedTransactions.length,
            filtered_by: transaction_types || 'all types',
            analysis_period_days: analysis_period,
            min_transaction_value,
            sentiment_analysis: sentiment,
            summary: `Found ${limitedTransactions.length} insider transactions for ${ticker.toUpperCase()}. Insider sentiment: ${sentiment.overall_sentiment} (${sentiment.confidence_level} confidence)`,
          }, null, 2),
        },
      ],
    };
  } catch (error) {
    return {
      content: [
        {
          type: "text" as const,
          text: `Error analyzing insider activity for ${args && typeof args === 'object' && 'ticker' in args ? (args as any).ticker : 'unknown ticker'}: ${error instanceof Error ? error.message : 'Unknown error'}`,
        },
      ],
      isError: true,
    };
  }
}

export function calculateInsiderSentiment(transactions: InsiderTransaction[], analysisPeriod: number, minValue: number) {
  const processor = new InsiderTransactionProcessor(transactions, analysisPeriod, minValue);
  const relevantTransactions = processor.getRelevantTransactions();
  
  if (relevantTransactions.length === 0) {
    return {
      overall_sentiment: 'neutral',
      confidence_level: 'low',
      transaction_summary: {
        total_transactions: 0,
        buy_transactions: 0,
        sell_transactions: 0,
        total_buy_value: 0,
        total_sell_value: 0,
      },
      key_insights: ['No significant insider transactions found in the analysis period'],
      insider_types: {},
    };
  }
  
  const {
    buyTransactions,
    sellTransactions, 
    totalBuyValue,
    totalSellValue,
    insiderTypes,
  } = processor.categorizeTransactions(relevantTransactions);

  const { sentiment, confidence } = processor.calculateSentiment(
    totalBuyValue,
    totalSellValue,
    relevantTransactions.length
  );

  const netValue = totalBuyValue - totalSellValue;
  const totalValue = totalBuyValue + totalSellValue;
  const buyRatio = totalValue > 0 ? totalBuyValue / totalValue : 0;
  
  // Generate insights
  const keyInsights = generateInsiderInsights(
    buyTransactions,
    sellTransactions,
    totalBuyValue,
    totalSellValue,
    insiderTypes
  );
  
  return {
    overall_sentiment: sentiment,
    confidence_level: confidence,
    transaction_summary: {
      total_transactions: relevantTransactions.length,
      buy_transactions: buyTransactions.length,
      sell_transactions: sellTransactions.length,
      total_buy_value: totalBuyValue,
      total_sell_value: totalSellValue,
      net_value: netValue,
      buy_ratio: Math.round(buyRatio * 100) / 100,
    },
    key_insights: keyInsights,
    insider_types: insiderTypes,
    recent_significant_transactions: getSignificantTransactions(relevantTransactions, 5),
  };
}

function parseTransactionDate(dateStr: string): Date {
  // Handle various date formats that might come from Finviz
  const formats = [
    /(\d{1,2})\/(\d{1,2})\/(\d{2,4})/, // MM/DD/YY or MM/DD/YYYY
    /(\d{4})-(\d{1,2})-(\d{1,2})/, // YYYY-MM-DD
  ];
  
  for (const format of formats) {
    const match = dateStr.match(format);
    if (match) {
      if (format.source.includes('\/')) {
        // MM/DD/YY format
        const month = parseInt(match[1]) - 1; // JS months are 0-indexed
        const day = parseInt(match[2]);
        let year = parseInt(match[3]);
        if (year < 100) year += 2000; // Convert 2-digit year
        return new Date(year, month, day);
      } else {
        // YYYY-MM-DD format
        const year = parseInt(match[1]);
        const month = parseInt(match[2]) - 1;
        const day = parseInt(match[3]);
        return new Date(year, month, day);
      }
    }
  }
  
  // Fallback: try direct parsing
  const parsed = new Date(dateStr);
  return isNaN(parsed.getTime()) ? new Date(0) : parsed;
}

function parseTransactionValue(valueStr: string): number {
  // Remove commas, dollar signs, and other formatting
  const cleaned = valueStr.replace(/[$,\s]/g, '');
  
  // Handle negative values (sells are often negative)
  const isNegative = cleaned.includes('-') || cleaned.includes('(');
  const numStr = cleaned.replace(/[-()]/g, '');
  
  const value = parseFloat(numStr);
  return isNaN(value) ? 0 : (isNegative ? -Math.abs(value) : Math.abs(value));
}

function isBuyTransaction(type: string): boolean {
  const buyKeywords = ['buy', 'purchase', 'acquire', 'exercise', 'conversion'];
  return buyKeywords.some(keyword => type.includes(keyword));
}

function isSellTransaction(type: string): boolean {
  const sellKeywords = ['sell', 'sale', 'dispose', 'gift'];
  return sellKeywords.some(keyword => type.includes(keyword));
}

function generateInsiderInsights(
  buyTransactions: InsiderTransaction[],
  sellTransactions: InsiderTransaction[],
  totalBuyValue: number,
  totalSellValue: number,
  insiderTypes: { [key: string]: { buys: number; sells: number; net_value: number } }
): string[] {
  const insights: string[] = [];
  
  // Net buying/selling insight
  const netValue = totalBuyValue - totalSellValue;
  if (netValue > 100000) {
    insights.push(`Net insider buying of $${(netValue / 1000000).toFixed(1)}M indicates positive sentiment`);
  } else if (netValue < -100000) {
    insights.push(`Net insider selling of $${(Math.abs(netValue) / 1000000).toFixed(1)}M may indicate profit-taking or lack of confidence`);
  }
  
  // Insider type analysis
  const ceoActivity = insiderTypes['ceo'] || insiderTypes['chief executive officer'];
  if (ceoActivity && ceoActivity.net_value > 50000) {
    insights.push('CEO showing confidence with net buying activity');
  } else if (ceoActivity && ceoActivity.net_value < -50000) {
    insights.push('CEO has been net selling shares');
  }
  
  // Director activity
  const directorTypes = Object.keys(insiderTypes).filter(type => 
    type.includes('director') || type.includes('board')
  );
  const directorNetValue = directorTypes.reduce((sum, type) => 
    sum + (insiderTypes[type]?.net_value || 0), 0
  );
  
  if (directorNetValue > 100000) {
    insights.push('Board members showing confidence with net buying');
  }
  
  // Transaction frequency
  if (buyTransactions.length > sellTransactions.length * 2) {
    insights.push('Significantly more buy transactions than sell transactions');
  } else if (sellTransactions.length > buyTransactions.length * 2) {
    insights.push('Significantly more sell transactions than buy transactions');
  }
  
  if (insights.length === 0) {
    insights.push('Mixed insider activity with no clear directional bias');
  }
  
  return insights;
}

function getSignificantTransactions(transactions: InsiderTransaction[], limit: number): InsiderTransaction[] {
  // Sort by transaction value (absolute) and return top transactions
  return transactions
    .sort((a, b) => Math.abs(parseTransactionValue(b.value)) - Math.abs(parseTransactionValue(a.value)))
    .slice(0, limit);
}
