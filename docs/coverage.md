# FINN coverage audit

Updated: 03 Nov 2026, 00:22 IST

Scope: 50 dynamic Pull slots (strict 50-company LRU); separate fixed Push portfolio: 18 companies.

Profiles: 50/50; financials: 50/50; trajectory tables: 50/50 (48 have five annual observations; shorter available histories are labeled).

| Ticker | Profile | Financials | Years | Narrative | First ms | Cached median ms | Max ms |
|---|---|---|---:|---|---:|---:|---:|
| 20MICRONS | Saved | Saved | 5 | Saved | 20.43 | 15.37 | 20.43 |
| APOLLOHOSP | Saved | Saved | 5 | Saved | 22.87 | 19.68 | 22.87 |
| ASIANPAINT | Saved | Saved | 5 | Saved | 20.2 | 13.62 | 20.2 |
| BAJFINANCE | Saved | Saved | 5 | Saved | 20.77 | 14.39 | 20.77 |
| BHARTIARTL | Saved | Saved | 5 | Saved | 29.65 | 14.64 | 29.65 |
| BSE | Saved | Saved | 5 | Saved | 17.89 | 15.84 | 17.89 |
| CAMS | Saved | Saved | 5 | Saved | 16.95 | 11.94 | 16.95 |
| COFORGE | Saved | Saved | 5 | Saved | 24.61 | 15.54 | 24.61 |
| DIXON | Saved | Saved | 5 | Saved | 15.73 | 14.11 | 17.33 |
| DMART | Saved | Saved | 5 | Saved | 18.68 | 12.65 | 20.51 |
| HAL | Saved | Saved | 5 | Saved | 18.12 | 11.45 | 18.12 |
| HAVELLS | Saved | Saved | 5 | Saved | 16.03 | 10.08 | 16.03 |
| HDFCBANK | Saved | Saved | 5 | Saved | 15.59 | 10.05 | 15.59 |
| HINDUNILVR | Saved | Saved | 5 | Saved | 13.63 | 11.79 | 13.63 |
| ICICIBANK | Saved | Saved | 5 | Saved | 14.32 | 10.25 | 14.32 |
| INFY | Saved | Saved | 5 | Saved | 12.09 | 10.28 | 12.09 |
| KAYNES | Saved | Saved | 5 | Saved | 15.14 | 11.28 | 24.51 |
| LT | Saved | Saved | 5 | Saved | 12.85 | 11.44 | 12.85 |
| MARUTI | Saved | Saved | 5 | Saved | 13.62 | 10.57 | 13.62 |
| NTPC | Saved | Saved | 5 | Saved | 14.61 | 11.85 | 14.61 |
| PERSISTENT | Saved | Saved | 5 | Saved | 16.64 | 12.32 | 16.64 |
| POLYCAB | Saved | Saved | 5 | Saved | 15.43 | 10.77 | 15.43 |
| RELIANCE | Saved | Saved | 5 | Saved | 13.29 | 10.02 | 13.29 |
| SEDEMAC | Saved | Saved | 5 | Saved | 12.68 | 10.63 | 14.76 |
| SIEMENS | Saved | Saved | 5 | Saved | 8.49 | 10.23 | 25.47 |
| SRF | Saved | Saved | 5 | Saved | 21.83 | 13.47 | 21.83 |
| SUNPHARMA | Saved | Saved | 5 | Saved | 15.69 | 12.85 | 18.11 |
| TATACAP | Saved | Saved | 5 | Saved | 14.81 | 13.21 | 14.81 |
| TATAMOTORS | Saved | Saved | 5 | Saved | 15.03 | 11.42 | 15.03 |
| TCS | Saved | Saved | 5 | Saved | 16.31 | 13.68 | 16.31 |
| TITAN | Saved | Saved | 5 | Saved | 20.24 | 14.97 | 28.8 |
| TRENT | Saved | Saved | 5 | No primary transcript | 16.01 | 13.89 | 24.68 |
| ULTRACEMCO | Saved | Saved | 5 | Saved | 16.56 | 12.18 | 16.69 |
| VBL | Saved | Saved | 5 | Saved | 14.22 | 14.54 | 15.21 |
| ZOMATO | Saved | Saved | 5 | Saved | 21.27 | 14.26 | 21.27 |
| AXISBANK | Saved | Saved | 5 | Saved | 17.71 | 13.43 | 17.71 |
| BEL | Saved | Saved | 5 | Saved | 14.0 | 13.39 | 24.23 |
| CHOLAFIN | Saved | Saved | 5 | Saved | 13.32 | 12.23 | 13.43 |
| CIPLA | Saved | Saved | 5 | Saved | 16.19 | 10.76 | 16.19 |
| EICHERMOT | Saved | Saved | 5 | Saved | 14.69 | 12.39 | 15.64 |
| HCLTECH | Saved | Saved | 5 | Saved | 16.84 | 11.13 | 16.84 |
| ITC | Saved | Saved | 5 | No primary transcript | 9.86 | 7.85 | 9.9 |
| JIOFIN | Saved | Saved | 4 | Saved | 13.66 | 11.8 | 13.66 |
| KOTAKBANK | Saved | Saved | 5 | Saved | 15.7 | 10.5 | 22.33 |
| M&M | Saved | Saved | 5 | Saved | 12.88 | 9.78 | 12.88 |
| NESTLEIND | Saved | Saved | 3 | Saved | 11.45 | 13.01 | 13.98 |
| POWERGRID | Saved | Saved | 5 | Saved | 12.63 | 10.34 | 13.49 |
| SBIN | Saved | Saved | 5 | Saved | 11.99 | 11.64 | 30.87 |
| TATASTEEL | Saved | Saved | 5 | Saved | 13.32 | 9.78 | 13.32 |
| WIPRO | Saved | Saved | 5 | Saved | 12.98 | 9.29 | 12.98 |

Warm localhost HTTP session (/api/health first), then first opening plus five repeats per ticker; includes JSON transfer and parsing.
All cached medians below 25 ms: True; requests below 25 ms: 296/300.
Maximum measured response: 30.87 ms. All 50 cached medians below 50 ms: True. All 300 timed samples below 50 ms: True.
Times are measurements on this machine, not a phone/Wi-Fi SLA.
Legacy labels: ZOMATO uses ETERNAL source data; TATAMOTORS uses TMPV (passenger vehicles) source data. Historical figures may span reorganisations. Source links and names are preserved in the app.
[NSE Eternal announcement](https://www.nseindia.com/companies-listing/corporate-filings-announcements?symbol=ETERNAL) · [NSE Tata Motors symbol-change circular](https://nsearchives.nseindia.com/content/circulars/FAOP70882.pdf)

Short histories are shown as available, without invented annual observations: JIOFIN (4 years), NESTLEIND (3 years).

## 51st-company LRU verification

Checked 2026-11-02T18:39:52.190087+00:00: CLEAN fetched real profile/financial/trajectory data in a backup of the 50-company cache. The least-recently searched company, APOLLOHOSP, was evicted. Pull retained exactly 50 companies; all 18 Push holdings and their digest remained unchanged. Reopening preserved the eviction. The original initial 50-company demo cache was preserved.
