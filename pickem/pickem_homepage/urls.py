from django.urls import path, re_path, include
from django.contrib.auth.views import LogoutView
from . import views

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.index, name='index'),
    path('scores/', views.scores, name='scores'),
    path('standings/', views.standings, name='standings'),
    path('rules/', views.rules, name='rules'),
    path('accounts/', include('allauth.urls')),
    path('logout', LogoutView.as_view()),
    re_path(r'^scores/competition/(?P<competition>[0-9]+)/season/(?P<gameseason>[0-9]+)/week/(?P<week>[0-9]+)$', views.scores_long, name='scores_long'),
    path('picks/', views.submit_game_picks, name='game_picks'),
]
