from django.urls import path

from apps.reminder.views import ReminderListView


urlpatterns = [
    path("", ReminderListView.as_view(), name="reminder-list"),
]
