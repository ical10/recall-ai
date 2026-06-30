import { createRootRoute, Outlet } from "@tanstack/react-router";
import { Nav } from "@/components/Nav";

export const rootRoute = createRootRoute({
  component: () => (
    <>
      <Nav />
      <Outlet />
    </>
  ),
});
