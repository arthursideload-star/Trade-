import { z } from 'zod';
import { FinvizAdapter } from '../adapters/finviz.js';
import { FundamentalMetrics } from '../types/index.js';

const FundamentalMetricsSchema = z.object({
  ticker: z.string(),
  metrics: z.array(z.string()).optional(),
});

const ValuationAnalysisSchema = z.object({
  tickers: z.array(z.string()),
  metrics: z.array(z.string()).default(['pe', 'forwardPE', 'peg', 'priceToBook']),
});

const FinancialHealthSchema = z.object({
  ticker: z.string(),
  weights: z.object({
    profitability: z.number().default(0.3),
    liquidity: z.number().default(0.2),
    leverage: z.number().default(0.2),
    efficiency: z.number().default(0.15),
    growth: z.number().default(0.15),
  }).default({}),
});

export async function getFundamentalMetrics(args: unknown) {
  try {
    const { ticker, metrics } = FundamentalMetricsSchema.parse(args);
    
    const finviz = new FinvizAdapter();
    const fundamentals = await finviz.getFundamentals(ticker);
    
    // Filter metrics if specified
    let filteredMetrics = fundamentals;
    if (metrics && metrics.length > 0) {
      filteredMetrics = { ticker: fundamentals.ticker };
      metrics.forEach(metric => {
        const key = metric as keyof FundamentalMetrics;
        if (key in fundamentals) {
          (filteredMetrics as any)[key] = fundamentals[key];
        }
      });
    }
    
    return {
      content: [
        {
          type: "text" as const,
          text: JSON.stringify({
            ticker: ticker.toUpperCase(),
            fundamentals: filteredMetrics,
            requested_metrics: metrics || 'all',
            summary: `Retrieved fundamental metrics for ${ticker.toUpperCase()}`,
          }, null, 2),
        },
      ],
    };
  } catch (error) {
    return {
      content: [
        {
          type: "text" as const,
          text: `Error getting fundamentals for ${args && typeof args === 'object' && 'ticker' in args ? (args as any).ticker : 'unknown ticker'}: ${error instanceof Error ? error.message : 'Unknown error'}`,
        },
      ],
      isError: true,
    };
  }
}

export async function analyzeValuationMetrics(args: unknown) {
  try {
    const { tickers, metrics } = ValuationAnalysisSchema.parse(args);
    
    const finviz = new FinvizAdapter();
    const valuations: { [ticker: string]: any } = {};
    const errors: string[] = [];
    
    // Get fundamentals for each ticker
    for (const ticker of tickers) {
      try {
        const fundamentals = await finviz.getFundamentals(ticker);
        valuations[ticker] = fundamentals;
      } catch (error) {
        errors.push(`${ticker}: ${error instanceof Error ? error.message : 'Unknown error'}`);
      }
    }
    
    // Calculate comparative analysis
    const analysis = calculateValuationComparison(valuations, metrics);
    
    return {
      content: [
        {
          type: "text" as const,
          text: JSON.stringify({
            tickers,
            metrics,
            valuations,
            comparative_analysis: analysis,
            errors: errors.length > 0 ? errors : undefined,
            summary: `Analyzed valuation metrics for ${Object.keys(valuations).length} out of ${tickers.length} requested tickers`,
          }, null, 2),
        },
      ],
    };
  } catch (error) {
    return {
      content: [
        {
          type: "text" as const,
          text: `Error in valuation analysis: ${error instanceof Error ? error.message : 'Unknown error'}`,
        },
      ],
      isError: true,
    };
  }
}

export async function calculateFinancialHealthScore(args: unknown) {
  try {
    const { ticker, weights } = FinancialHealthSchema.parse(args);
    
    const finviz = new FinvizAdapter();
    const fundamentals = await finviz.getFundamentals(ticker);
    
    const healthScore = calculateHealthScore(fundamentals, weights);
    
    return {
      content: [
        {
          type: "text" as const,
          text: JSON.stringify({
            ticker: ticker.toUpperCase(),
            health_score: healthScore,
            weights,
            fundamentals,
            summary: `Financial health score: ${healthScore.overall_score}/100 (${healthScore.rating})`,
          }, null, 2),
        },
      ],
    };
  } catch (error) {
    return {
      content: [
        {
          type: "text" as const,
          text: `Error calculating health score for ${args && typeof args === 'object' && 'ticker' in args ? (args as any).ticker : 'unknown ticker'}: ${error instanceof Error ? error.message : 'Unknown error'}`,
        },
      ],
      isError: true,
    };
  }
}

