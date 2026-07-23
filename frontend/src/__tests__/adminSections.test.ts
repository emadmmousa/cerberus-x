import { describe, expect, it } from "vitest";
import {
  ADMIN_SECTIONS,
  adminPageTitle,
  adminSectionsByGroup,
  isAdminSectionId,
} from "../lib/adminSections";

describe("adminSections", () => {
  it("lists all settings areas", () => {
    expect(ADMIN_SECTIONS.length).toBe(9);
    expect(isAdminSectionId("ops")).toBe(true);
    expect(isAdminSectionId("nope")).toBe(false);
  });

  it("groups sections for navigation", () => {
    const groups = adminSectionsByGroup();
    expect(groups).toHaveLength(3);
    expect(groups.flatMap((g) => g.sections)).toHaveLength(9);
  });

  it("maps routes to page titles", () => {
    expect(adminPageTitle()).toBe("Administration");
    expect(adminPageTitle("users")).toBe("Users");
    expect(adminPageTitle("rbac")).toBe("Access Guard");
    expect(adminPageTitle("logs")).toBe("Audit");
  });
});
