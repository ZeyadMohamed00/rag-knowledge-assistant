import { createRoot } from "react-dom/client";
import { App } from "./App";
import { AuthGate } from "./auth";
import "./styles.css";
createRoot(document.getElementById("root")!).render(<AuthGate title="Knowledge Assistant"><App /></AuthGate>);
