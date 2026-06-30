import { createRoute } from "@tanstack/react-router";
import { rootRoute } from "./__root";
import { ReviewPage } from "@/components/ReviewPage";

export const reviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/review",
  component: ReviewPage,
});
