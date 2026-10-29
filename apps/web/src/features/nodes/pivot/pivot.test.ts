import { describe, expect, it } from "vitest";

import { pivotFieldName } from "./ConfigPanel";

describe("pivotFieldName", () => {
  // Must match the backend's nodes/pivot.py field_name: base_field is matched by this name.
  it("adds the date grouping like the generated table", () => {
    expect(pivotFieldName({ column: "uf", date_group: "none" })).toBe("uf");
    expect(pivotFieldName({ column: "data venda", date_group: "month" })).toBe("data venda (mês)");
    expect(pivotFieldName({ column: "data", date_group: "quarter" })).toBe("data (trimestre)");
  });
});
