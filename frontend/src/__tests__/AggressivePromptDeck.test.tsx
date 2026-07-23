import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AggressivePromptDeck } from "../components/AggressivePromptDeck";
import { AGGRESSIVE_PROMPTS } from "../lib/aggressivePrompts";

describe("AggressivePromptDeck", () => {
  it("renders the first page of aggressive prompts", () => {
    render(<AggressivePromptDeck onSelect={vi.fn()} />);
    expect(screen.getByText(/Strike library/i)).toBeInTheDocument();
    for (const prompt of AGGRESSIVE_PROMPTS.slice(0, 6)) {
      expect(screen.getByText(prompt.title)).toBeInTheDocument();
    }
    expect(screen.queryByText(AGGRESSIVE_PROMPTS[6]?.title ?? "")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Strike library pagination")).toBeInTheDocument();
  });

  it("filters by tactic tab in host mode", () => {
    render(<AggressivePromptDeck onSelect={vi.fn()} />);
    fireEvent.click(screen.getByRole("tab", { name: /Host strikes/i }));
    fireEvent.click(screen.getByRole("tab", { name: /Web assault/i }));
    expect(screen.getByText("Web kill chain")).toBeInTheDocument();
    expect(screen.queryByText("Email exposure hunt")).not.toBeInTheDocument();
  });

  it("shows OSINT target tabs in OSINT mode", () => {
    render(<AggressivePromptDeck onSelect={vi.fn()} />);
    fireEvent.click(screen.getByRole("tab", { name: /OSINT by target/i }));
    expect(screen.getByRole("tab", { name: /Email address/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: /Email address/i }));
    expect(screen.getByText("Email exposure hunt")).toBeInTheDocument();
    expect(screen.queryByText("Complete dark arsenal")).not.toBeInTheDocument();
  });

  it("fires onSelect with the full prompt card", () => {
    const onSelect = vi.fn();
    render(<AggressivePromptDeck onSelect={onSelect} />);
    fireEvent.click(screen.getByText("Username OSINT sweep"));
    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({ id: "osint-username", targetProfile: "username" }),
    );
  });
});
