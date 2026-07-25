import axios from 'axios';
import { RedditPost, RedditSearchResult } from '../types/index.js';
import { config, isRedditConfigured } from '../config.js';

export class RedditAdapter {
  private accessToken?: string;
  private tokenExpiry?: Date;
  private baseUrl = 'https://oauth.reddit.com';
  private authUrl = 'https://www.reddit.com/api/v1/access_token';

  constructor() {
    if (!isRedditConfigured()) {
      console.warn('Reddit API is not fully configured. Some features may not work.');
    }
  }

  async searchPosts(
    ticker: string,
    subreddits: string[] = ['stocks', 'wallstreetbets', 'investing', 'ValueInvesting'],
    timeFilter: 'hour' | 'day' | 'week' | 'month' | 'year' = 'week',
    limit = 25,
    sort: 'relevance' | 'hot' | 'top' | 'new' = 'hot'
  ): Promise<RedditSearchResult> {
    if (!isRedditConfigured()) {
      throw new Error('Reddit API credentials are not configured');
    }

    try {
      await this.ensureValidToken();
      
      const allPosts: RedditPost[] = [];
      const searchQuery = ticker.toUpperCase();

      for (const subreddit of subreddits) {
        try {
          const posts = await this.searchSubreddit(searchQuery, subreddit, timeFilter, limit, sort);
          allPosts.push(...posts);
        } catch (error) {
          console.warn(`Failed to search r/${subreddit}:`, error);
          // Continue with other subreddits even if one fails
        }
      }

      // Sort by score and remove duplicates
      const uniquePosts = this.removeDuplicates(allPosts);
      const sortedPosts = uniquePosts.sort((a, b) => b.score - a.score);

      return {
        posts: sortedPosts,
        totalFound: sortedPosts.length,
        searchQuery,
      };
    } catch (error) {
      console.error('Error searching Reddit posts:', error);
      throw new Error(`Failed to search Reddit: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  async getPostComments(postId: string, limit = 100): Promise<any[]> {
    if (!isRedditConfigured()) {
      throw new Error('Reddit API credentials are not configured');
    }

    try {
      await this.ensureValidToken();

      const response = await axios.get(`${this.baseUrl}/comments/${postId}`, {
        headers: {
          'Authorization': `Bearer ${this.accessToken}`,
          'User-Agent': 'TradingMCP/1.0',
        },
        params: {
          limit,
          sort: 'top',
        },
      });

      // Process comments from Reddit's nested structure
      const comments = this.flattenComments(response.data[1]?.data?.children || []);
      return comments;
    } catch (error) {
      console.error(`Error getting comments for post ${postId}:`, error);
      throw new Error(`Failed to get comments: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  private async ensureValidToken(): Promise<void> {
    if (this.accessToken && this.tokenExpiry && this.tokenExpiry > new Date()) {
      return; // Token is still valid
    }

    await this.authenticate();
  }

  private async authenticate(): Promise<void> {
    if (!config.reddit?.clientId || !config.reddit?.clientSecret || !config.reddit?.username || !config.reddit?.password) {
      throw new Error('Missing Reddit API credentials');
    }

    try {
      const auth = Buffer.from(`${config.reddit.clientId}:${config.reddit.clientSecret}`).toString('base64');
      
      const response = await axios.post(
        this.authUrl,
        new URLSearchParams({
          grant_type: 'password',
          username: config.reddit.username,
          password: config.reddit.password,
        }),
        {
          headers: {
            'Authorization': `Basic ${auth}`,
            'User-Agent': 'TradingMCP/1.0',
            'Content-Type': 'application/x-www-form-urlencoded',
          },
        }
      );

      this.accessToken = response.data.access_token;
      this.tokenExpiry = new Date(Date.now() + (response.data.expires_in * 1000));
      
      console.debug('Successfully authenticated with Reddit API');
    } catch (error) {
      console.error('Reddit authentication failed:', error);
      throw new Error('Failed to authenticate with Reddit API');
    }
  }

  private async searchSubreddit(
    query: string, 
    subreddit: string, 
    timeFilter: string, 
    limit: number, 
    sort: string
  ): Promise<RedditPost[]> {
    const response = await axios.get(`${this.baseUrl}/r/${subreddit}/search`, {
      headers: {
        'Authorization': `Bearer ${this.accessToken}`,
        'User-Agent': 'TradingMCP/1.0',
      },
      params: {
        q: query,
        restrict_sr: 'true',
        sort,
        t: timeFilter,
        limit,
      },
    });

    const posts: RedditPost[] = [];
    const children = response.data?.data?.children || [];

    for (const child of children) {
      const post = child.data;
      if (post && post.title) {
        posts.push({
          title: post.title,
          author: post.author,
          score: post.score,
          numComments: post.num_comments,
          url: `https://reddit.com${post.permalink}`,
          createdUtc: new Date(post.created_utc * 1000).toISOString(),
          subreddit: post.subreddit,
          selftext: post.selftext || '',
        });
      }
    }

    return posts;
  }

  private removeDuplicates(posts: RedditPost[]): RedditPost[] {
    const seen = new Set<string>();
    return posts.filter(post => {
      if (seen.has(post.url)) {
        return false;
      }
      seen.add(post.url);
      return true;
    });
  }

  private flattenComments(comments: any[]): any[] {
    const flattened: any[] = [];
    
    for (const comment of comments) {
      if (comment.data && comment.data.body) {
        flattened.push({
          author: comment.data.author,
          body: comment.data.body,
          score: comment.data.score,
          createdUtc: new Date(comment.data.created_utc * 1000).toISOString(),
        });

        // Recursively process replies
        if (comment.data.replies && comment.data.replies.data && comment.data.replies.data.children) {
          flattened.push(...this.flattenComments(comment.data.replies.data.children));
        }
      }
    }

    return flattened;
  }

  async getTrendingTickers(subreddits: string[] = ['wallstreetbets', 'stocks']): Promise<{ [ticker: string]: number }> {
    if (!isRedditConfigured()) {
      throw new Error('Reddit API credentials are not configured');
    }

    try {
      await this.ensureValidToken();
      
      const tickerMentions: { [ticker: string]: number } = {};
      const tickerRegex = /\$([A-Z]{1,5})\b|\b([A-Z]{2,5})\b/g;

      for (const subreddit of subreddits) {
        try {
          const response = await axios.get(`${this.baseUrl}/r/${subreddit}/hot`, {
            headers: {
              'Authorization': `Bearer ${this.accessToken}`,
              'User-Agent': 'TradingMCP/1.0',
            },
            params: {
              limit: 100,
            },
          });

          const posts = response.data?.data?.children || [];
          
          for (const post of posts) {
            const text = `${post.data.title} ${post.data.selftext || ''}`;
            let match;
            
            while ((match = tickerRegex.exec(text)) !== null) {
              const ticker = (match[1] || match[2]).toUpperCase();
              if (ticker.length >= 2 && ticker.length <= 5) {
                tickerMentions[ticker] = (tickerMentions[ticker] || 0) + 1;
              }
            }
          }
        } catch (error) {
          console.warn(`Failed to get trending tickers from r/${subreddit}:`, error);
        }
      }

      return tickerMentions;
    } catch (error) {
      console.error('Error getting trending tickers:', error);
      throw new Error(`Failed to get trending tickers: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }
}
