from time import timezone
from django.db import models

# Create your models here.
class GamesAndScores(models.Model):
    id = models.IntegerField(primary_key=True)
    slug = models.SlugField(max_length=250)
    competition = models.CharField(max_length=250)
    gameWeek = models.CharField(max_length=2)
    gameyear = models.CharField(max_length=4)
    startTimestamp = models.DateTimeField()
    gameWinner = models.IntegerField()
    statusType = models.CharField(max_length=250)
    statusTitle = models.CharField(max_length=250)
    homeTeamId = models.IntegerField()
    homeTeamSlug = models.CharField(max_length=250)
    homeTeamName = models.CharField(max_length=250)
    homeTeamScore = models.IntegerField()
    awayTeamId = models.IntegerField()
    awayTeamSlug = models.CharField(max_length=250)
    awayTeamName = models.CharField(max_length=250)
    awayTeamScore = models.IntegerField()
    gameAdded = models.DateTimeField(auto_now_add=True)
    gameUpdated = models.DateTimeField(auto_now=True)


def __str__(self):
    return self.slug



# {
#     "id": 10377587,
#     "startTimestamp": 1660508700,
#     "slug": "minnesota-vikings-las-vegas-raiders",
#     "scoreHomeAwaySlug": "26:20",
#     "scoreAwayHomeSlug": "20:26",
#     "winner": 1,
#     "status": {
#         "code": 100,
#         "type": "finished",
#         "title": "Ended"
#     },
#     "homeTeam": {
#         "id": 4390,
#         "name": "Las Vegas Raiders",
#         "short": "Las Vegas Raiders",
#         "slug": "las-vegas-raiders",
#         "teamColors": {
#             "primary": "#52b030",
#             "secondary": "#52b030"
#         }
#     },
#     "awayTeam": {
#         "id": 4423,
#         "name": "Minnesota Vikings",
#         "short": "Minnesota Vikings",
#         "slug": "minnesota-vikings",
#         "teamColors": {
    #             "primary": "#52b030",
    #             "secondary": "#52b030"
    #         }
    #     },
    #     "homeScore": {
    #         "current": 26,
    #         "display": 26,
    #         "period1": 3,
    #         "period2": 7,
    #         "period3": 6,
    #         "period4": 10
    #     },
    #     "awayScore": {
    #         "current": 20,
    #         "display": 20,
    #         "period1": 0,
    #         "period2": 6,
    #         "period3": 7,
    #         "period4": 7
    #     },
    #     "time": {},
    #     "competition": {
    #         "id": 9465,
    #         "name": "NFL Preseason",
    #         "slug": "nfl-preseason",
    #         "sport": {
    #             "id": 63,
    #             "name": "American Football",
    #             "slug": "american-football"
    #         },
    #         "category": {
    #             "id": 1370,
    #             "code": "US",
    #             "name": "USA",
    #             "slug": "usa",
    #             "flag": "usa"
    #         }
    #     }
    # }
