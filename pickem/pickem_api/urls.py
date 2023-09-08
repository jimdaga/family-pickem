from django.urls import include, path, re_path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),

    # GAMES
    re_path(r'^games/(?P<pk>[0-9]+)$', views.game_detail),
    re_path(r'^games', views.game_list),

    # USER DETAILS
    re_path(r'^userinfo/(?P<pk>[0-9]+)$', views.user_info),

    # WEEKS
    re_path(r'^weeks/(?P<date>\d{4}-\d{2}-\d{2})$', views.week_detail),
    re_path(r'^weeks', views.week_list),

    # PICKS
    re_path(
        r'^userpicks/(?P<game_season>[0-9]+)/(?P<game_week>[0-9]+)/(?P<uid>[0-9]+)$', views.correct_user_picks),
    re_path(
        r'^userpickids/(?P<game_season>[0-9]+)/(?P<game_week>[0-9]+)$', views.game_picks_week_all),
    re_path(r'^picks/(?P<pick_game_id>[0-9]+)$', views.game_picks),
    re_path(r'^userpicks/(?P<pick_id>[0-9]+-[0-9]+)$', views.user_picks),

    # TEAMS
    re_path(r'^teams/id/(?P<team_id>[0-9]+)$', views.get_teams_detail),
    re_path(r'^teams/', views.get_teams),

    # ACTIVE GAMES
    re_path(r'^activegames/', views.get_active_games),

    # UNSCORED GAMES
    re_path(r'^unscored', views.games_unscored),

    # USER POINT DETAIL
    re_path(r'^userpointsdel/(?P<game_season>[0-9]+)/(?P<id>[0-9]+)$', views.delete_user_record),
    re_path(r'^userpoints/(?P<game_season>[0-9]+)/(?P<id>[0-9]+)$', views.user_points),
    re_path(r'^userpoints/add', views.user_points_all),
    re_path(r'^userpoints/', views.user_points_all),
]
