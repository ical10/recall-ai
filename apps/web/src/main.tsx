import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "./router";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RouterProvider />
  </StrictMode>,
);
