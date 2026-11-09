# Phase 5 — Threat Intelligence (Feed, DISARM, Network Analysis)

## Context
Read `00-PROJECT-BRIEF.md` for full context. Phases 1-4 are built. Now we build the advanced threat intelligence features that differentiate CivicGuards from simple fact-checkers — the features that make it a real threat intelligence platform comparable to Cyabra, Blackbird.AI, and Logically.

## Objective
Build a real-time threat feed of trending misinformation, advanced DISARM framework visualization, network/spread analysis, and narrative tracking. This is the layer that justifies enterprise pricing and attracts researchers/journalists.

---

## Task 1: Threat Feed (Live Intelligence Dashboard)

**Location**: `/dashboard/threats`

### Concept:
A real-time, continuously-updating dashboard showing the current misinformation landscape — like a "weather map" for disinfo. Data comes from aggregated user scans, community reports, and trending claims.

### Layout:

**Top Bar — Threat Level Indicator:**
- Global "Threat Level" gauge: Low / Moderate / Elevated / High / Critical
- Calculated from: volume of flagged scans in last 24h, average threat scores, rate of new reports
- Color-coded background strip

**Trending Narratives Section:**
- Cards showing the most-scanned/reported misinformation narratives right now
- Each narrative card shows:
  - Narrative title/summary (AI-generated cluster label)
  - Threat score (average across related scans)
  - Volume indicator (how many scans/reports)
  - Trend arrow (rising/falling/stable)
  - Top DISARM techniques used
  - Time first detected
  - "Investigate →" button to see all related scans
- Cluster similar claims together using pgvector similarity
- Update periodically (every 15 minutes or on-demand refresh)

**Category Breakdown:**
- Horizontal bar chart or heatmap showing misinformation by category:
  - Politics, Health, Science, Finance, Technology, Conflict, Climate, Other
- Click a category to filter the feed

**Recent High-Threat Scans:**
- Live-updating list of recent scans with threat score > 70
- Shows: content preview, threat score, engines that flagged it, time
- Real-time feel (new entries slide in from top)

**Geographic Spread (Future Enhancement Placeholder):**
- Map visualization showing where misinformation is being detected
- Placeholder with "Coming Soon" label
- When implemented, this would use IP geolocation from scan requests

---

## Task 2: DISARM Framework Explorer

**Location**: `/dashboard/disarm`

### Interactive DISARM Matrix:
Build a visual matrix similar to the MITRE ATT&CK Navigator:

- **Rows**: DISARM Phases (Plan → Prepare → Execute → Assess)
- **Columns**: Tactics within each phase
- **Cells**: Individual techniques
- Each cell is color-coded by how frequently that technique has been detected in CivicGuards scans:
  - Gray: Never seen
  - Light green: Rarely seen (<5 detections)
  - Yellow: Occasionally seen (5-20 detections)
  - Orange: Frequently seen (20-100 detections)
  - Red: Very frequently seen (100+ detections)

### Technique Detail View:
Click on any technique cell to see:
- Full technique description (from DISARM database)
- Real examples detected by CivicGuards (anonymized scan excerpts)
- Related techniques (commonly used together)
- Counter-techniques (DISARM Blue — defensive responses)
- "Learn about this technique →" link to Education Hub
- Statistics: total detections, trend over time, common co-occurring techniques

### DISARM Heat Map:
- A time-series view showing which techniques are trending up/down over the last 30 days
- Helps researchers identify emerging tactics

### Filter & Export:
- Filter by phase, tactic, time range, threat level
- Export current view as CSV or PDF
- Pro/Enterprise feature

---

## Task 3: Narrative Tracking (Inspired by Blackbird.AI)

### Concept:
Group related scans and reports into "Narratives" — clusters of misinformation around the same false claim or theme. Track how narratives evolve, spread, and are countered.

### Narrative Detection:
```python
# When a new scan comes in:
# 1. Generate embedding of the claim/content
# 2. Search existing narratives by embedding similarity (threshold: 0.80)
# 3. If match: add scan to existing narrative, update stats
# 4. If no match: create new narrative with this scan as seed
# 5. Periodically re-cluster narratives to merge/split as needed
```

### Narrative Detail Page (`/dashboard/threats/narratives/[narrativeId]`):

- **Narrative Summary**: AI-generated title and description
- **Timeline**: When claims in this narrative were first and last seen
- **Volume Chart**: Line chart showing scan/report volume over time
- **Variant List**: All the different versions/mutations of this claim
- **DISARM Techniques**: Which techniques are used across this narrative
- **Source Analysis**: Which domains/sources are spreading this narrative
- **Engine Consensus**: Aggregated verdicts across all scans in the narrative
- **Related Narratives**: Other narratives that share techniques or sources

### Narrative List View (`/dashboard/threats/narratives`):
- Table of all tracked narratives
- Columns: Title, Status (Active/Declining/Resolved), Threat Score, Volume, First Seen, Last Activity, Top Techniques
- Sortable and filterable
- Search by keyword

