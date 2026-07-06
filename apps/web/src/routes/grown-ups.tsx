import { createRoute } from "@tanstack/react-router";
import { rootRoute } from "./__root";
import { GrownUpsPage } from "@/components/GrownUpsPage";

export const grownUpsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/grown-ups",
  component: GrownUpsPage,
});
