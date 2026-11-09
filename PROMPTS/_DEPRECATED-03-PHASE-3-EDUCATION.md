# Phase 3 — Education Hub (Duolingo for Media Literacy)

## Context
Read `00-PROJECT-BRIEF.md` for full context. Phase 1 (foundation) and Phase 2 (scanner) are built. Now we build the education hub — a gamified learning platform that teaches media literacy using inoculation theory, directly tied to the DISARM framework and real-world examples from the scanner.

## Objective
Build a complete learning experience with courses, interactive lessons, multiple quiz types, gamification (XP, streaks, badges, leaderboards), and progress tracking. The education content should reference real DISARM techniques so users learn the actual playbook that disinformation actors use.

---

## Task 1: Education Hub Home

**Location**: `/dashboard/learn`

### Layout:
- **Header**: "Build Your Immunity" — subtitle: "Learn to identify and resist misinformation tactics"
- **Stats Bar**: Current streak (fire icon + days), Total XP, Badges earned, Rank on leaderboard
- **Continue Learning**: Card showing the user's current in-progress lesson with progress bar
- **Course Grid**: All available courses displayed as cards

### Course Cards:
Each card shows:
- Course icon (lucide-react icon)
- Title
- Difficulty badge (Beginner/Intermediate/Advanced — color coded green/yellow/red)
- Progress bar (X/Y lessons completed)
- Brief description
- Estimated time

---

## Task 2: Course Structure & Content

### Pre-Built Courses:

**Course 1: "Foundations of Misinformation" (Beginner)**
5 lessons covering:
1. What is misinformation vs disinformation vs malinformation?
2. Why does misinformation spread? (psychology, cognitive biases)
3. The misinformation ecosystem (who creates it and why)
4. How social media amplifies false narratives
5. Introduction to fact-checking basics

**Course 2: "Spot the Tactics" (Beginner)**
6 lessons, each focused on a major DISARM tactic:
1. Emotional Manipulation (DISARM: TA06 Develop Content)
2. Fake Experts & False Authority (DISARM: T0009 Create fake experts)
3. Conspiracy Amplification (DISARM: T0022 Conspiracy narratives)
4. Cherry-Picking & Misleading Stats (DISARM: T0023 Distort facts)
5. Bot Networks & Fake Amplification (DISARM: T0046 Use fake accounts)
6. Impersonation & Fake Sources (DISARM: T0007 Create inauthentic pages)

**Course 3: "Visual Misinformation" (Intermediate)**
4 lessons:
1. Manipulated images — how to spot edits and out-of-context photos
2. Deepfake videos — detection clues and tools
3. Misleading charts and data visualizations
4. Reverse image search techniques

**Course 4: "The Disinformation Playbook" (Advanced)**
Based entirely on the DISARM framework:
1. Phase 1: Plan — How campaigns are planned (target audiences, goals)
2. Phase 2: Prepare — Infrastructure setup (fake accounts, websites, content creation)
3. Phase 3: Execute — Distribution tactics (amplification, cross-platform spread)
4. Phase 4: Assess — How disinformation actors measure success
5. Real-world case studies (mapped to DISARM)

**Course 5: "Be a Digital Detective" (Intermediate)**
Practical skills:
1. OSINT basics — open source intelligence for verification
2. Checking sources and cross-referencing claims
3. Using CivicGuards scanner effectively
4. Evaluating source credibility
5. Building a personal fact-checking workflow

---

## Task 3: Lesson Page

**Location**: `/dashboard/learn/[courseId]/[lessonId]`

### Lesson Content Format (`content_json` structure):
```json
{
  "blocks": [
    { "type": "text", "content": "Markdown text content..." },
    { "type": "callout", "variant": "info|warning|tip", "content": "Important note..." },
    { "type": "example", "headline": "Fake headline example", "explanation": "Why this is misleading...", "disarmTechnique": "T0023" },
    { "type": "comparison", "real": { "text": "...", "source": "..." }, "fake": { "text": "...", "tactics": ["T0023", "T0007"] } },
    { "type": "interactive", "interactionType": "reveal", "question": "Can you spot what's wrong?", "content": "...", "answer": "..." },
    { "type": "image", "url": "...", "caption": "...", "isManipulated": true },
    { "type": "disarm_card", "techniqueId": "T0023", "showInContext": true },
    { "type": "quiz_inline", "quizId": "..." }
  ]
}
```

### Lesson Page Layout:
- Left sidebar: Course outline with lesson list, current lesson highlighted, checkmarks on completed ones
- Main content: Rendered lesson blocks with nice typography
- Progress indicator at top (lesson 3 of 6)
- "Mark as Complete" button at bottom (only active after reading + passing quiz)
- XP earned animation when completing a lesson
- "Next Lesson →" button

---

## Task 4: Quiz System

### Quiz Types:

**1. Multiple Choice**
Standard 4-option questions. After answering, show explanation.

**2. Spot the Fake**
Present 2-4 headlines/claims side by side. User must identify which ones are fake. Timer optional. Shows DISARM technique used in the fake ones after answering.

