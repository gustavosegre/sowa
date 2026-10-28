import type { components } from "./generated/schema";

type S = components["schemas"];

export type Pipeline = S["Pipeline"];
export type PipelineNode = S["Node"];
export type PipelineEdge = S["Edge"];
export type NodeUI = S["NodeUI"];
export type Column = S["Column"];
export type LogicalType = S["LogicalType"];
export type Issue = S["Issue"];
export type NodeAnalysis = S["NodeAnalysisOut"];
export type SchemaResponse = S["SchemaResponse"];
export type StatsOut = S["StatsOut"];
export type ProfileOut = S["ProfileOut"];
export type Project = S["ProjectOut"];
export type SavedPipeline = S["SavedPipeline"];
export type Source = S["SourceOut"];
export type Detection = S["Detection"];
export type ImportOptions = S["ImportOptions"];
export type ColumnPlan = S["ColumnPlan"];
export type ColumnGuess = S["ColumnGuess"];
export type ImportReport = S["ImportReport"];
export type UploadOut = S["UploadOut"];
export type ConfirmOut = S["ConfirmOut"];
export type ExportJob = S["ExportJobOut"];
export type FunctionInfo = S["FunctionOut"];
export type FormulaCheck = S["FormulaCheckOut"];
export type ApiErrorBody = S["ApiError"];

// Node configs (published in OpenAPI by the backend registry).
export type SourceConfig = S["SourceConfig"];
export type SelectConfig = S["SelectConfig"];
export type CastConfig = S["CastConfig"];
export type CastRule = S["CastRule"];
export type CalculatedConfig = S["CalculatedConfig"];
export type FilterConfig = S["FilterConfig"];
export type Condition = S["Condition"];
export type ConditionGroup = S["ConditionGroup"];
export type SortConfig = S["SortConfig"];
export type SortKey = S["SortKey"];
export type GroupByConfig = S["GroupByConfig"];
export type Aggregation = S["Aggregation"];
export type Measure = S["Measure"];
export type OutputConfig = S["OutputConfig"];
export type NoteConfig = S["NoteConfig"];
export type FrameConfig = S["FrameConfig"];

export type NodeStatus = NodeAnalysis["status"];