function calculateValuationComparison(valuations: { [ticker: string]: FundamentalMetrics }, metrics: string[]) {
  const tickers = Object.keys(valuations);
  if (tickers.length === 0) return {};
  
  const analysis: any = {
    metrics_comparison: {},
    rankings: {},
    outliers: {},
    average_values: {},
  };
  
  // Calculate averages and comparisons for each metric
  metrics.forEach(metric => {
    const values: { [ticker: string]: number } = {};
    const numericValues: number[] = [];
    
    tickers.forEach(ticker => {
      const value = (valuations[ticker] as any)[metric];
      if (value && value !== '-' && !isNaN(parseFloat(value))) {
        const numValue = parseFloat(value);
        values[ticker] = numValue;
        numericValues.push(numValue);
      }
    });
    
    if (numericValues.length > 0) {
      const avg = numericValues.reduce((a, b) => a + b, 0) / numericValues.length;
      const sorted = Object.entries(values).sort(([,a], [,b]) => a - b);
      
      analysis.metrics_comparison[metric] = values;
      analysis.rankings[metric] = sorted.map(([ticker]) => ticker);
      analysis.average_values[metric] = avg;
      
      // Identify outliers (values > 2 standard deviations from mean)
      const stdDev = Math.sqrt(numericValues.reduce((sq, n) => sq + Math.pow(n - avg, 2), 0) / numericValues.length);
      const outlierThreshold = stdDev * 2;
      
      analysis.outliers[metric] = Object.entries(values)
        .filter(([, value]) => Math.abs(value - avg) > outlierThreshold)
        .map(([ticker, value]) => ({ ticker, value, deviation: Math.abs(value - avg) }));
    }
  });
  
  return analysis;
}

/**
 * Utility functions for health score calculations
 */
class HealthScoreCalculator {
  private fundamentals: FundamentalMetrics;
  private weights: any;

  constructor(fundamentals: FundamentalMetrics, weights: any) {
    this.fundamentals = fundamentals;
    this.weights = weights;
  }

  /**
   * Calculate profitability score based on profit margin and ROE
   */
  calculateProfitabilityScore(): { score: number; details: any } {
    let score = 50; // neutral start
    const details: any = {};

    if (this.fundamentals.profitMargin) {
      const margin = parseFloat(this.fundamentals.profitMargin.replace('%', ''));
      if (!isNaN(margin)) {
        score = Math.min(100, Math.max(0, 50 + margin * 2));
        details.profit_margin = `${margin}%`;
      }
    }
    
    if (this.fundamentals.returnOnEquity) {
      const roe = parseFloat(this.fundamentals.returnOnEquity.replace('%', ''));
      if (!isNaN(roe)) {
        const roeScore = Math.min(100, Math.max(0, 50 + roe * 3));
        score = (score + roeScore) / 2;
        details.return_on_equity = `${roe}%`;
      }
    }

    return { score, details };
  }

  /**
   * Calculate liquidity score based on current ratio
   */
  calculateLiquidityScore(): { score: number; details: any } {
    let score = 50;
    const details: any = {};

    if (this.fundamentals.currentRatio) {
      const ratio = parseFloat(this.fundamentals.currentRatio);
      if (!isNaN(ratio)) {
        if (ratio >= 1.5 && ratio <= 3) {
          score = 90;
        } else if (ratio >= 1 && ratio < 1.5) {
          score = 70;
        } else if (ratio > 3) {
          score = 60;
        } else {
          score = 20;
        }
        details.current_ratio = ratio;
      }
    }

    return { score, details };
  }

  /**
   * Calculate leverage score based on debt-to-equity ratio
   */
  calculateLeverageScore(): { score: number; details: any } {
    let score = 50;
    const details: any = {};

    if (this.fundamentals.debtToEquity) {
      const debtToEquity = parseFloat(this.fundamentals.debtToEquity);
      if (!isNaN(debtToEquity)) {
        if (debtToEquity <= 0.3) {
          score = 90;
        } else if (debtToEquity <= 0.6) {
          score = 70;
        } else if (debtToEquity <= 1.0) {
          score = 50;
        } else {
          score = Math.max(10, 50 - (debtToEquity - 1) * 20);
        }
        details.debt_to_equity = debtToEquity;
      }
    }

    return { score, details };
  }

