import OpenAI from 'openai';
import { NewsAnalysis, NewsArticle } from '../types/index.js';
import { config, isOpenAIConfigured } from '../config.js';

export class OpenAIAdapter {
  private client: OpenAI | null = null;

  constructor() {
    if (isOpenAIConfigured()) {
      this.client = new OpenAI({
        apiKey: config.openaiApiKey,
      });
    } else {
      console.warn('OpenAI API key is not configured. News analysis features will not work.');
    }
  }

  async getLatestNews(
    ticker: string, 
    daysBack = 7, 
    maxArticles = 10,
    includeSentiment = true
  ): Promise<NewsAnalysis> {
    if (!this.client) {
      throw new Error('OpenAI API key is not configured');
    }

    try {
      const prompt = this.buildNewsPrompt(ticker, daysBack, maxArticles, includeSentiment);
      
      const response = await this.client.chat.completions.create({
        model: 'gpt-4o-mini',
        messages: [
          {
            role: 'system',
            content: 'You are a financial news analyst. Provide accurate, well-sourced news summaries with complete URLs. Focus on market-moving events and their potential impact on stock prices.',
          },
          {
            role: 'user',
            content: prompt,
          },
        ],
        max_tokens: 2000,
        temperature: 0.3,
      });

      const content = response.choices[0]?.message?.content || '';
      return this.parseNewsResponse(content, ticker);
    } catch (error) {
      console.error(`Error getting news for ${ticker}:`, error);
      throw new Error(`Failed to get news analysis: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  async analyzeNewsImpact(ticker: string, newsItems: string[]): Promise<{
    overallImpact: 'positive' | 'negative' | 'neutral';
    impactScore: number;
    keyInsights: string[];
    riskFactors: string[];
  }> {
    if (!this.client) {
      throw new Error('OpenAI API key is not configured');
    }

    try {
      const prompt = `
        Analyze the following news items for ${ticker} and provide:
        1. Overall market impact (positive/negative/neutral)
        2. Impact score (1-10, where 10 is highest impact)
        3. Key insights for investors
        4. Risk factors to consider
        
        News items:
        ${newsItems.map((item, index) => `${index + 1}. ${item}`).join('\n')}
        
        Provide response in JSON format with keys: overallImpact, impactScore, keyInsights, riskFactors
      `;

      const response = await this.client.chat.completions.create({
        model: 'gpt-4o-mini',
        messages: [
          {
            role: 'system',
            content: 'You are a financial analyst specializing in news impact assessment. Provide structured analysis in JSON format.',
          },
          {
            role: 'user',
            content: prompt,
          },
        ],
        max_tokens: 1000,
        temperature: 0.2,
      });

      const content = response.choices[0]?.message?.content || '';
      return this.parseImpactAnalysis(content);
    } catch (error) {
      console.error(`Error analyzing news impact for ${ticker}:`, error);
      throw new Error(`Failed to analyze news impact: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  async getMarketContext(ticker: string, sector?: string): Promise<{
    sectorTrends: string[];
    marketSentiment: string;
    competitorAnalysis: string[];
    macroFactors: string[];
  }> {
    if (!this.client) {
      throw new Error('OpenAI API key is not configured');
    }

    try {
      const prompt = `
        Provide market context analysis for ${ticker}${sector ? ` in the ${sector} sector` : ''}:
        
        Include:
        1. Current sector trends affecting the stock
        2. Overall market sentiment
        3. Key competitor movements
        4. Relevant macroeconomic factors
        
        Provide response in JSON format with keys: sectorTrends, marketSentiment, competitorAnalysis, macroFactors
      `;

      const response = await this.client.chat.completions.create({
        model: 'gpt-4o-mini',
        messages: [
          {
            role: 'system',
            content: 'You are a market analyst providing contextual analysis for stock research. Focus on current market conditions and sector dynamics.',
          },
          {
            role: 'user',
            content: prompt,
          },
        ],
        max_tokens: 1200,
        temperature: 0.3,
      });

      const content = response.choices[0]?.message?.content || '';
      return this.parseMarketContext(content);
    } catch (error) {
      console.error(`Error getting market context for ${ticker}:`, error);
      throw new Error(`Failed to get market context: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  async analyzeSocialSentiment(posts: any[]): Promise<{
    overallSentiment: 'bullish' | 'bearish' | 'neutral';
    sentimentScore: number;
    keyThemes: string[];
    confidenceLevel: 'high' | 'medium' | 'low';
  }> {
    if (!this.client) {
      throw new Error('OpenAI API key is not configured');
    }

    try {
      const postsText = posts.slice(0, 20).map(post => 
        `Title: ${post.title}\nContent: ${post.selftext || post.body || 'No content'}\nScore: ${post.score}`
      ).join('\n\n');

      const prompt = `
        Analyze the sentiment of these social media posts about a stock:
        
        ${postsText}
        
        Provide:
        1. Overall sentiment (bullish/bearish/neutral)
        2. Sentiment score (-10 to +10, where -10 is very bearish, +10 is very bullish)
        3. Key themes mentioned
        4. Confidence level in the analysis
        
        Respond in JSON format with keys: overallSentiment, sentimentScore, keyThemes, confidenceLevel
      `;

      const response = await this.client.chat.completions.create({
        model: 'gpt-4o-mini',
        messages: [
          {
            role: 'system',
            content: 'You are a social media sentiment analyst for financial markets. Analyze retail investor sentiment accurately.',
          },
          {
            role: 'user',
            content: prompt,
          },
        ],
        max_tokens: 800,
        temperature: 0.2,
      });

      const content = response.choices[0]?.message?.content || '';
      return this.parseSentimentAnalysis(content);
    } catch (error) {
      console.error('Error analyzing social sentiment:', error);
      throw new Error(`Failed to analyze social sentiment: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  private buildNewsPrompt(ticker: string, daysBack: number, maxArticles: number, includeSentiment: boolean): string {
    return `
      Find and summarize the ${maxArticles} most recent and impactful news articles about ${ticker} from the last ${daysBack} days.
      
      For each article, provide:
      1. Headline/Title
      2. Brief summary (2-3 sentences)
      3. Source name
      4. Complete source URL
      5. Publication date
      ${includeSentiment ? '6. Sentiment impact (positive/negative/neutral)' : ''}
      
      Focus on:
      - Earnings reports and financial results
      - Product launches or business developments
      - Regulatory changes or legal issues
      - Market analyst upgrades/downgrades
      - Management changes
      - Partnership or acquisition news
      
      Format as JSON with an array of articles, each containing: headline, summary, source, url, publishedAt${includeSentiment ? ', sentiment' : ''}.
    `;
  }

  private parseNewsResponse(content: string, ticker: string): NewsAnalysis {
    try {
      // Try to extract JSON from the response
      const jsonMatch = content.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        const parsed = JSON.parse(jsonMatch[0]);
        if (parsed.articles && Array.isArray(parsed.articles)) {
          const articles: NewsArticle[] = parsed.articles.map((article: any) => ({
            headline: article.headline || article.title || 'No headline',
            summary: article.summary || article.description || 'No summary available',
            source: article.source || 'Unknown source',
            url: article.url || '#',
            publishedAt: article.publishedAt || article.date || new Date().toISOString(),
            sentiment: article.sentiment as 'positive' | 'negative' | 'neutral' || 'neutral',
          }));

          return {
            ticker: ticker.toUpperCase(),
            articles,
            overallSentiment: this.calculateOverallSentiment(articles),
            keyThemes: this.extractKeyThemes(articles),
            marketImpact: this.assessMarketImpact(articles),
          };
        }
      }
    } catch (error) {
      console.warn('Failed to parse JSON response, using fallback parsing');
    }

    // Fallback parsing for non-JSON responses
    return this.parseNewsResponseFallback(content, ticker);
  }

  private parseNewsResponseFallback(content: string, ticker: string): NewsAnalysis {
    // Simple fallback parsing - create a single article from the content
    const articles: NewsArticle[] = [{
      headline: `Recent news summary for ${ticker}`,
      summary: content.substring(0, 500) + (content.length > 500 ? '...' : ''),
      source: 'AI Analysis',
      url: '#',
      publishedAt: new Date().toISOString(),
      sentiment: 'neutral',
    }];

    return {
      ticker: ticker.toUpperCase(),
      articles,
      overallSentiment: 'neutral',
      keyThemes: ['General market news'],
      marketImpact: 'medium',
    };
  }

  private parseImpactAnalysis(content: string): any {
    return this.parseJSONResponse(content, {
      overallImpact: 'neutral',
      impactScore: 5,
      keyInsights: ['Analysis unavailable'],
      riskFactors: ['Standard market risks'],
    });
  }

  private parseMarketContext(content: string): any {
    return this.parseJSONResponse(content, {
      sectorTrends: ['General market trends'],
      marketSentiment: 'Mixed market conditions',
      competitorAnalysis: ['Competitive landscape analysis unavailable'],
      macroFactors: ['Standard macroeconomic factors'],
    });
  }

  private parseSentimentAnalysis(content: string): any {
    return this.parseJSONResponse(content, {
      overallSentiment: 'neutral',
      sentimentScore: 0,
      keyThemes: ['General discussion'],
      confidenceLevel: 'low',
    });
  }

  /**
   * Generic JSON parsing utility with fallback handling
   * @param content - Raw content from AI response
   * @param fallback - Default values to return if parsing fails
   * @returns Parsed JSON object or fallback values
   */
  private parseJSONResponse<T>(content: string, fallback: T): T {
    try {
      const jsonMatch = content.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        return JSON.parse(jsonMatch[0]);
      }
    } catch (error) {
      console.warn('Failed to parse JSON response');
    }
    return fallback;
  }

  private calculateOverallSentiment(articles: NewsArticle[]): 'positive' | 'negative' | 'neutral' {
    const sentiments = articles.map(a => a.sentiment).filter(s => s);
    const positive = sentiments.filter(s => s === 'positive').length;
    const negative = sentiments.filter(s => s === 'negative').length;
    
    if (positive > negative) return 'positive';
    if (negative > positive) return 'negative';
    return 'neutral';
  }

  private extractKeyThemes(articles: NewsArticle[]): string[] {
    // Simple keyword extraction from headlines and summaries
    const text = articles.map(a => `${a.headline} ${a.summary}`).join(' ').toLowerCase();
    const themes: string[] = [];
    
    const keywords = ['earnings', 'revenue', 'profit', 'loss', 'acquisition', 'merger', 'partnership', 
                     'product', 'launch', 'regulation', 'lawsuit', 'upgrade', 'downgrade'];
    
    keywords.forEach(keyword => {
      if (text.includes(keyword)) {
        themes.push(keyword.charAt(0).toUpperCase() + keyword.slice(1));
      }
    });
    
    return themes.length > 0 ? themes : ['General business news'];
  }

  private assessMarketImpact(articles: NewsArticle[]): 'high' | 'medium' | 'low' {
    const highImpactKeywords = ['earnings', 'acquisition', 'merger', 'lawsuit', 'regulation', 'bankruptcy'];
    const text = articles.map(a => `${a.headline} ${a.summary}`).join(' ').toLowerCase();
    
    const hasHighImpact = highImpactKeywords.some(keyword => text.includes(keyword));
    const articleCount = articles.length;
    
    if (hasHighImpact || articleCount >= 5) return 'high';
    if (articleCount >= 2) return 'medium';
    return 'low';
  }
}
