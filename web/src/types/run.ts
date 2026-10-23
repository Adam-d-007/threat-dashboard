/* Generated from run.schema.json by npm run gen:types. Do not edit. */

/**
 * f(articles 24 h / 90-day median)
 */
export type Value = number | null;
export type Articles24H = number | null;
export type BaselineMedian = number | null;
export type Id = string;
/**
 * ISO 3166-1 alpha-2
 */
export type Country = string;
export type Name = string;
export type Url = string;
/**
 * Allowed raw values, lowest to highest
 */
export type Scale = string[];
/**
 * Value read from the page, one of scale
 */
export type Raw = string | null;
/**
 * 1-based position of raw on scale
 */
export type Level = number | null;
/**
 * (level - 1) / (len(scale) - 1)
 */
export type Normalized = number | null;
/**
 * Date the level was declared, if stated
 */
export type Since = string | null;
/**
 * Last time the value was read successfully
 */
export type AsOf = string | null;
export type Status = "ok" | "stale" | "failed" | "disabled";
export type Error = string | null;
/**
 * sha1 of the paragraph stating the level, to detect any change in wording
 */
export type TextHash = string | null;
/**
 * Other levels in force at the same time, e.g. a higher level for railways only
 */
export type Detail = string | null;
/**
 * Typed in by hand from the official page, because the page cannot be read automatically
 */
export type Manual = boolean;
/**
 * national: a country's own threat level; travel: another government's travel advice for this country
 */
export type Kind = "national" | "travel";
/**
 * ISO alpha-2 of the government that issues the travel advice (travel only)
 */
export type Issuer = string | null;
export type Status1 = "ok" | "fallback" | "disabled";
export type TextEn = string;
export type TextSk = string | null;
export type ItemIds = string[];
export type Lines = BriefLine[];
export type WhatChangedEn = string | null;
export type WhatChangedSk = string | null;
export type Status2 = "llm" | "rules" | "unclassified";
export type Relevant = boolean;
export type Domain = "terrorism" | "hybrid" | "cyber" | "unrest" | "geopolitics" | "other";
export type EventType =
  | "attack"
  | "attempted_attack"
  | "plot_disrupted"
  | "arrest"
  | "conviction"
  | "threat_statement"
  | "sabotage"
  | "other";
export type Ideology =
  "jihadist" | "right_wing" | "left_anarchist" | "ethno_separatist" | "state_linked" | "other" | "unknown";
/**
 * 0 not an incident, 1 arrest or disrupted plot, 2 attempted attack, 3 attack without deaths, 4 attack with 1 to 4 deaths, 5 attack with 5 or more deaths
 */
export type Severity = number;
export type SkLink = "none" | "indirect" | "direct";
/**
 * ISO 3166-1 alpha-2
 */
export type Countries = string[];
export type Name1 = string;
export type Lat = number;
export type Lon = number;
export type Precision = "city" | "region" | "country";
export type Places = Place[];
export type EventKey = string | null;
export type SummaryEn = string | null;
export type SummarySk = string | null;
export type Confidence = number | null;
export type Id1 = "events" | "media" | "anchors" | "llm";
export type Weight = number;
export type Value1 = number | null;
export type EventIds = string[];
export type NewEventIds = string[];
export type Region = "SK" | "EU";
export type LevelFrom = number | null;
export type LevelTo = number;
export type LevelChanges = LevelChange[];
export type Id2 = string;
export type ValueFrom = string | null;
export type ValueTo = string | null;
export type AnchorChanges = ValueChange[];
export type SourceChanges = ValueChange[];
export type TextEn1 = string;
export type TextSk1 = string | null;
export type EventIds1 = string[];
export type Id3 = string;
export type TitleEn = string;
export type TitleSk = string | null;
export type EventType1 =
  | "attack"
  | "attempted_attack"
  | "plot_disrupted"
  | "arrest"
  | "conviction"
  | "threat_statement"
  | "sabotage"
  | "other";
export type Ideology1 =
  "jihadist" | "right_wing" | "left_anarchist" | "ethno_separatist" | "state_linked" | "other" | "unknown";
