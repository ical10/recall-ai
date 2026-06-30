import { createRoute } from "@tanstack/react-router";
import { rootRoute } from "./__root";
import { AboutPage } from "@/components/AboutPage";

export const aboutRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/about",
  component: AboutPage,
});
