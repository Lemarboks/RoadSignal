export type MapCell = {
  type: "Feature";
  id: string;
  geometry: { type: "Polygon"; coordinates: number[][][] };
  properties: {
    cell_id: string;
    resolution: number;
    incident_count: number;
    max_severity: number;
    average_confidence: number;
    latest_occurred_at: string;
    provenance: "demo" | "reported" | "mixed" | "unknown";
    demo_incident_count: number;
  };
};
export type MapCells = {
  type: "FeatureCollection";
  features: MapCell[];
  metadata: {
    resolution: number; generated_at: string; incident_count: number; cell_count: number;
    provenance: "demo" | "reported" | "mixed" | "unknown";
    source: "active_incident_reports"; includes_expired: false;
  };
};
export type MapCellsState = { data: MapCells | null; status: "loading" | "ready" | "unavailable" };
export function cellProvenance(value: MapCell["properties"]["provenance"]) {
  return { demo: "Demonstration reports", reported: "Submitted reports", mixed: "Demonstration and submitted reports", unknown: "Report origin unknown" }[value];
}
