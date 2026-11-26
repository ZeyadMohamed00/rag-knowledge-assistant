import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { App } from "./App";

function mockFetch() {
  let docs: unknown[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const ok = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status });
    if (url.endsWith("/documents") && (!init || init.method === "GET" || !init.method)) return ok(docs);
    if (url.endsWith("/demo/seed")) { docs = [{ id: 1, filename: "sample-handbook.pdf", pages: 11, chunks: 20 }]; return ok({ seeded: true }, 201); }
    if (url.endsWith("/chats") && init?.method === "POST") return ok({ id: 7, title: "New chat" }, 201);
    if (url.endsWith("/chats")) return ok([]);
    if (url.includes("/ask")) return ok({ answer: "It returns 422. [1]", citations: [{ document: "sample-handbook.pdf", page: 3, snippet: "FastAPI" }], mode: "extractive" });
    return ok({});
  }));
}

test("demo load, ask, and see page citation", async () => {
  mockFetch();
  render(<App />);
  await userEvent.click(await screen.findByText(/Load sample documents/));
  await screen.findByText(/sample-handbook.pdf/);
  await userEvent.type(screen.getByLabelText("Question"), "status code?");
  await userEvent.click(screen.getByText("Ask"));
  await waitFor(() => expect(screen.getByText(/It returns 422/)).toBeInTheDocument());
  expect(screen.getByText(/sample-handbook.pdf, page 3/)).toBeInTheDocument();
});

test("ask disabled with no documents", async () => {
  mockFetch();
  render(<App />);
  await screen.findByText(/New here/);
  expect(screen.getByText("Ask")).toBeDisabled();
});