---

## Task 4: Source Intelligence

### Source Database Enhancement:
Expand the `sources` table into a proper source intelligence system.

**Source Profile Page (`/dashboard/sources/[domain]`):**
- Domain name, description, category
- Credibility Score gauge (0-100)
- Bias Rating visualization (Far Left ← Left ← Center → Right → Far Right)
- Factual Reporting grade (Very High → Very Low)
- MBFC (Media Bias/Fact Check) data if available
- Historical scan data: how many times this source's content was scanned, average threat score
- DISARM techniques commonly found in this source's content
- Timeline of flagged content from this source
- Related/sister domains

**Source Explorer (`/dashboard/sources`):**
- Searchable table of all sources in the database
- Filter by credibility score range, bias rating, category
- Sort by credibility, number of scans, average threat score
- "Add Source" form for community contributions (moderated)

### Source Credibility API Enhancement:
```python
# When a URL is scanned:
# 1. Extract domain
# 2. Check sources table for existing profile
# 3. If not found: create basic profile (domain, first scan date)
# 4. Every 10 scans of a domain: recalculate credibility score based on:
#    - Historical threat scores of content from this domain
#    - Community votes on reports from this domain
#    - Known fact-check database entries
#    - Domain age and registration info
# 5. Track domain credibility over time (credibility_history table)
```

---

## Task 5: Advanced Scan Insights

### Cross-Scan Analysis:
When a user views their scan history (Pro), provide AI-generated insights:
- "You've been encountering a lot of content using emotional manipulation tactics lately"
- "3 of your recent scans are part of the same misinformation narrative about [topic]"
- "This source has appeared in 5 of your scans and has low credibility"

### Scan Correlation:
Show connections between scans:
- Same source
- Same DISARM techniques
- Same narrative cluster
- Similar content (pgvector)
- Visualize as a network graph (using d3.js or similar)

---

## Task 6: Alerts System (Pro/Enterprise)

### Custom Alerts:
Pro users can set up alerts:
- **Keyword Alert**: "Notify me when a scan mentions [keyword]"
- **Source Alert**: "Notify me when content from [domain] is flagged"
- **Technique Alert**: "Notify me when [DISARM technique] is detected"
- **Narrative Alert**: "Notify me about updates to narrative [X]"
- **Threshold Alert**: "Notify me when the global threat level reaches [High]"

### Alert Delivery:
- In-app notifications (existing notification system)
- Email digest (daily/weekly summary) — use SendGrid or similar
- Webhook (Enterprise) — POST to customer URL

### Backend:
```
POST /api/v1/alerts                  — Create an alert
GET  /api/v1/alerts                  — List user's alerts
PATCH /api/v1/alerts/{id}            — Update alert
DELETE /api/v1/alerts/{id}           — Delete alert
GET  /api/v1/alerts/{id}/history     — Alert trigger history
```

New table:
```
alerts: id, user_id, alert_type, config_json, enabled, created_at
alert_triggers: id, alert_id, triggered_at, trigger_data_json, notification_sent
```

---

## Backend Endpoints Summary:

```
# Threat Feed
GET  /api/v1/threats/overview          — Threat level + summary stats
GET  /api/v1/threats/trending           — Trending narratives
GET  /api/v1/threats/recent             — Recent high-threat scans
GET  /api/v1/threats/categories         — Category breakdown

# DISARM
GET  /api/v1/disarm/matrix             — Full matrix data with detection counts
GET  /api/v1/disarm/techniques/{id}    — Technique detail with examples
GET  /api/v1/disarm/heatmap            — Time-series technique trends

# Narratives
GET  /api/v1/narratives                — List narratives
GET  /api/v1/narratives/{id}           — Narrative detail
GET  /api/v1/narratives/{id}/timeline  — Narrative timeline data
GET  /api/v1/narratives/{id}/scans     — Scans in this narrative

# Sources
GET  /api/v1/sources                   — List sources
GET  /api/v1/sources/{domain}          — Source profile
GET  /api/v1/sources/{domain}/history  — Source credibility history

# Alerts
POST /api/v1/alerts
GET  /api/v1/alerts
PATCH /api/v1/alerts/{id}
DELETE /api/v1/alerts/{id}
```

---

## Deliverables Checklist
- [ ] Threat feed dashboard with live-updating data
- [ ] Threat level calculation and display
- [ ] Trending narratives detection and display
- [ ] DISARM interactive matrix (ATT&CK Navigator style)
- [ ] DISARM technique detail pages with real examples
- [ ] DISARM heatmap with time-series trends
- [ ] Narrative tracking system (auto-clustering)
- [ ] Narrative detail pages with timeline and variants
- [ ] Source intelligence profiles
- [ ] Source explorer with search and filters
- [ ] Cross-scan analysis and insights (Pro)
- [ ] Scan correlation network visualization
- [ ] Custom alerts system (Pro/Enterprise)
- [ ] Alert delivery (in-app + email)
- [ ] All new API endpoints
