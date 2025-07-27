# Project Name
Pickem

## To Do

#### General Changes 
High Priority 
- [ ] Set all the tiebreaker games for 2025-2026
- [ ] Disable devmode on prod site
- [ ] setup argocd to auto deploy 

Medium Priority 
- [ ] Add a cronjob to delete stuck update data jobs
- [ ] Add dark mode to site {WIP}
- [ ] Setup pick e-mail reminders -- or --
- [ ] Send text when picks not made 

Low Priority
- [ ] Add audit database 

#### Standings Page Changes
Medium Priority 
- [ ] Add up/down icons with week over week change

#### Picks Page Changes
Medium Priority 
- [ ] Add % win likely 

#### Stats Page Changes 

#### Homepage Changes
Medium Priority 
- [ ] Add AI Summary of prior week 

#### Scores Page Changes 
Medium Priority 
- [ ] Show what % each team was picked 
- [ ] Add stadium / tv details
- [ ] Link "preview" to ESPN preview 

#### Long Term Changes 
- [ ] Concept of "Families" 
- [ ] Add user profiles and link user avatars 
- [ ] Prop Bets page 
- [ ] hall of fame

## Done 
- [x] Finish writing tool to generate stats
- [x] For past seasons show the winner at the top
- [x] Allow editing picks before they lock 
- [x] Fullscreen tiebreaker should be a new line so it doesn't overflow
- [x] Fix place circle to be top left 
- [x] Make picks lock at 1PM Sat (add "locked" to game?)
- [x] Give users way to change username (remove dependency on username in points)
- [x] Add "Favorite Team"
- [x] Add "Tagline" and update League Member 
- [x] Implement "Edit" button 
- [x] Add phone numbers to users 
- [x] Fix alignment so LIVE doesn't make scores not line up 
- [x] Make live/final/upcoming buttons work 
- [x] Show box score on mobile
- [x] Make site live refresh 
- [x] Ensure team record shows
- [x] Update prod instance with weeks/games for 2023/24
- [x] Fix records to use current season
- [x] Add 'season' logic to picks
- [x] Update scores page to be aware of year/season 
- [x] Refactor score updates to use ESPN api
- [x] Link to ESPN team logos (https://a.espncdn.com/i/teamlogos/nfl/500/ne.png)
- [x] Add "winner" to each week's page 
- [x] Home team not getting scores (1-4) after game ends
- [x] Automate teams win/losses 
- [x] Update `GameScored` in pick update 
- [x] Script to update correct picks (http://localhost:8000/api/unscored)
- [x] Fix "active games" api
- [x] Add tie breaker 
- [x] Add per quarter scores 
- [x] Update wins/losses logic for teams 
- [x] Cronjobs to run all background scripts 
- [x] fix navbar dropdowns (bootstrap javascript issue?)
- [x] fix navbar hiding things
- [x] Deploy to AWS w/ RDS 
- [x] Inprogress Pick pills not showing on scores page 
- [x] rules page 
- [x] Show submitted "tie breaker" on picks page 
- [x] Recollect all the game data (for each week, update)