export type Severity1 = number;
export type Date = string;
export type Country1 = string;
export type SkLink1 = "none" | "indirect" | "direct";
/**
 * terrorism when any report calls it that, else the first report's domain; None on events stored before 2026-10-23
 */
export type Topic = ("terrorism" | "hybrid" | "cyber" | "unrest" | "geopolitics" | "other") | null;
export type ItemIds1 = string[];
/**
 * LLM incident keys seen
 */
export type EventKeys = string[];
export type Domains = string[];
export type HasTierA = boolean;
/**
 * Highest tier among its sources
 */
export type BestTier = ("A" | "B" | "C") | null;
export type Corroborated = boolean;
export type FirstSeen = string;
export type LastUpdated = string;
export type Id4 = string;
export type Effect = string;
export type EventIds2 = string[];
export type Tone = number | null;
export type Themes = string[];
export type Id5 = string;
export type NameEn = string;
export type NameSk = string;
/**
 * ISO 3166-1 alpha-2, EU expanded to its member states; the map places a report in this theatre when it names one of them
 */
export type Countries1 = string[];
export type Value2 = number;
export type BaselineMedian1 = number;
/**
 * Activity value per day, oldest first, up to 30 days
 */
export type Sparkline = number[];
export type ItemId = string;
export type SummaryEn1 = string;
export type SummarySk1 = string | null;
export type TopItems = TopItem[];
export type SkAngleEn = string | null;
export type SkAngleSk = string | null;
export type Theatres = Theatre[];
export type Date1 = string;
export type TitleEn1 = string;
export type TitleSk1 = string | null;
export type Origin = "manual" | "news";
export type Verified = boolean;
export type Url1 = string | null;
export type Watchlist = WatchlistEntry[];
export type Source = string;
export type DataEnds = number;
export type Generated = string;
export type Year = number;
/**
 * None for a year the GTD has no data for (1993)
 */
export type Incidents = number | null;
export type Deaths = number | null;
export type Sk = GtdYear[];
export type Eu = GtdYear[];
/**
 * sha1 of the canonical URL
 */
export type Id6 = string;
export type SourceId = string;
export type Tier = "A" | "B" | "C";
export type Url2 = string;
export type Title = string;
export type Lang = string;
export type PublishedAt = string;
/**
 * True when the source gave no date; published_at is then when the item was first seen
 */
export type PublishedEstimated = boolean;
export type FetchedAt = string;
export type Snippet = string;
export type Domain1 = string;
export type AlsoReportedBy = string[];
export type EventId = string | null;
export type Status3 = "ok" | "fallback" | "disabled";
export type Level1 = (1 | 2 | 3 | 4) | null;
export type Position = ("low" | "mid" | "high") | null;
export type Confidence1 = ("low" | "medium" | "high") | null;
export type Drivers = Driver[];
export type WhatChangedEn1 = string | null;
export type WhatChangedSk1 = string | null;
export type Model = string | null;
export type Status4 = "ok" | "fallback" | "disabled";
export type Provider = string | null;
export type Model1 = string | null;
export type Calls = number;
export type FallbackUsed = boolean;
export type ItemsLlm = number;
export type ItemsRules = number;
export type ItemsCached = number;
export type Source1 = string;
export type Level2 = number;
export type LabelSk = string | null;
export type Since1 = string | null;
export type CheckedAt = string | null;
export type Url3 = string;
export type Region1 = "SK" | "EU";
export type Level3 = 1 | 2 | 3 | 4;
export type Index = number;
/**
 * True while the event history is shorter than two weeks: computed and recorded, but not shown as a level
 */
export type Provisional = boolean;
export type AvailableFrom = string | null;
export type IndexPrev = number | null;
export type LevelPrev = (1 | 2 | 3 | 4) | null;
export type RulesLevel = 1 | 2 | 3 | 4;
export type Components = Component[];
export type Gates = Gate[];
export type Disagreement = boolean;
export type AnchorIds = string[];
export type SchemaVersion = 1;
export type Id7 = string;
export type Status5 = "ok" | "partial" | "failed";
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
export type AfterPrefilter = number;
export type Relevant1 = number;
export type Id8 = string;
export type Name2 = string;
export type Tier1 = "A" | "B" | "C";
export type Group = string;
export type Status6 = "ok" | "stale" | "failed" | "disabled";
export type LastSuccess = string | null;
export type LastError = string | null;
export type Items = number;
export type HttpStatus = number | null;
export type Error1 = string | null;
export type Note = string | null;
/**
 * Successful runs in a row with no items
 */
