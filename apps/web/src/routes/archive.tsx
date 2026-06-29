import { createRoute } from "@tanstack/react-router";
import { rootRoute } from "./__root";
import { ArchivePage } from "@/components/ArchivePage";

export const archiveRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/archive",
  component: ArchivePage,
});
