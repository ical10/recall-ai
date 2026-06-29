import { rootRoute } from "./routes/__root";
import { aboutRoute } from "./routes/about";
import { archiveRoute } from "./routes/archive";
import { dashboardRoute } from "./routes/dashboard";
import { indexRoute } from "./routes/index";
import { loginRoute } from "./routes/login";
import { reviewRoute } from "./routes/review";
import { settingsRoute } from "./routes/settings";

export const routeTree = rootRoute.addChildren([
  indexRoute,
  dashboardRoute,
  loginRoute,
  aboutRoute,
  reviewRoute,
  settingsRoute,
  archiveRoute,
]);
