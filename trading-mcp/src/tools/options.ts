import { z } from 'zod';
import { BarchartAdapter } from '../adapters/barchart.js';

const PutCallRatioSchema = z.object({
  ticker: z.string(),
});

export async function getPutCallRatio(args: unknown) {
  try {
    const { ticker } = PutCallRatioSchema.parse(args);
    
    const barchart = new BarchartAdapter();
    const ratioData = await barchart.getPutCallRatio(ticker);
    
    if (!ratioData.validationResult.isValid) {
      return {
        content: [
          {
            type: "text" as const,
            text: JSON.stringify({
              ticker: ticker.toUpperCase(),
              error: 'Failed to extract valid put/call ratio data',
              details: ratioData.validationResult.warnings,
              put_call_analysis: ratioData,
              summary: `Data extraction failed for ${ticker.toUpperCase()}. ${ratioData.validationResult.warnings.join('; ')}`,
            }, null, 2),
          },
        ],
        isError: true,
      };
    }
    
    const warnings = ratioData.validationResult.warnings.length > 0 
      ? ` (Warnings: ${ratioData.validationResult.warnings.join('; ')})`
      : '';
    
    return {
      content: [
        {
          type: "text" as const,
          text: JSON.stringify({
            ticker: ticker.toUpperCase(),
            put_call_analysis: ratioData,
            summary: `Retrieved put/call ratio data for ${ticker.toUpperCase()}. Overall volume ratio: ${ratioData.overallPutCallVolumeRatio.toFixed(2)} (${ratioData.analysis.sentiment} sentiment)${warnings}`,
            interpretation: ratioData.analysis.interpretation,
            key_insights: ratioData.analysis.keyInsights,
            data_quality: {
              is_valid: ratioData.validationResult.isValid,
              warnings: ratioData.validationResult.warnings,
            },
          }, null, 2),
        },
      ],
    };
  } catch (error) {
    return {
      content: [
        {
          type: "text" as const,
          text: `Error getting put/call ratio for ${args && typeof args === 'object' && 'ticker' in args ? (args as any).ticker : 'unknown ticker'}: ${error instanceof Error ? error.message : 'Unknown error'}`,
        },
      ],
      isError: true,
    };
  }
} 