export type ZeroRuns = number;
export type LastItemsAt = string | null;
export type Sources = SourceHealth[];
export type Items1 = Item[];
export type Anchors = AnchorReading[];
/**
 * Events from the last 30 days
 */
export type Events = Event[];
export type ReportYear = number;
export type Url4 = string;
export type DataYear = number;
export type AttacksTotal = number;
export type AttacksCompleted = number | null;
export type MemberStatesWithAttacks = number | null;
export type Fatalities = number | null;
export type ArrestsTotal = number;
export type AttacksFailed = number;
export type AttacksFoiled = number;
export type SlovakiaAttacks = number;
export type SlovakiaArrests = number;
export type ReportYear1 = number;
export type Published = string;
export type Url5 = string;
export type PointsEn = string[];
export type PointsSk = string[];
/**
 * True for made-up sample data used to develop the frontend; the site labels it on every page
 */
export type Sample = boolean;
export type SchemaVersion1 = 1;
export type RunId = string;
export type At = string;
export type Region2 = "SK" | "EU";
export type Index1 = number;
export type Level4 = 1 | 2 | 3 | 4;
export type RulesLevel1 = 1 | 2 | 3 | 4;
export type LlmLevel = (1 | 2 | 3 | 4) | null;
/**
 * Gates that changed the level in this run (a cap lowered it, or the floor raised it)
 */
export type Gates1 = string[];
export type Rows = TimeseriesRow[];
export type Sample1 = boolean;

export interface ThreatDashboardData {
  [k: string]: unknown;
}
/**
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "Activity".
 */
export interface Activity {
  value: Value;
  articles_24h: Articles24H;
  baseline_median: BaselineMedian;
}
/**
 * An official reading from a government page: a national threat level, or another
 * government's travel advice for a country.
 *
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "AnchorReading".
 */
export interface AnchorReading {
  id: Id;
  country: Country;
  name: Name;
  url: Url;
  scale: Scale;
  raw: Raw;
  level: Level;
  normalized: Normalized;
  since: Since;
  as_of: AsOf;
  status: Status;
  error: Error;
  text_hash: TextHash;
  detail: Detail;
  manual: Manual;
  kind: Kind;
  issuer: Issuer;
}
/**
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "Brief".
 */
export interface Brief {
  status: Status1;
  lines: Lines;
  what_changed_en: WhatChangedEn;
  what_changed_sk: WhatChangedSk;
}
/**
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "BriefLine".
 */
export interface BriefLine {
  text_en: TextEn;
  text_sk: TextSk;
  item_ids: ItemIds;
}
/**
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "Classification".
 */
export interface Classification {
  status: Status2;
  relevant: Relevant;
  domain: Domain;
  event_type: EventType;
  ideology: Ideology;
  severity: Severity;
  sk_link: SkLink;
  countries: Countries;
  places: Places;
  event_key: EventKey;
  summary_en: SummaryEn;
  summary_sk: SummarySk;
  confidence: Confidence;
}
/**
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "Place".
 */
export interface Place {
  name: Name1;
  lat: Lat;
  lon: Lon;
  precision: Precision;
}
/**
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "Component".
 */
export interface Component {
  id: Id1;
  weight: Weight;
  value: Value1;
  inputs: Inputs;
  event_ids: EventIds;
}
export interface Inputs {
  [k: string]: number | string | null;
}
/**
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "Diff".
 */
export interface Diff {
  new_event_ids: NewEventIds;
  level_changes: LevelChanges;
  anchor_changes: AnchorChanges;
  source_changes: SourceChanges;
}
/**
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "LevelChange".
 */
export interface LevelChange {
  region: Region;
  level_from: LevelFrom;
  level_to: LevelTo;
}
/**
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "ValueChange".
 */
