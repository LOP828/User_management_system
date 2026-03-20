import { createBrowserRouter, Navigate } from "react-router-dom";

import { AppLayout } from "../layouts/AppLayout";
import { MatchCardDetailPage } from "../pages/match-cards/MatchCardDetailPage";
import { DashboardPage } from "../pages/dashboard/DashboardPage";
import { ReminderPage } from "../pages/reminders/ReminderPage";
import { RecommendationPage } from "../pages/recommendations/RecommendationPage";
import { SuccessPage } from "../pages/success/SuccessPage";
import { TransferPage } from "../pages/transfers/TransferPage";
import { UserDetailPage } from "../pages/users/UserDetailPage";
import { UserListPage } from "../pages/users/UserListPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      {
        index: true,
        element: <Navigate to="/users" replace />
      },
      {
        path: "dashboard",
        element: <DashboardPage />
      },
      {
        path: "users",
        element: <UserListPage />
      },
      {
        path: "users/:id",
        element: <UserDetailPage />
      },
      {
        path: "recommendations",
        element: <RecommendationPage />
      },
      {
        path: "reminders",
        element: <ReminderPage />
      },
      {
        path: "success",
        element: <SuccessPage />
      },
      {
        path: "transfers",
        element: <TransferPage />
      },
      {
        path: "match-cards/:id",
        element: <MatchCardDetailPage />
      }
    ]
  }
]);
