from django.urls import include, path
from . import views

urlpatterns = [
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    path('games/', views.getGames, name='games'),
    path('games/add/', views.addGame, name='add_games'),
    path('', views.index, name='index'),
]