# Free Alternative Data Sources (Underutilized)

Data that's freely available but not widely used by retail traders.

## 1. Wikipedia Page Views (We have this)
- **Signal:** Rising views = retail attention before price move
- **Code:** `wikipedia_views.py`
- **Edge:** Leading indicator for meme stocks / retail interest

## 2. SEC EDGAR - Beyond 10-K/10-Q (We have this)
- **Signal:** "Going concern" warnings, material weakness
- **Code:** `sec_filing_risk.py`
- **Edge:** Early warning system (not price predictor)

## 3. Google Trends (Free API)
- **Signal:** Search volume for stock tickers, "buy [ticker]", "short [ticker]"
- **API:** `https://trends.google.com/trends/api/explore` (unofficial)
- **Edge:** Retail sentiment leading indicator
- **Rate limits:** Very strict (need delays)

## 4. Reddit API (Free tier)
- **Signal:** r/wallstreetbets, r/stocks mention velocity
- **API:** `https://www.reddit.com/r/wallstreetbets/search.json?q=ticker&sort=new`
- **Edge:** Detect pump/dump early
- **Code:** Already in `sentiment_intelligence.py`

## 5. Economic Calendar (Free)
- **Signal:** FOMC, CPI, employment dates
- **API:** `https://www.forexfactory.com/calendar` (scrape) or `nager.date` (holiday API)
- **Edge:** Avoid trading into macro events

## 6. Patent Filings (Free USPTO)
- **Signal:** New patent grants for tech/biotech companies
- **API:** `https://developer.uspto.gov/api-catalog` (free registration)
- **Edge:** Innovation surprise for small caps

## 7. Job Postings (Free tiers)
- **Signal:** Rapid hiring = growth acceleration
- **API:** `https://data.usajobs.gov/` (gov only) or scrape Indeed (fragile)
- **Edge:** Employment as growth signal

## 8. Shipping/Port Data (Free)
- **Signal:** Import/export volume for supply chain stocks
- **API:** `https://www.pierpass.org/` or `https://www.portoflosangeles.org/business/statistics/` (scrape)
- **Edge:** Early inventory/sales signal for retail

## 9. Weather Data (Free NOAA)
- **Signal:** Droughts affect agriculture, cold snaps affect energy
- **API:** `https://www.weather.gov/documentation/services-web-api`
- **Edge:** Commodity/cyclical stock prediction

## 10. Geopolitical Risk (Free GDELT)
- **Signal:** Global event database
- **API:** `https://blog.gdeltproject.org/` (BigQuery free tier)
- **Edge:** Oil, defense, shipping stocks

## 11. Options Chain (Free tiers)
- **Signal:** Unusual call/put volume, IV skew
- **API:** `https://www.alphavantage.co/documentation/` (5 calls/min free)
- **Edge:** Smart money positioning

## 12. Fed Speech Calendar (Free)
- **Signal:** Fed speakers = volatility
- **API:** `https://www.federalreserve.gov/newsevents/calendar.htm` (scrape)
- **Edge:** Volatility timing

## Most Promising for Free Edge:

1. **Google Trends + Reddit combo** - Retail sentiment divergence
2. **Options flow (Alpha Vantage free tier)** - Unusual activity detection
3. **Patent + hiring for small cap tech** - Fundamental surprise
4. **Weather + commodities** - Cyclical edge

All can be accessed free with rate limits and creativity.