export interface ValueChange {
  id: Id2;
  value_from: ValueFrom;
  value_to: ValueTo;
}
/**
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "Driver".
 */
export interface Driver {
  text_en: TextEn1;
  text_sk: TextSk1;
  event_ids: EventIds1;
}
/**
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "Event".
 */
export interface Event {
  id: Id3;
  title_en: TitleEn;
  title_sk: TitleSk;
  event_type: EventType1;
  ideology: Ideology1;
  severity: Severity1;
  date: Date;
  country: Country1;
  place: Place | null;
  sk_link: SkLink1;
  topic: Topic;
  item_ids: ItemIds1;
  event_keys: EventKeys;
  domains: Domains;
  has_tier_a: HasTierA;
  best_tier: BestTier;
  corroborated: Corroborated;
  first_seen: FirstSeen;
  last_updated: LastUpdated;
}
/**
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "Gate".
 */
export interface Gate {
  id: Id4;
  effect: Effect;
  event_ids: EventIds2;
}
/**
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "GdeltInfo".
 */
export interface GdeltInfo {
  tone: Tone;
  themes: Themes;
}
/**
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "Geopolitics".
 */
export interface Geopolitics {
  theatres: Theatres;
  brief: Brief | null;
  watchlist: Watchlist;
}
/**
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "Theatre".
 */
export interface Theatre {
  id: Id5;
  name_en: NameEn;
  name_sk: NameSk;
  activity: Activity;
  countries: Countries1;
  tone: Tone1 | null;
  sparkline: Sparkline;
  top_items: TopItems;
  sk_angle_en: SkAngleEn;
  sk_angle_sk: SkAngleSk;
}
/**
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "Tone".
 */
export interface Tone1 {
  value: Value2;
  baseline_median: BaselineMedian1;
}
/**
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "TopItem".
 */
export interface TopItem {
  item_id: ItemId;
  summary_en: SummaryEn1;
  summary_sk: SummarySk1;
}
/**
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "WatchlistEntry".
 */
export interface WatchlistEntry {
  date: Date1;
  title_en: TitleEn1;
  title_sk: TitleSk1;
  origin: Origin;
  verified: Verified;
  url: Url1;
}
/**
 * Yearly Global Terrorism Database counts (static/gtd_aggregates.json, aggregates only).
 *
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "Gtd".
 */
export interface Gtd {
  source: Source;
  data_ends: DataEnds;
  generated: Generated;
  SK: Sk;
  EU: Eu;
}
/**
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "GtdYear".
 */
export interface GtdYear {
  year: Year;
  incidents: Incidents;
  deaths: Deaths;
}
/**
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "Item".
 */
export interface Item {
  id: Id6;
  source_id: SourceId;
  tier: Tier;
  url: Url2;
  title: Title;
  lang: Lang;
  published_at: PublishedAt;
  published_estimated: PublishedEstimated;
  fetched_at: FetchedAt;
  snippet: Snippet;
  domain: Domain1;
  also_reported_by: AlsoReportedBy;
  gdelt: GdeltInfo | null;
  classification: Classification | null;
  event_id: EventId;
}
/**
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "LlmAssessment".
 */
export interface LlmAssessment {
  status: Status3;
  level: Level1;
  position: Position;
  confidence: Confidence1;
  drivers: Drivers;
  what_changed_en: WhatChangedEn1;
  what_changed_sk: WhatChangedSk1;
  model: Model;
}
/**
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "LlmUsage".
 */
export interface LlmUsage {
  status: Status4;
  provider: Provider;
  model: Model1;
  calls: Calls;
  fallback_used: FallbackUsed;
  items_llm: ItemsLlm;
  items_rules: ItemsRules;
  items_cached: ItemsCached;
}
/**
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "OfficialLevel".
 */
export interface OfficialLevel {
  source: Source1;
  level: Level2;
  label_sk: LabelSk;
  since: Since1;
  checked_at: CheckedAt;
  url: Url3;
}
/**
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "RegionAssessment".
 */
