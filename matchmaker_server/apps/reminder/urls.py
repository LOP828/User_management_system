from django.urls import path

from apps.reminder.views import ReminderListView, ReminderProcessView


urlpatterns = [
    path("", ReminderListView.as_view(), name="reminder-list"),
    path("<int:pk>/process/", ReminderProcessView.as_view(), name="reminder-process"),
]
