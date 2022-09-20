from django import template
from django.contrib.auth.models import User

register = template.Library()

@register.filter
def addstr(arg1, arg2):
    """concatenate arg1 & arg2"""
    return str(arg1) + str(arg2)

@register.filter
def lookupname(id):
    user = User.objects.get(id=id)
    return user