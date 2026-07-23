import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ChatMessageBody } from "../components/ChatMessageBody";

describe("ChatMessageBody", () => {
  it("collapses planning prose behind Thinking... in instant chat", () => {
    render(
      <ChatMessageBody
        collapseThinking
        content={"Understood.\n\n### Seed Identification:\n- Email: a@corp.com\n\n### Phase Plan:\n"}
      />,
    );

    expect(screen.getByText("Thinking...")).toBeInTheDocument();
    expect(document.querySelector(".agent-msg__content--brief")?.textContent).toContain(
      "Analysis complete",
    );
    expect(document.querySelector(".agent-fold__body")?.textContent).toContain("Seed Identification");
  });

  it("keeps the thinking fold open while streaming updates arrive", () => {
    const { rerender } = render(
      <ChatMessageBody collapseThinking streaming content="" />,
    );

    fireEvent.click(screen.getByText("Thinking..."));
    expect((screen.getByText("Thinking...").closest("details") as HTMLDetailsElement).open).toBe(true);

    rerender(
      <ChatMessageBody
        collapseThinking
        streaming
        content="### Seed Identification:\n- Email: a@corp.com"
      />,
    );

    expect((screen.getByText("Thinking...").closest("details") as HTMLDetailsElement).open).toBe(true);
    expect(document.querySelector(".agent-fold__body")?.textContent).toContain("a@corp.com");
  });

  it("keeps short answers visible while folding internals", () => {
    render(
      <ChatMessageBody
        collapseThinking
        content="OSINT sweep queued — running theharvester, darkweb, and breach_intel now."
      />,
    );

    expect(screen.getByText(/OSINT sweep queued/i)).toBeInTheDocument();
    expect(screen.queryByText("Thinking...")).not.toBeInTheDocument();
  });

  it("shows archived thinking content after the visible reply is sanitized", () => {
    render(
      <ChatMessageBody
        collapseThinking
        content="Mission live summary only."
        thinkingContent={"### Seed Identification:\n- Full Name: عبد الباسط\n\n### Phase Plan:\n"}
        briefContext={{ missionLaunched: true, target: "linkedin.com" }}
      />,
    );

    expect(screen.getByText(/Mission live summary only/i)).toBeInTheDocument();
    expect(document.querySelector(".agent-fold__body")?.textContent).toContain("Seed Identification");
  });

  it("hides an empty thinking fold after completion", () => {
    render(
      <ChatMessageBody collapseThinking content="Done." briefContext={{ missionLaunched: true, target: "x.com" }} />,
    );

    expect(screen.queryByText("Thinking...")).not.toBeInTheDocument();
  });
});