**3. Identify the Tactic**
Show a piece of misinformation content and ask the user to identify which DISARM technique is being used. Multiple choice from 4 technique options. Links to the DISARM technique card on correct answer.

**4. True or False**
Quick-fire round. Present claims rapidly. User swipes or clicks True/False. Score based on accuracy and speed. Great for streak-building.

**5. Inoculation Challenge (Special)**
Inspired by Bad News Game. Present a scenario: "You're a disinformation agent trying to spread a false narrative about [topic]. Which tactic would be most effective?" User chooses from DISARM techniques. After choosing, the lesson explains why that tactic works and how to defend against it. This is the "weakened dose" inoculation approach.

### Quiz Page Layout (`/dashboard/learn/[courseId]/[lessonId]/quiz`):
- Clean, focused UI — no sidebar distractions
- Question number / total indicator
- Large question text
- Answer options as shadcn cards or buttons (not radio buttons — make them tappable/clickable)
- After answering: green flash for correct, red for incorrect
- Show explanation text + DISARM technique card if applicable
- Score summary at end with XP earned
- "Retry" or "Next Lesson" buttons

---

## Task 5: Gamification System

### XP Points:
- Complete a lesson: +10 XP
- Pass a quiz (>70%): +20 XP
- Perfect quiz score: +30 XP (bonus)
- First scan of the day: +5 XP
- Daily login: +2 XP
- Report verified misinformation in community: +15 XP

### Streaks:
- Track consecutive days with at least one lesson completed or quiz taken
- Display streak with fire icon
- Streak freeze: Pro users get 1 free freeze per week (don't break streak if missed a day)
- Show streak on dashboard and profile

### Badges:
```
FIRST_SCAN          — "First Light" — Complete your first scan
FIRST_LESSON        — "Student" — Complete your first lesson
COURSE_COMPLETE     — "Graduate" — Complete a full course
ALL_COURSES         — "Scholar" — Complete all courses
PERFECT_QUIZ        — "Sharp Eye" — Get 100% on a quiz
STREAK_7            — "On Fire" — 7-day streak
STREAK_30           — "Dedicated" — 30-day streak
SCANS_100           — "Veteran Scanner" — Complete 100 scans
COMMUNITY_FIRST     — "Truth Teller" — Submit first community report
COMMUNITY_VERIFIED  — "Verified" — Have a report verified by experts
DISARM_MASTER       — "Tactician" — Learn all DISARM techniques
```

### Leaderboard (`/dashboard/learn/leaderboard`):
- Tabs: Weekly / Monthly / All-Time
- Show: Rank, Avatar, Name, XP, Streak, Badges count
- Highlight current user's position
- Top 3 get special styling (gold, silver, bronze)

---

## Task 6: Progress Tracking

### User Progress Dashboard (`/dashboard/learn`):
- Overall completion percentage across all courses
- Individual course progress bars
- XP history graph (last 30 days)
- Badges showcase (earned + locked with silhouettes)
- Skills radar chart: rate user's knowledge across DISARM categories

### Backend Endpoints:
```
GET  /api/v1/education/courses              — List all courses
GET  /api/v1/education/courses/{id}         — Course detail with lessons
GET  /api/v1/education/lessons/{id}         — Lesson content
POST /api/v1/education/lessons/{id}/complete — Mark lesson complete
GET  /api/v1/education/quizzes/{id}         — Get quiz questions
POST /api/v1/education/quizzes/{id}/submit  — Submit quiz answers, return score
GET  /api/v1/education/progress             — User's overall progress
GET  /api/v1/education/leaderboard          — Leaderboard data
GET  /api/v1/education/badges               — User's badges
POST /api/v1/education/streak/check         — Check and update streak
```

---

## Task 7: Scanner ↔ Education Integration

This is what makes CivicGuards unique — the scanner and education are connected:

1. **On scan results page**: If DISARM techniques are detected, show "Learn about this tactic →" links that go to the relevant lesson
2. **In lessons**: "See real examples →" links that show actual scans from the database that used this technique
3. **After scanning**: If user scans something flagged as misinformation, prompt: "This uses [Tactic Name]. Want to learn how to spot it? Start the lesson →"
4. **Quiz content from real scans**: Generate quiz questions from actual flagged content (anonymized). "This real headline was flagged. Can you identify why?"

---

## Seed Content

Create at least:
- All 5 courses with full metadata
- 3 complete lessons per course with full content_json (at minimum)
- 2 quizzes per lesson with 5 questions each
- All badge definitions
- DISARM technique cards for the top 20 most common techniques

---

## Deliverables Checklist
- [ ] Education hub home page with course grid
- [ ] Course detail page with lesson list
- [ ] Lesson page with block-based content rendering
- [ ] All 5 quiz types implemented
- [ ] XP system with proper point awards
- [ ] Streak tracking with visual display
- [ ] Badge system with earn conditions
- [ ] Leaderboard with weekly/monthly/all-time tabs
- [ ] Progress tracking across all courses
- [ ] Scanner ↔ Education cross-linking
- [ ] All 5 courses with seed content
- [ ] Gamification animations (XP pop-ups, badge unlocks, streak celebrations)
- [ ] Mobile-responsive quiz interface
