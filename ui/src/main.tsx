import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./temporal.css";
import App from "./TemporalApp.tsx";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
