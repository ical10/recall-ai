import { rootRoute } from "./routes/__root";
import { archiveRoute } from "./routes/archive";
import { dashboardRoute } from "./routes/dashboard";
import { dashboardRedirectRoute } from "./routes/dashboard-redirect";
import { reviewRoute } from "./routes/review";
import { settingsRoute } from "./routes/settings";

export const routeTree = rootRoute.addChildren([
  dashboardRoute,
  dashboardRedirectRoute,
  reviewRoute,
  settingsRoute,
  archiveRoute,
]);
