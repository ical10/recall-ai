import { createRoute } from "@tanstack/react-router";
import { rootRoute } from "./__root";
import { SettingsPage } from "@/components/SettingsPage";

export const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings",
  component: SettingsPage,
});
