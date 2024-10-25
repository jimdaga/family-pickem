from django import template
from django.contrib.auth.models import User
from pickem_api.models import Teams, GamePicks, userSeasonPoints, userStats
from django.shortcuts import render
from allauth.socialaccount.models import SocialAccount
from datetime import date

register = template.Library()

def get_season():
    # I'll probably hate myself in the future for hardcoding this :) 
    today = date.today()
    today_datestamp = date(today.year, today.month, today.day)

    if today_datestamp > date(2022, 4, 1) and today_datestamp < date(2023, 4, 1):
        return '2223'
    elif today_datestamp > date(2023, 4, 1) and today_datestamp < date(2024, 4, 1):
        return '2324'
    elif today_datestamp > date(2024, 4, 1):
        return '2425'

@register.filter
def addstr(arg1, arg2):
    """concatenate arg1 & arg2"""
    return str(arg1) + str(arg2)

@register.filter
def lookupname(id):
    user = User.objects.get(id=id)
    return user

@register.filter
def lookupavatar(user_id):
    try:
        social_account = SocialAccount.objects.get(user_id=user_id)
        avatar_url = social_account.get_avatar_url()
    except SocialAccount.DoesNotExist:
        # avatar_url = None
        avatar_url = "https://www.wmata.com/systemimages/icons/menu-car-icon.png"
    
    return avatar_url


@register.filter
def lookuplogo(slug):
    if slug != None:
        logo = Teams.objects.get(teamNameSlug=slug)
    else:
        logo = {
            'teamLogo': None
        }
    return logo

@register.filter
def lookuppick(id):
    pick = GamePicks.objects.filter(id=id).distinct()
    return pick.count

@register.filter(name='times') 
def times(number):
    return range(1, number+1)

@register.filter
def lookweekwinner(weekno):
    gameseason=get_season()
    winner_object = "week_{}_winner".format(weekno)
    week_winner = userSeasonPoints.objects.filter(**{winner_object: True},gameseason=gameseason).distinct() 
    return week_winner

@register.filter
def lookupStats(user_id):
    stats = userStats.objects.filter(userID=user_id).first()

    weeksWonSeason = stats.weeksWonSeason if stats else '0'
    weeksWonTotal = stats.weeksWonTotal if stats else '0'
    pickPercentSeason = stats.pickPercentSeason if stats else '0'
    pickPercentTotal = stats.pickPercentTotal if stats else '0'
    correctPickTotalSeason = stats.correctPickTotalSeason if stats else '0'
    correctPickTotalTotal = stats.correctPickTotalTotal if stats else '0'
    totalPicksSeason = stats.totalPicksSeason if stats else '0'
    totalPicksTotal = stats.totalPicksTotal if stats else '0'
    mostPickedSeason = stats.mostPickedSeason if stats else None
    mostPickedTotal = stats.mostPickedTotal if stats else None
    leastPickedSeason = stats.leastPickedSeason if stats else None
    leastPickedTotal = stats.leastPickedTotal if stats else None
    seasonsWon = stats.seasonsWon if stats else None


    data = {
        'weeksWonSeason': weeksWonSeason,
        'weeksWonTotal': weeksWonTotal,
        'pickPercentSeason': pickPercentSeason,
        'pickPercentTotal': pickPercentTotal,
        'correctPickTotalSeason': correctPickTotalSeason,
        'correctPickTotalTotal': correctPickTotalTotal,
        'totalPicksSeason': totalPicksSeason,
        'totalPicksTotal': totalPicksTotal,
        'mostPickedSeason': mostPickedSeason,
        'mostPickedTotal': mostPickedTotal,
        'leastPickedSeason': leastPickedSeason,
        'leastPickedTotal': leastPickedTotal,
        'seasonsWon': seasonsWon,
    }

    return data
