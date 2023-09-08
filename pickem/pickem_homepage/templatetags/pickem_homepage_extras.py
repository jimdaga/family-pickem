from django import template
from django.contrib.auth.models import User
from pickem_api.models import Teams, GamePicks
from django.shortcuts import render
from allauth.socialaccount.models import SocialAccount

register = template.Library()

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
    logo = Teams.objects.get(teamNameSlug=slug)
    return logo

@register.filter
def lookuppick(id):
    pick = GamePicks.objects.filter(id=id).distinct()
    return pick.count

@register.filter(name='times') 
def times(number):
    return range(1, number+1)