import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../../test/utils";
import { server } from "../../test/server";
import { escherichiaClade } from "../../test/fixtures/clade";
import { taxprofilerProfile } from "../../test/fixtures/samples";
import CladeSection from "./CladeSection";

const API = "*/api/v1";

function withClassifiers(...names: string[]) {
  server.use(
    http.get(`${API}/samples/:sampleId/profile`, () =>
      HttpResponse.json({ profiles: names.map((n) => taxprofilerProfile(n)) })
    )
  );
}

function recordCladeRequests(): string[] {
  const seen: string[] = [];
  server.use(
    http.get(`${API}/samples/:sampleId/clade`, ({ request }) => {
      const classifier = new URL(request.url).searchParams.get("classifier") ?? "";
      seen.push(classifier);
      return HttpResponse.json({ ...escherichiaClade(), classifier });
    })
  );
  return seen;
}

describe("CladeSection", () => {
  it("renders the tree and explains that it opened at the genus", async () => {
    withClassifiers("kraken2");

    renderWithProviders(<CladeSection sampleOid="oid-1" taxonId={83334} />);

    expect(
      await screen.findByText("Escherichia coli O157:H7", { selector: "td span" })
    ).toBeVisible();
    expect(screen.getByText(/opened at the genus of/)).toBeInTheDocument();
  });

  it("starts on the classifier active in the taxonomy table", async () => {
    withClassifiers("kraken2", "centrifuge");
    const requested = recordCladeRequests();

    renderWithProviders(
      <CladeSection sampleOid="oid-1" taxonId={83334} initialClassifier="centrifuge" />
    );

    await waitFor(() => expect(requested).toEqual(["centrifuge"]));
    expect(screen.getByRole("button", { name: "centrifuge" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
  });

  it("loads another classifier when its tab is clicked", async () => {
    withClassifiers("kraken2", "centrifuge");
    const requested = recordCladeRequests();
    renderWithProviders(<CladeSection sampleOid="oid-1" taxonId={83334} />);
    await waitFor(() => expect(requested).toEqual(["kraken2"]));

    await userEvent.click(screen.getByRole("button", { name: "centrifuge" }));

    await waitFor(() => expect(requested).toEqual(["kraken2", "centrifuge"]));
  });

  it("shows the backend's explanation when the taxonomy needs reloading", async () => {
    withClassifiers("kraken2");
    server.use(
      http.get(`${API}/samples/:sampleId/clade`, () =>
        HttpResponse.json(
          { detail: "The taxonomy reference predates lineage support." },
          { status: 409 }
        )
      )
    );

    renderWithProviders(<CladeSection sampleOid="oid-1" taxonId={83334} />);

    expect(
      await screen.findByText("The taxonomy reference predates lineage support.")
    ).toBeInTheDocument();
  });

  it("lists taxa that could not be placed", async () => {
    withClassifiers("kraken2");
    server.use(
      http.get(`${API}/samples/:sampleId/clade`, () =>
        HttpResponse.json({
          ...escherichiaClade(),
          unplaced: [
            {
              taxon_id: 99,
              name: "gone",
              reason: "deleted",
              merged_from: [],
              cells: { S1: { direct: 4, clade: 4, direct_rpm: null, clade_rpm: null } },
            },
          ],
        })
      )
    );
    renderWithProviders(<CladeSection sampleOid="oid-1" taxonId={83334} />);

    await userEvent.click(await screen.findByRole("button", { name: /could not be placed/ }));

    expect(screen.getByText("deleted by NCBI")).toBeInTheDocument();
  });

  it("says so when the sample has no classifier profiles", async () => {
    renderWithProviders(<CladeSection sampleOid="oid-1" taxonId={83334} />);

    expect(await screen.findByText("This sample has no classifier profiles.")).toBeVisible();
  });
});
