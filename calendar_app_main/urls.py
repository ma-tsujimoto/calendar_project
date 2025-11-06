from django.urls import path
from . import views

app_name = 'calendar_app_main'  # アプリの名前空間

urlpatterns = [
    # --- イベント関連 ---
    path('event/<str:event_id>/', views.event_detail, name='event_detail'),
    path('event/<str:event_id>/edit/', views.edit_event, name='edit_event'),
    path('event/<str:event_id>/delete/', views.delete_event, name='delete_event'),

    # --- イベント追加 ---
    path('add/<str:year>/<str:month>/<str:day>/', views.add_event, name='add_event'),

    # --- カレンダー表示 ---
    path('<str:year>/<str:month>/', views.calendar_view, name='calendar_by_month'),
    path('', views.calendar_view, name='calendar_home'),

    path('<int:year>/<int:month>/', views.calendar_view, name='calendar_by_month'),
    path("<str:year>/<str:month>/<str:day>/", views.calendar_by_day, name="calendar_by_day"),  # ← 日表示
]
