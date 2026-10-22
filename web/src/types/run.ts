/* Generated from run.schema.json by npm run gen:types. Do not edit. */

export type SchemaVersion = 1;
export type Id = string;
export type Status = "ok" | "partial" | "failed";
export type StartedAt = string;
export type FinishedAt = string;
export type WindowStart = string;
export type GitSha = string | null;
export type Fetched = number;
/**
 * Items read from the hourly RSS collector's buffer
 */
export type FromBuffer = number;
export type AfterDedupe = number;
export type InWindow = number;
export type Id1 = string;
export type Name = string;
export type Tier = "A" | "B" | "C";
export type Group = string;
export type Status1 = "ok" | "stale" | "failed" | "disabled";
export type LastSuccess = string | null;
export type LastError = string | null;
export type Items = number;
export type HttpStatus = number | null;
export type Error = string | null;
export type Note = string | null;
export type Sources = SourceHealth[];
/**
 * sha1 of the canonical URL
 */
export type Id2 = string;
export type SourceId = string;
export type Tier1 = "A" | "B" | "C";
export type Url = string;
export type Title = string;
export type Lang = string;
export type PublishedAt = string;
/**
 * True when the source gave no date; published_at is then when the item was first seen
 */
export type PublishedEstimated = boolean;
export type FetchedAt = string;
export type Snippet = string;
export type Domain = string;
export type AlsoReportedBy = string[];
export type Tone = number | null;
export type Themes = string[];
export type Items1 = Item[];

export interface Run {
  schema_version: SchemaVersion;
  run: RunInfo;
  sources: Sources;
  items: Items1;
}
export interface RunInfo {
  id: Id;
  status: Status;
  started_at: StartedAt;
  finished_at: FinishedAt;
  window_start: WindowStart;
  git_sha: GitSha;
  counts: RunCounts;
}
export interface RunCounts {
  fetched: Fetched;
  from_buffer: FromBuffer;
  after_dedupe: AfterDedupe;
  in_window: InWindow;
}
export interface SourceHealth {
  id: Id1;
  name: Name;
  tier: Tier;
  group: Group;
  status: Status1;
  last_success: LastSuccess;
  last_error: LastError;
  items: Items;
  http_status: HttpStatus;
  error: Error;
  note: Note;
}
export interface Item {
  id: Id2;
  source_id: SourceId;
  tier: Tier1;
  url: Url;
  title: Title;
  lang: Lang;
  published_at: PublishedAt;
  published_estimated: PublishedEstimated;
  fetched_at: FetchedAt;
  snippet: Snippet;
  domain: Domain;
  also_reported_by: AlsoReportedBy;
  gdelt: GdeltInfo | null;
}
export interface GdeltInfo {
  tone: Tone;
  themes: Themes;
}