  /**
   * Calculate efficiency score based on P/E ratio
   */
  calculateEfficiencyScore(): { score: number; details: any } {
    let score = 50;
    const details: any = {};

    if (this.fundamentals.pe) {
      const pe = parseFloat(this.fundamentals.pe);
      if (!isNaN(pe) && pe > 0) {
        if (pe >= 10 && pe <= 20) {
          score = 80;
        } else if (pe >= 5 && pe < 10) {
          score = 70;
        } else if (pe > 20 && pe <= 30) {
          score = 60;
        } else if (pe > 30) {
          score = Math.max(20, 60 - (pe - 30));
        } else {
          score = 30;
        }
        details.price_to_earnings = pe;
      }
    }

    return { score, details };
  }

  /**
   * Calculate growth score based on EPS growth
   */
  calculateGrowthScore(): { score: number; details: any } {
    let score = 50;
    const details: any = {};

    if (this.fundamentals.epsGrowth) {
      const epsGrowth = parseFloat(this.fundamentals.epsGrowth.replace('%', ''));
      if (!isNaN(epsGrowth)) {
        score = Math.min(100, Math.max(0, 50 + epsGrowth));
        details.eps_growth = `${epsGrowth}%`;
      }
    }

    return { score, details };
  }

  /**
   * Calculate overall health score
   */
  calculateOverallScore() {
    const profitability = this.calculateProfitabilityScore();
    const liquidity = this.calculateLiquidityScore();
    const leverage = this.calculateLeverageScore();
    const efficiency = this.calculateEfficiencyScore();
    const growth = this.calculateGrowthScore();

    const scores = {
      profitability: profitability.score,
      liquidity: liquidity.score,
      leverage: leverage.score,
      efficiency: efficiency.score,
      growth: growth.score,
    };

    const details = {
      ...profitability.details,
      ...liquidity.details,
      ...leverage.details,
      ...efficiency.details,
      ...growth.details,
    };

    const overallScore = Math.round(
      scores.profitability * this.weights.profitability +
      scores.liquidity * this.weights.liquidity +
      scores.leverage * this.weights.leverage +
      scores.efficiency * this.weights.efficiency +
      scores.growth * this.weights.growth
    );

    return { overallScore, scores, details };
  }
}

function calculateHealthScore(fundamentals: FundamentalMetrics, weights: any) {
  const calculator = new HealthScoreCalculator(fundamentals, weights);
  const { overallScore, scores, details } = calculator.calculateOverallScore();

  // Determine rating
  let rating = 'Poor';
  if (overallScore >= 80) rating = 'Excellent';
  else if (overallScore >= 70) rating = 'Good';
  else if (overallScore >= 60) rating = 'Fair';
  else if (overallScore >= 40) rating = 'Below Average';

  return {
    overall_score: overallScore,
    rating,
    component_scores: scores,
    details,
    interpretation: {
      profitability: getProfitabilityInterpretation(scores.profitability),
      liquidity: getLiquidityInterpretation(scores.liquidity),
      leverage: getLeverageInterpretation(scores.leverage),
      efficiency: getEfficiencyInterpretation(scores.efficiency),
      growth: getGrowthInterpretation(scores.growth),
    },
  };
}

function getProfitabilityInterpretation(score: number): string {
  if (score >= 80) return 'Strong profitability metrics';
  if (score >= 60) return 'Adequate profitability';
  if (score >= 40) return 'Below average profitability';
  return 'Poor profitability performance';
}

function getLiquidityInterpretation(score: number): string {
  if (score >= 80) return 'Strong liquidity position';
  if (score >= 60) return 'Adequate liquidity';
  if (score >= 40) return 'Liquidity concerns';
  return 'Poor liquidity position';
}

function getLeverageInterpretation(score: number): string {
  if (score >= 80) return 'Conservative debt levels';
  if (score >= 60) return 'Manageable debt levels';
  if (score >= 40) return 'Elevated debt levels';
  return 'High debt burden';
}

function getEfficiencyInterpretation(score: number): string {
  if (score >= 80) return 'Attractive valuation';
  if (score >= 60) return 'Fair valuation';
  if (score >= 40) return 'Expensive valuation';
  return 'Very expensive or concerning valuation';
}

function getGrowthInterpretation(score: number): string {
  if (score >= 80) return 'Strong growth prospects';
  if (score >= 60) return 'Moderate growth expected';
  if (score >= 40) return 'Limited growth prospects';
  return 'Declining or negative growth';
}
