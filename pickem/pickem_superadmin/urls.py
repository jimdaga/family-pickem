from django.urls import path

from pickem_superadmin import views

app_name = 'superadmin'

urlpatterns = [
    path('', views.overview, name='overview'),
    path('users/', views.users, name='users'),
    path('users/<int:user_id>/block/', views.user_block, name='user_block'),
    path('users/<int:user_id>/unblock/', views.user_unblock, name='user_unblock'),
    path('users/<int:user_id>/update/', views.user_update, name='user_update'),
    path('pools/', views.pools, name='pools'),
    path('pools/save/', views.pools_save, name='pools_save'),
    path('families/', views.families, name='families'),
    path('families/save/', views.families_save, name='families_save'),
    path('teams/', views.teams, name='teams'),
    path('teams/save/', views.teams_save, name='teams_save'),
    path('jobs/', views.jobs_page, name='jobs'),
    path('jobs/queue/', views.jobs_queue, name='jobs_queue'),
    path('jobs/schedule/save/', views.jobs_schedule_save, name='jobs_schedule_save'),
    path('season/update/', views.season_update, name='season_update'),
    path('pools/<int:pool_id>/backfill-settings/', views.pool_settings_backfill, name='pool_settings_backfill'),
    path('banners/publish/', views.banner_publish, name='banner_publish'),
    path('banners/<int:banner_id>/deactivate/', views.banner_deactivate, name='banner_deactivate'),
    path('audit/', views.audit, name='audit'),
    path('pools/<int:pool_id>/detail/', views.pool_detail, name='pool_detail'),
    path('pools/<int:pool_id>/recompute/', views.pool_recompute, name='pool_recompute'),
    path('pools/<int:pool_id>/rescore-week/', views.pool_rescore_week, name='pool_rescore_week'),
    path('picks/<str:pick_id>/delete/', views.pick_delete, name='pick_delete'),
    path('season-rows/<int:row_id>/reset/', views.season_row_reset, name='season_row_reset'),
    path('games/<int:game_id>/fix/', views.game_fix, name='game_fix'),
]
