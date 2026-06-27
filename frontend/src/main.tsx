import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "./index.css";
import App from "./App.tsx";
import { NotesProvider } from "./context/NotesContext.tsx";
import { injectCssVars } from "./tokens";

injectCssVars();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <NotesProvider>
        <App />
      </NotesProvider>
    </BrowserRouter>
  </StrictMode>,
);
