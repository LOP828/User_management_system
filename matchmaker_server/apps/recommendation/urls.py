from django.urls import path

from apps.recommendation.views import (
    BatchCloseView,
    CandidateSelectView,
    RecommendationBatchListCreateView,
)

urlpatterns = [
    path("", RecommendationBatchListCreateView.as_view(), name="recommendation-batch-list-create"),
    path("candidates/<int:candidate_id>/select/", CandidateSelectView.as_view(), name="recommendation-candidate-select"),
    path("<int:batch_id>/close/", BatchCloseView.as_view(), name="recommendation-batch-close"),
]
