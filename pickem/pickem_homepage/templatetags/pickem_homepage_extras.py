from django import template
from django.contrib.auth.models import User
from pickem_api.models import Teams, GamePicks

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
def lookuplogo(slug):
    logo = Teams.objects.get(teamNameSlug=slug)
    return logo

@register.filter
def lookuppick(id):
    pick = GamePicks.objects.filter(id=id).distinct()
    return pick.count
