import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import App from "../App";
import fixtures from "./fixtures.json";

const reply = (data: unknown, ok = true, status = 200) =>
  Promise.resolve({
    ok,
    status,
    json: () => Promise.resolve(data),
  } as Response);
function server({
  live = false,
  review,
}: { live?: boolean; review?: (init: RequestInit) => Promise<Response> } = {}) {
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    if (url === "/api/cases") return reply(fixtures.cases);
    if (url === "/api/config")
      return reply({
        live_available: live,
        max_file_bytes: 10485760,
        max_claims: 15,
        max_disclosure_chars: 35000,
      });
    if (url === "/api/reviews" && init)
      return review ? review(init) : reply(fixtures.results.A);
    return reply({ detail: "Not found" }, false, 404);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}
async function setup(options = {}) {
  const fetchMock = server(options);
  const user = userEvent.setup();
  render(<App />);
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Compare & screen" }),
    ).toBeEnabled(),
  );
  return { user, fetchMock };
}

describe("review workspace", () => {
  it("runs an offline review, filters results, and opens the exact source passage", async () => {
    const { user } = await setup();
    expect(screen.getByRole("button", { name: /Live AI/ })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Compare & screen" }));
    expect(await screen.findByText("3 claims reviewed")).toBeInTheDocument();
    expect(screen.getAllByRole("article")).toHaveLength(3);
    await user.click(screen.getByRole("button", { name: "0 Supported" }));
    expect(screen.getByText("No claims in this category.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "View all findings" }));
    const first = screen.getAllByRole("article")[0];
    await user.click(within(first).getByRole("button", { name: /D0002/ }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("Full source passage")).toBeInTheDocument();
    expect(
      within(dialog).getByText(fixtures.results.A.sources.disclosure[1].text),
    ).toBeInTheDocument();
    await user.click(
      within(dialog).getByRole("button", { name: "Close source inspector" }),
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await user.click(within(first).getByText("Regulatory assessment"));
    expect(
      within(first).getByText(/Candidate passages only/),
    ).toBeInTheDocument();
  });

  it("clears results on case change and loads the newly selected source inputs", async () => {
    const { user } = await setup();
    await user.click(screen.getByRole("button", { name: "Compare & screen" }));
    await screen.findByText("3 claims reviewed");
    await user.selectOptions(screen.getByLabelText(/Start with a case/), "C");
    expect(screen.queryByText("3 claims reviewed")).not.toBeInTheDocument();
    expect(
      screen.getByText("A fresh look at your changes."),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Environmental claims")).toHaveValue(
      fixtures.cases[2].claims.join("\n"),
    );
    expect(
      screen.queryByRole("button", { name: "Export JSON" }),
    ).not.toBeInTheDocument();
  });

  it("does not display a late response after the user edits the inputs", async () => {
    let resolve!: (value: Response) => void;
    const delayed = new Promise<Response>((r) => {
      resolve = r;
    });
    const { user } = await setup({ review: () => delayed });
    await user.click(screen.getByRole("button", { name: "Compare & screen" }));
    expect(screen.getByText("Following the evidence.")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Environmental claims"), " edited");
    await act(async () => {
      resolve(await reply(fixtures.results.A));
    });
    expect(screen.queryByText("3 claims reviewed")).not.toBeInTheDocument();
    expect(
      screen.getByText("A fresh look at your changes."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Compare & screen" }),
    ).toBeEnabled();
  });

  it("requires an upload and submits the selected file and version label", async () => {
    const { user, fetchMock } = await setup();
    await user.selectOptions(
      screen.getByLabelText("Regulatory reference"),
      "upload",
    );
    await user.click(screen.getByRole("button", { name: "Compare & screen" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Choose a regulation file first.",
    );
    const file = new File(
      ["Article 99. Evidence must be supplied."],
      "regulation.txt",
      { type: "text/plain" },
    );
    await user.upload(screen.getByLabelText(/Choose a regulation file/), file);
    await user.type(screen.getByLabelText("Version label"), "v2");
    await user.click(screen.getByRole("button", { name: "Compare & screen" }));
    await screen.findByText("3 claims reviewed");
    const call = fetchMock.mock.calls.find(([url]) => url === "/api/reviews");
    const body = call?.[1]?.body as FormData;
    expect(body.get("regulation_file")).toBe(file);
    expect(body.get("version")).toBe("v2");
    expect(body.get("regulation_source")).toBe("upload");
  });

  it("shows server errors and permits a retry without displaying fixture results", async () => {
    let failed = true;
    const { user } = await setup({
      review: () =>
        failed
          ? reply({ detail: "Model request timed out." }, false, 422)
          : reply(fixtures.results.A),
    });
    await user.click(screen.getByRole("button", { name: "Compare & screen" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Model request timed out.",
    );
    expect(screen.queryByRole("article")).not.toBeInTheDocument();
    failed = false;
    await user.click(screen.getByRole("button", { name: "Compare & screen" }));
    expect(await screen.findByText("3 claims reviewed")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("sends Live AI mode only when configured and distinguishes its result", async () => {
    const response = structuredClone(fixtures.results.A);
    response.report.mode = "Live AI";
    const { user, fetchMock } = await setup({
      live: true,
      review: () => reply(response),
    });
    await user.click(screen.getByRole("button", { name: "Live AI" }));
    await user.click(screen.getByRole("button", { name: "Compare & screen" }));
    expect(await screen.findByText("Live AI analysis")).toBeInTheDocument();
    expect(screen.queryByText("Offline demonstration")).not.toBeInTheDocument();
    const body = fetchMock.mock.calls.find(
      ([url]) => url === "/api/reviews",
    )?.[1]?.body as FormData;
    expect(body.get("mode")).toBe("Live AI");
    expect(body.has("api_key")).toBe(false);
  });

  it("exports only the report JSON and explains the actual baseline method", async () => {
    const create = vi.fn((_blob: Blob) => "blob:test-export");
    URL.createObjectURL = create;
    URL.revokeObjectURL = vi.fn();
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => {});
    const { user } = await setup();
    await user.click(screen.getByRole("button", { name: "How it works" }));
    expect(screen.getByRole("dialog")).toHaveTextContent(
      "No vector search is used.",
    );
    await user.click(screen.getByRole("button", { name: "Close explanation" }));
    await user.click(screen.getByRole("button", { name: "Compare & screen" }));
    await user.click(
      await screen.findByRole("button", { name: "Export JSON" }),
    );
    expect(create).toHaveBeenCalledOnce();
    expect(click).toHaveBeenCalledOnce();
    expect(create.mock.calls[0][0]).toBeInstanceOf(Blob);
  });
});
