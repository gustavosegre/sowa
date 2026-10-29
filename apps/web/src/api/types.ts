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
export type AuthStatus = S["AuthStatus"];

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

// Phase 2 nodes.
export type DistinctConfig = S["DistinctConfig"];
export type SampleNodeConfig = S["SampleNodeConfig"];
export type TextCleanConfig = S["TextCleanConfig"];
export type ReplaceConfig = S["ReplaceConfig"];
export type ReplaceRule = S["ReplaceRule"];
export type FillNullConfig = S["FillNullConfig"];
export type FillRule = S["FillRule"];
export type DatePartsConfig = S["DatePartsConfig"];
export type BinConfig = S["BinConfig"];
export type SplitConfig = S["SplitConfig"];
export type ConditionalConfig = S["ConditionalConfig"];
export type ConditionalRule = S["ConditionalRule"];
export type Outcome = S["Outcome"];
export type UnpivotConfig = S["UnpivotConfig"];
export type WindowConfig = S["WindowConfig"];
export type WindowItem = S["WindowItem"];
export type PivotConfig = S["PivotConfig"];
export type PivotField = S["PivotField"];
export type PivotValue = S["PivotValue"];
export type JoinConfig = S["JoinConfig"];
export type JoinKey = S["JoinKey"];
export type UnionConfig = S["UnionConfig"];
export type LookupConfig = S["LookupConfig"];
export type LookupKey = S["LookupKey"];

// Phase 3.
export type SqlConfig = S["SqlConfig"];

// Templates and sub-flows (Phase 3).
export type Flow = S["Flow"];
export type FlowInput = S["FlowInput"];
export type SubflowConfig = S["SubflowConfig"];
export type Template = S["TemplateOut"];
export type TemplateDetail = S["TemplateDetail"];
export type Parameter = S["Parameter"];
export type VersionOut = S["VersionOut"];
export type VersionDetail = S["VersionDetail"];
