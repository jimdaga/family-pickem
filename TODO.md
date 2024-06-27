# Project Name
Pickem

## TO TRACKER

### In Progress
- [ ] homepage 
- [ ] standings page 
- [ ] Mark the TieBreaker games in db 

### To Do
- [ ] Setup `eb deploy` using github actions 
- [ ] Users without picks doesn't show when everyone has picked 
- [ ] Standings page to include "most weeks won" metrics 
- [ ] Add phone numbers to users 
- [ ] Send text when picks not made 
- [ ] Add (5/12) type counter to picks made/not made 
- [ ] Hide "picks" or "picks made" if == 0 
- [ ] Add audit database 
- [ ] Give users way to change username (remove dependency on username in points)

### Done 
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
- [ ] test
