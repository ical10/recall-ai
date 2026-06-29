import { createRoute, redirect } from "@tanstack/react-router";
import { rootRoute } from "./__root";

export const dashboardRedirectRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/dashboard",
  beforeLoad: () => {
    throw redirect({ to: "/" });
  },
});
