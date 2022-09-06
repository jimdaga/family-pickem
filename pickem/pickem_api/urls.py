from django.urls import include, path, re_path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    re_path(r'^games/(?P<pk>[0-9]+)$', views.game_detail),
    re_path(r'^games', views.game_list),
    re_path(r'^weeks/(?P<date>\d{4}-\d{2}-\d{2})$', views.week_detail),
    re_path(r'^weeks', views.week_list),
    re_path(r'^unscored', views.games_unscored),
    re_path(r'^picks/(?P<pick_game_id>[0-9]+)$', views.game_picks),
]
