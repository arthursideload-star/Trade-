import axios from 'axios';
import * as cheerio from 'cheerio';
import { PutCallRatioAnalysis, PutCallRatioData } from '../types/index.js';

export class BarchartAdapter {
  private baseUrl = 'https://www.barchart.com';

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

  async getPutCallRatio(ticker: string): Promise<PutCallRatioAnalysis> {
    try {
      const url = `${this.baseUrl}/stocks/quotes/${ticker.toUpperCase()}/put-call-ratios?orderBy=expirationDate&orderDir=desc`;
      const response = await axios.get(url, {
        headers: this.getHeaders(),
        timeout: 15000,
      });

      return this.parsePutCallRatioData(response.data, ticker);
    } catch (error) {
      throw new Error(`Failed to get put/call ratio for ${ticker}: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  private parsePutCallRatioData(html: string, ticker: string): PutCallRatioAnalysis {
    const $ = cheerio.load(html);
    
    const currentPrice = $('.last-price, .price, [data-ng-bind*="price"]').first().text().trim() || undefined;
    const totals = this.extractTotals($);
    const ratiosByDate = this.extractTableData($);
    
    // Use extracted totals or calculate from detailed data
    const finalTotals = this.consolidateTotals(totals, ratiosByDate);
    const analysis = this.analyzePutCallSentiment(finalTotals.volumeRatio, finalTotals.oiRatio, ratiosByDate);

    return {
      ticker: ticker.toUpperCase(),
      currentPrice,
      overallPutCallVolumeRatio: finalTotals.volumeRatio,
      overallPutCallOIRatio: finalTotals.oiRatio,
      totalPutVolume: finalTotals.putVolume,
      totalCallVolume: finalTotals.callVolume,
      totalPutOI: finalTotals.putOI,
      totalCallOI: finalTotals.callOI,
      ratiosByDate,
      analysis,
      validationResult: this.validateData(finalTotals),
    };
  }

  private extractTotals($: cheerio.CheerioAPI) {
    const totals = { putVolume: 0, callVolume: 0, putOI: 0, callOI: 0, volumeRatio: 0, oiRatio: 0 };
    
    // Try structured data first
    $('.bc-futures-options-quotes-totals .bc-futures-options-quotes-totals__data-row').each((_, row) => {
      const $row = $(row);
      const text = $row.text().trim();
      const value = this.parseNumber($row.find('strong').text().trim());
      
      if (text.includes('Put Volume Total')) totals.putVolume = value;
      else if (text.includes('Call Volume Total')) totals.callVolume = value;
      else if (text.includes('Put/Call Volume Ratio')) totals.volumeRatio = value;
      else if (text.includes('Put Open Interest Total')) totals.putOI = value;
      else if (text.includes('Call Open Interest Total')) totals.callOI = value;
      else if (text.includes('Put/Call Open Interest Ratio')) totals.oiRatio = value;
    });

    // Fallback to regex parsing if structured data not found
    if (totals.putVolume === 0 && totals.callVolume === 0) {
      const pageText = $.text();
      const patterns = {
        putVolume: /Put Volume Total[:\s]+([0-9,]+)/i,
        callVolume: /Call Volume Total[:\s]+([0-9,]+)/i,
        volumeRatio: /Put\/Call Volume Ratio[:\s]+([0-9.]+)/i,
        putOI: /Put Open Interest Total[:\s]+([0-9,]+)/i,
        callOI: /Call Open Interest Total[:\s]+([0-9,]+)/i,
        oiRatio: /Put\/Call Open Interest Ratio[:\s]+([0-9.]+)/i,
      };

      Object.entries(patterns).forEach(([key, pattern]) => {
        const match = pageText.match(pattern);
        if (match) totals[key as keyof typeof totals] = this.parseNumber(match[1]);
      });
    }

    return totals;
  }

  private extractTableData($: cheerio.CheerioAPI): PutCallRatioData[] {
    const ratiosByDate: PutCallRatioData[] = [];
    
    // Find the most relevant table
    let tableRows = $('table').filter((i, table) => {
      const tableText = $(table).text().toLowerCase();
      return tableText.includes('put/call') || tableText.includes('expiration') || tableText.includes('ratio');
    }).first().find('tbody tr');

    if (tableRows.length === 0) {
      tableRows = $('table tbody tr');
    }

    tableRows.each((_, row) => {
      const cells = $(row).find('td, th').map((i, cell) => $(cell).text().trim()).get();
      
      if (cells.length >= 6) {
        const [dateCell, putVolCell, callVolCell, volRatioCell, putOICell, callOICell, oiRatioCell] = cells;
        
        // Check if first cell looks like a date
        if (/\d{1,2}\/\d{1,2}\/\d{4}|\d{4}-\d{2}-\d{2}|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec/i.test(dateCell)) {
          const putVolume = this.parseNumber(putVolCell);
          const callVolume = this.parseNumber(callVolCell);
          const putOI = this.parseNumber(putOICell);
          const callOI = this.parseNumber(callOICell);
          
          if (putVolume > 0 || callVolume > 0) {
            ratiosByDate.push({
              expirationDate: dateCell,
              putVolume,
              callVolume,
              putCallVolumeRatio: this.parseNumber(volRatioCell) || (callVolume > 0 ? putVolume / callVolume : 0),
              putOpenInterest: putOI,
              callOpenInterest: callOI,
              putCallOIRatio: this.parseNumber(oiRatioCell || '') || (callOI > 0 ? putOI / callOI : 0),
              totalVolume: putVolume + callVolume,
              totalOpenInterest: putOI + callOI,
            });
          }
        }
      }
    });

    return ratiosByDate;
  }

  private consolidateTotals(extracted: any, ratiosByDate: PutCallRatioData[]) {
    const summed = ratiosByDate.reduce((acc, data) => ({
      putVolume: acc.putVolume + data.putVolume,
      callVolume: acc.callVolume + data.callVolume,
      putOI: acc.putOI + data.putOpenInterest,
      callOI: acc.callOI + data.callOpenInterest,
    }), { putVolume: 0, callVolume: 0, putOI: 0, callOI: 0 });

    const totals = {
      putVolume: extracted.putVolume || summed.putVolume,
      callVolume: extracted.callVolume || summed.callVolume,
      putOI: extracted.putOI || summed.putOI,
      callOI: extracted.callOI || summed.callOI,
      volumeRatio: 0,
      oiRatio: 0,
    };

    totals.volumeRatio = extracted.volumeRatio || (totals.callVolume > 0 ? totals.putVolume / totals.callVolume : 0);
    totals.oiRatio = extracted.oiRatio || (totals.callOI > 0 ? totals.putOI / totals.callOI : 0);

    // Create summary entry if no detailed data but have totals
    if (ratiosByDate.length === 0 && (totals.putVolume > 0 || totals.callVolume > 0)) {
      ratiosByDate.push({
        expirationDate: 'Overall',
        putVolume: totals.putVolume,
        callVolume: totals.callVolume,
        putCallVolumeRatio: totals.volumeRatio,
        putOpenInterest: totals.putOI,
        callOpenInterest: totals.callOI,
        putCallOIRatio: totals.oiRatio,
        totalVolume: totals.putVolume + totals.callVolume,
        totalOpenInterest: totals.putOI + totals.callOI,
      });
    }

    return totals;
  }

  private analyzePutCallSentiment(volumeRatio: number, oiRatio: number, ratiosByDate: PutCallRatioData[]) {
    let sentiment: 'bullish' | 'bearish' | 'neutral' = 'neutral';
    const keyInsights: string[] = [];
    let interpretation = '';

    // Analyze volume ratio
    if (volumeRatio > 1.2) {
      sentiment = 'bearish';
      interpretation = 'High put/call volume ratio suggests bearish sentiment';
      keyInsights.push(`High put/call volume ratio of ${volumeRatio.toFixed(2)} indicates heavy put buying`);
    } else if (volumeRatio < 0.8) {
      sentiment = 'bullish';
      interpretation = 'Low put/call volume ratio suggests bullish sentiment';
      keyInsights.push(`Low put/call volume ratio of ${volumeRatio.toFixed(2)} indicates heavy call buying`);
    } else {
      interpretation = 'Put/call volume ratio is within normal range';
      keyInsights.push(`Put/call volume ratio of ${volumeRatio.toFixed(2)} suggests neutral sentiment`);
    }

    // Analyze OI ratio
    if (oiRatio > 1.5) {
      keyInsights.push(`High put/call OI ratio of ${oiRatio.toFixed(2)} suggests hedging activity`);
    } else if (oiRatio > 0 && oiRatio < 0.5) {
      keyInsights.push(`Low put/call OI ratio of ${oiRatio.toFixed(2)} suggests bullish positioning`);
    }

    // Analyze trends across expiration dates
    if (ratiosByDate.length >= 3) {
      const recentRatios = ratiosByDate.slice(0, 3).map(d => d.putCallVolumeRatio);
      const isIncreasing = recentRatios.every((ratio, i) => i === 0 || ratio >= recentRatios[i - 1]);
      const isDecreasing = recentRatios.every((ratio, i) => i === 0 || ratio <= recentRatios[i - 1]);

      if (isIncreasing) keyInsights.push('Put/call ratios are increasing across recent expiration dates');
      else if (isDecreasing) keyInsights.push('Put/call ratios are decreasing across recent expiration dates');
    }

    return { sentiment, interpretation, keyInsights };
  }

  private parseNumber(value: string): number {
    if (!value || typeof value !== 'string') return 0;
    const cleaned = value.replace(/[^0-9.-]/g, '');
    const parsed = parseFloat(cleaned);
    return isNaN(parsed) ? 0 : parsed;
  }

  private validateData(totals: any): { isValid: boolean; warnings: string[] } {
    const warnings: string[] = [];
    const hasData = totals.putVolume > 0 || totals.callVolume > 0 || totals.putOI > 0 || totals.callOI > 0;
    
    if (!hasData) {
      return { isValid: false, warnings: ['No put/call data found'] };
    }

    // Check for extreme values
    if (totals.volumeRatio > 10) warnings.push(`Unusually high put/call volume ratio: ${totals.volumeRatio.toFixed(2)}`);
    if (totals.oiRatio > 5) warnings.push(`Unusually high put/call OI ratio: ${totals.oiRatio.toFixed(2)}`);

    return { isValid: true, warnings };
  }
} 