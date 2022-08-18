from django.http import HttpResponse
from django.shortcuts import render, get_list_or_404
from .models import GamesAndScores
from django.core import serializers

# Create your views here.
def index(request):
    return HttpResponse("Family Pickem API.")

def getAllGames(request):
    games = serializers.serialize("json", GamesAndScores.objects.all())
    return HttpResponse(games,content_type="application/json")