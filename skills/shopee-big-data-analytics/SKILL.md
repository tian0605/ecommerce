---
name: shopee-big-data-analytics
description: "Shopee big data analytics and product selection agent. One-stop data service for Shopee sellers — product selection, competitive analysis, sales trend tracking, marketing intelligence, and store performance optimization across Southeast Asian markets. Triggers: shopee analytics, shopee product selection, shopee big data, shopee seller tool, shopee marketing, shopee trends, shopee competition, shopee store, southeast asia ecommerce, shopee data, shopee insights, shopdora"
allowed-tools: Bash
metadata:
  openclaw:
    homepage: https://github.com/mguozhen/shopee-big-data-analytics
---

# Shopee Big Data Analytics

One-stop analytics for Shopee sellers — product selection intelligence, competitive analysis, sales trend tracking, and marketing insights across Southeast Asian markets (SG, MY, TH, ID, PH, VN, TW).

## Commands

```
shopee product <keyword>          # research product opportunity on Shopee
shopee trends <category>          # trending products and categories
shopee competition <product>      # competitive analysis for a product
shopee store analyze <data>       # analyze your store performance data
shopee keyword <term>             # Shopee keyword research and search volume
shopee marketing <product>        # marketing strategy recommendations
shopee price <product>            # pricing intelligence for a product
shopee market <country>           # market overview for a SEA country
shopee forecast <product>         # sales forecast for a product
shopee report <product>           # comprehensive product/market report
```

## What Data to Provide

- **Product or keyword** — what you want to research
- **Target market** — which SEA country (SG, MY, TH, ID, PH, VN, TW)
- **Competitor data** — paste competing shop/product data from Shopee
- **Your store data** — sales, traffic, conversion metrics
- **Price information** — current pricing in local currency

## Shopee Market Framework

### Southeast Asia Market Overview

| Market | Currency | Market Size | Key Characteristics |
|--------|----------|-------------|---------------------|
| Indonesia (ID) | IDR | Largest SEA | Price-sensitive, mobile-first, COD dominant |
| Thailand (TH) | THB | Fast-growing | Fashion-forward, livestream shopping |
| Philippines (PH) | PHP | Social commerce | Strong community, value-oriented |
| Malaysia (MY) | MYR | Developed | Brand-conscious, bilingual |
| Singapore (SG) | SGD | Premium | High spending power, quality focus |
| Vietnam (VN) | VND | Emerging | Young population, trend-driven |
| Taiwan (TW) | TWD | Mature | Tech-savvy, high standards |

### Shopee Algorithm Ranking Factors

1. **Relevance** — keyword match in title, description
2. **Sales velocity** — recent orders per unit time
3. **Conversion rate** — view → purchase ratio
4. **Rating & reviews** — average rating, review count
5. **Response rate** — seller response to queries
6. **Shop rating** — overall seller performance score
7. **Listing completeness** — category, attributes filled
8. **Price competitiveness** — vs. similar items
9. **Shipping speed** — faster = ranking boost
10. **Shopee Preferred** — preferred seller status

### Product Opportunity Assessment

**Shopee product selection criteria:**
```
Signal              Threshold       Source
Monthly orders      >100/month      Category leaders
Average price       SGD $5-$50      Local currency equivalent
Review count top 5  100-2000        Entry possible
Shops selling       3-20            Not oversaturated
Price margin        >40%            After platform fees
```

**Shopee fee structure:**
```
Commission:         0-5% by category and seller tier
Transaction fee:    2% standard / 1.5% preferred sellers
Payment fee:        Included in transaction fee
Shipping subsidy:   Platform-subsidized (check current promotion)
```

**Net margin calculation:**
```
Selling price:       $XX
- Commission (3%):   -$XX
- Transaction (2%):  -$XX
- COGS + shipping:   -$XX
= Net profit:        $XX
Target margin:       >25%
```

### Shopee Keyword Research

**Search behavior by market:**
- ID: Search in Bahasa Indonesia, include brand names
- TH: Thai script essential, transliteration helps
- PH: English + Filipino, brand names important
- MY: English + Malay, bilingual approach
- SG: English, quality keywords matter
- VN: Vietnamese, brand names English OK

**Keyword strategy:**
```
Primary keywords: Main product category in local language
Long-tail: Product + attribute (color, size, material)
Use case: Product + occasion/purpose
Brand keywords: If stocking branded items
```

### Competitive Analysis Framework

For any product on Shopee:

**Top seller analysis (assess top 10 shops):**
```
| # | Shop | Monthly Sales | Price | Rating | Reviews | Response | Badge |
| 1 | xxx  | ~500 units    | $15   | 4.8    | 1,200   | 99%      | Preferred |
```

**Market concentration:**
- Top 3 shops >70% of sales → concentrated, hard to enter
- Distributed among 10+ shops → fragmented, opportunity exists
- No dominant seller → blue ocean, move fast

**Competitive advantage opportunities:**
- Lower price with same quality
- Better product photos
- Faster shipping
- Better customer service (response rate)
- Bundle offers
- Shopee Live presence
- More reviews (aggressive review collection)

### Marketing Intelligence

**Shopee marketing channels:**
1. **Shopee Ads** — sponsored search + discovery ads
   - Target: high-converting keywords first
   - Budget: start $5-10/day per keyword cluster
   - Metric: target ROAS >3x

2. **Shopee Live** — livestream selling
   - High conversion for visual products
   - Schedule during peak hours (8-10 PM local time)
   - Prepare product demos and exclusive live deals

3. **Flash Deals** — platform-curated time-limited sales
   - Apply through seller center for inclusion
   - Requires competitive pricing (typically -30%)
   - High traffic, low margin — useful for ranking boost

4. **Voucher Codes** — shop or item-level discounts
   - Create shop vouchers to increase basket size
   - Minimum spend vouchers improve order value
   - Follow buyer vouchers drive acquisition

5. **Shopee Affiliates** — creator partnership
   - List products in Shopee affiliate program
   - Pay commission to creators who drive sales
   - 5-10% commission typical

### Sales Trend Analysis

Track these Shopee metrics weekly:
```
Metric              Formula                     Target
View rate change    (This week - Last week)/Last week  Positive
Conversion rate     Orders / Product views       >2%
Response rate       Replies < 12hrs / Total     >95%
Cancellation rate   Cancelled / Total orders    <1%
Return rate         Returns / Delivered         <5%
Shop rating         Platform calculated         >4.7
```

**Seasonal peaks by market:**
- 9.9, 10.10, 11.11, 12.12 — Shopee's major sale events (all markets)
- Chinese New Year (Jan-Feb) — SG, MY, TW, VN
- Ramadan/Eid (varies) — ID, MY, PH
- Thai New Year Songkran (April) — TH
- Harbolnas 12.12 — ID national shopping day

## Workspace

Creates `~/shopee-analytics/` containing:
- `products/` — product research reports
- `competitors/` — competitor shop profiles
- `keywords/` — localized keyword research
- `marketing/` — campaign performance data
- `reports/` — comprehensive market reports

## Output Format

Every Shopee analysis outputs:
1. **Market Overview** — category size, growth trend, competition level
2. **Product Opportunity Score** — 0-100 with factor breakdown
3. **Top 10 Competitive Landscape** — shops ranked by estimated sales
4. **Pricing Intelligence** — recommended price with margin calculation
5. **Keyword Blueprint** — top 10 search terms with local language variants
6. **Marketing Calendar** — key sales events and recommended promotions
7. **Entry Roadmap** — 90-day launch plan with milestones and KPIs