export interface RegionAssessment {
  region: Region1;
  level: Level3;
  index: Index;
  provisional: Provisional;
  available_from: AvailableFrom;
  index_prev: IndexPrev;
  level_prev: LevelPrev;
  rules_level: RulesLevel;
  components: Components;
  gates: Gates;
  llm: LlmAssessment;
  disagreement: Disagreement;
  /**
   * SIS level for SK; none for the EU, which has no EU-wide level
   */
  official: OfficialLevel | null;
  anchor_ids: AnchorIds;
}
/**
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "Run".
 */
export interface Run {
  schema_version: SchemaVersion;
  run: RunInfo;
  sources: Sources;
  items: Items1;
  anchors: Anchors;
  /**
   * Null until scoring exists
   */
  terrorism: Terrorism | null;
  geopolitics: Geopolitics | null;
  events: Events;
  diff: Diff | null;
  tesat: Tesat | null;
  sis_annual: SisAnnual | null;
  gtd: Gtd | null;
  sample: Sample;
}
/**
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "RunInfo".
 */
export interface RunInfo {
  id: Id7;
  status: Status5;
  started_at: StartedAt;
  finished_at: FinishedAt;
  window_start: WindowStart;
  git_sha: GitSha;
  counts: RunCounts;
  llm: LlmUsage | null;
}
/**
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "RunCounts".
 */
export interface RunCounts {
  fetched: Fetched;
  from_buffer: FromBuffer;
  after_dedupe: AfterDedupe;
  in_window: InWindow;
  after_prefilter: AfterPrefilter;
  relevant: Relevant1;
}
/**
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "SourceHealth".
 */
export interface SourceHealth {
  id: Id8;
  name: Name2;
  tier: Tier1;
  group: Group;
  status: Status6;
  last_success: LastSuccess;
  last_error: LastError;
  items: Items;
  http_status: HttpStatus;
  error: Error1;
  note: Note;
  zero_runs: ZeroRuns;
  last_items_at: LastItemsAt;
}
/**
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "Terrorism".
 */
export interface Terrorism {
  SK: RegionAssessment;
  EU: RegionAssessment;
}
/**
 * Europol TE-SAT yearly figures, typed in from the PDF (manual_anchors.yaml).
 *
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "Tesat".
 */
export interface Tesat {
  report_year: ReportYear;
  url: Url4;
  current: TesatYear;
  attacks_failed: AttacksFailed;
  attacks_foiled: AttacksFoiled;
  attacks_by_ideology: AttacksByIdeology;
  arrests_by_ideology: ArrestsByIdeology;
  slovakia_attacks: SlovakiaAttacks;
  slovakia_arrests: SlovakiaArrests;
  previous: TesatYear | null;
}
/**
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "TesatYear".
 */
export interface TesatYear {
  data_year: DataYear;
  attacks_total: AttacksTotal;
  attacks_completed: AttacksCompleted;
  member_states_with_attacks: MemberStatesWithAttacks;
  fatalities: Fatalities;
  arrests_total: ArrestsTotal;
}
export interface AttacksByIdeology {
  [k: string]: number;
}
export interface ArrestsByIdeology {
  [k: string]: number;
}
/**
 * Points from the latest SIS annual report, summarised by hand (manual_anchors.yaml).
 *
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "SisAnnual".
 */
export interface SisAnnual {
  report_year: ReportYear1;
  published: Published;
  url: Url5;
  points_en: PointsEn;
  points_sk: PointsSk;
}
/**
 * timeseries.json: one row per region per run, never pruned.
 *
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "Timeseries".
 */
export interface Timeseries {
  schema_version: SchemaVersion1;
  rows: Rows;
  sample: Sample1;
}
/**
 * This interface was referenced by `ThreatDashboardData`'s JSON-Schema
 * via the `definition` "TimeseriesRow".
 */
export interface TimeseriesRow {
  run_id: RunId;
  at: At;
  region: Region2;
  index: Index1;
  level: Level4;
  rules_level: RulesLevel1;
  llm_level: LlmLevel;
  components: Components1;
  gates: Gates1;
}
export interface Components1 {
  [k: string]: number | null;
}
