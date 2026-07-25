import axios from 'axios';
import * as cheerio from 'cheerio';
import { ScreeningResult, FundamentalMetrics, InsiderTransaction, InsiderActivity } from '../types/index.js';

export class FinvizAdapter {
  private baseUrl = 'https://finviz.com';
  private screenerUrl = `${this.baseUrl}/screener.ashx`;
  private quoteUrl = `${this.baseUrl}/quote.ashx`;

  private getHeaders() {
    return {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
      'Accept-Language': 'en-US,en;q=0.5',
      'Accept-Encoding': 'gzip, deflate',
      'Connection': 'keep-alive',
      'Upgrade-Insecure-Requests': '1',
    };
  }

  /**
   * Screen stocks based on technical patterns and filters
   * @param pattern - Technical pattern to screen for (e.g., 'channel_down', 'triangle_ascending')
   * @param marketCap - Market cap filter ('nano', 'micro', 'small', 'mid', 'large', 'mega')
   * @param geo - Geographic filter ('usa', 'foreign')
   * @returns Promise<ScreeningResult[]> - Array of stocks matching the criteria
   */
  async screenStocks(pattern: string, marketCap: string, geo = 'usa'): Promise<ScreeningResult[]> {
    try {
      const url = this.buildScreenerUrl(pattern, marketCap, geo);
      console.debug(`Fetching screener data from: ${url}`);
      
      const response = await axios.get(url, {
        headers: this.getHeaders(),
        timeout: 10000,
      });

      return this.parseScreenerResults(response.data);
    } catch (error) {
      console.error('Error screening stocks:', error);
      throw new Error(`Failed to screen stocks: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  /**
   * Get fundamental metrics for a specific stock ticker
   * @param ticker - Stock ticker symbol (e.g., 'AAPL', 'MSFT')
   * @returns Promise<FundamentalMetrics> - Comprehensive fundamental data
   */
  async getFundamentals(ticker: string): Promise<FundamentalMetrics> {
    try {
      const url = `${this.quoteUrl}?t=${ticker.toUpperCase()}`;
      console.debug(`Fetching fundamentals for ${ticker} from: ${url}`);
      
      const response = await axios.get(url, {
        headers: this.getHeaders(),
        timeout: 10000,
      });

      return this.parseFundamentals(response.data, ticker);
    } catch (error) {
      console.error(`Error getting fundamentals for ${ticker}:`, error);
      throw new Error(`Failed to get fundamentals for ${ticker}: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  /**
   * Get insider trading activity for a specific stock
   * @param ticker - Stock ticker symbol
   * @returns Promise<InsiderActivity> - Recent insider transactions and summary
   */
  async getInsiderActivity(ticker: string): Promise<InsiderActivity> {
    try {
      const url = `${this.quoteUrl}?t=${ticker.toUpperCase()}`;
      console.debug(`Fetching insider activity for ${ticker} from: ${url}`);
      
      const response = await axios.get(url, {
        headers: this.getHeaders(),
        timeout: 10000,
      });

      const transactions = this.parseInsiderActivity(response.data);
      return {
        ticker: ticker.toUpperCase(),
        transactions,
        totalTransactions: transactions.length,
      };
    } catch (error) {
      console.error(`Error getting insider activity for ${ticker}:`, error);
      throw new Error(`Failed to get insider activity for ${ticker}: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  private buildScreenerUrl(pattern: string, marketCap: string, geo: string): string {
    const params = new URLSearchParams({
      v: '111', // Table view
      f: `cap_${marketCap},geo_${geo},ta_pattern_${pattern}`,
      ft: '4'
    });
    return `${this.screenerUrl}?${params}`;
  }

  private parseScreenerResults(html: string): ScreeningResult[] {
    const $ = cheerio.load(html);
    const results: ScreeningResult[] = [];

    // Find the screener table
    $('table.styled-table-new tr').each((index, row) => {
      if (index === 0) return; // Skip header row
      
      const cells = $(row).find('td');
      if (cells.length >= 11) {
        const result: ScreeningResult = {
          ticker: $(cells.eq(1)).text().trim(),
          company: $(cells.eq(2)).text().trim(),
          sector: $(cells.eq(3)).text().trim(),
          industry: $(cells.eq(4)).text().trim(),
          country: $(cells.eq(5)).text().trim(),
          marketCap: $(cells.eq(6)).text().trim(),
          pe: $(cells.eq(7)).text().trim(),
          price: $(cells.eq(8)).text().trim(),
          change: $(cells.eq(9)).text().trim(),
          volume: $(cells.eq(10)).text().trim(),
        };
        
        if (result.ticker && result.ticker !== '-') {
          results.push(result);
        }
      }
    });

    return results;
  }

  private parseFundamentals(html: string, ticker: string): FundamentalMetrics {
    const $ = cheerio.load(html);
    const fundamentals: FundamentalMetrics = { ticker: ticker.toUpperCase() };

    // Parse fundamental data from the snapshot table
    $('table.snapshot-table2 tr').each((_, row) => {
      const cells = $(row).find('td');
      for (let i = 0; i < cells.length; i += 2) {
        const label = $(cells.eq(i)).text().trim();
        const value = $(cells.eq(i + 1)).text().trim();
        
        switch (label) {
          case 'P/E':
            fundamentals.pe = value;
            break;
          case 'Forward P/E':
            fundamentals.forwardPE = value;
            break;
          case 'PEG':
            fundamentals.peg = value;
            break;
          case 'Current Ratio':
            fundamentals.currentRatio = value;
            break;
          case 'Insider Own':
            fundamentals.insiderOwn = value;
            break;
          case 'Short Float':
            fundamentals.shortFloat = value;
            break;
          case 'Profit Margin':
            fundamentals.profitMargin = value;
            break;
          case 'Market Cap':
            fundamentals.marketCap = value;
            break;
          case 'EPS next Y':
            fundamentals.epsGrowth = value;
            break;
          case 'Sales past 5Y':
            fundamentals.salesGrowth = value;
            break;
          case 'Debt/Eq':
            fundamentals.debtToEquity = value;
            break;
          case 'P/B':
            fundamentals.priceToBook = value;
            break;
          case 'ROE':
            fundamentals.returnOnEquity = value;
            break;
          case 'RSI (14)':
            fundamentals.rsi14 = value;
            break;
          case 'SMA200':
            fundamentals.sma200 = value;
            break;
        }
      }
    });

    return fundamentals;
  }

  private parseInsiderActivity(html: string): InsiderTransaction[] {
    const $ = cheerio.load(html);
    const transactions: InsiderTransaction[] = [];

    // Find insider trading table
    $('table.insider-table tr').each((index, row) => {
      if (index === 0) return; // Skip header row
      
      const cells = $(row).find('td');
      if (cells.length >= 7) {
        const transaction: InsiderTransaction = {
          insider: $(cells.eq(0)).text().trim(),
          relationship: $(cells.eq(1)).text().trim(),
          date: $(cells.eq(2)).text().trim(),
          transactionType: $(cells.eq(3)).text().trim(),
          cost: $(cells.eq(4)).text().trim(),
          shares: $(cells.eq(5)).text().trim(),
          value: $(cells.eq(6)).text().trim(),
          sharesTotal: $(cells.eq(7)).text().trim() || 'N/A',
        };
        
        if (transaction.insider && transaction.insider !== '-') {
          transactions.push(transaction);
        }
      }
    });

    return transactions;
  }

  /**
   * Apply advanced filters for custom stock screening
   * @param filters - Custom filter parameters as key-value pairs
   * @returns Promise<ScreeningResult[]> - Stocks matching the advanced criteria
   */
  async advancedFilter(filters: { [key: string]: string }): Promise<ScreeningResult[]> {
    try {
      const params = new URLSearchParams({
        v: '111',
        ...filters,
      });
      
      const url = `${this.screenerUrl}?${params}`;
      console.debug(`Fetching advanced filter results from: ${url}`);
      
      const response = await axios.get(url, {
        headers: this.getHeaders(),
        timeout: 10000,
      });

      return this.parseScreenerResults(response.data);
    } catch (error) {
      console.error('Error with advanced filter:', error);
      throw new Error(`Failed to apply advanced filter: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }
}
