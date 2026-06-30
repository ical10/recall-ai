import { createRoute } from "@tanstack/react-router";
import { rootRoute } from "./__root";
import { Dashboard } from "@/components/Dashboard";

export const dashboardRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/dashboard",
  component: Dashboard,
});
