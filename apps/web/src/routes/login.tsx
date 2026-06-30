import { createRoute } from "@tanstack/react-router";
import { rootRoute } from "./__root";
import { LoginPage } from "@/components/LoginPage";

export const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/login",
  component: LoginPage,
});
