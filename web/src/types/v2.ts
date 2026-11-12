/* Generated from v2.schema.json by npm run gen:types. Do not edit. */

export type SchemaVersion = 2;
export type UpdatedAt = string;
export type StartedAt = string;
export type GitSha = string | null;
export type Overall = "ok" | "degraded" | "failed";
export type Reasons = string[];
export type Status1 = ("ok" | "degraded" | "failed") | "skipped";
export type Detail = string;
export type WaitingLabel = number;
export type WaitingMatch = number;
export type OldestWaitingHours = number | null;
export type GivenUp24H = number;
export type Labelled24H = number;
export type LastScored = string | null;
export type BriefWrittenAt = string | null;
export type Id = string;
export type Name = string;
export type Tier = "A" | "B" | "C";
export type Group = string;
export type Status2 = "ok" | "stale" | "failed" | "disabled";
export type LastSuccess = string | null;
export type LastError = string | null;
export type Items = number;
export type HttpStatus = number | null;
export type Error = string | null;
export type Note = string | null;
/**
 * Successful runs in a row with no items
 */
export type ZeroRuns = number;
export type LastItemsAt = string | null;
export type Sources = SourceHealth[];
export type SchemaVersion1 = 2;
/**
 * The scoring run the levels come from
 */
export type RunId = string | null;
export type ScoredAt = string | null;
export type Region = "SK" | "EU";
export type Level = 1 | 2 | 3 | 4;
export type Index = number;
/**
 * True while the event history is shorter than two weeks: computed and recorded, but not shown as a level
 */
export type Provisional = boolean;
export type AvailableFrom = string | null;
export type IndexPrev = number | null;
export type LevelPrev = (1 | 2 | 3 | 4) | null;
export type RulesLevel = 1 | 2 | 3 | 4;
export type Id1 = "events" | "media" | "anchors" | "llm";
export type Weight = number;
export type Value = number | null;
export type EventIds = string[];
export type Components = Component[];
export type Id2 = string;
export type Effect = string;
export type EventIds1 = string[];
export type Gates = Gate[];
export type Status3 = "ok" | "fallback" | "disabled";
export type Level1 = (1 | 2 | 3 | 4) | null;
export type Position = ("low" | "mid" | "high") | null;
export type Confidence = ("low" | "medium" | "high") | null;
export type TextEn = string;
export type TextSk = string | null;
export type EventIds2 = string[];
export type Drivers = Driver[];
export type WhatChangedEn = string | null;
export type WhatChangedSk = string | null;
export type Model = string | null;
export type Disagreement = boolean;
export type Source = string;
export type Level2 = number;
export type LabelSk = string | null;
export type Since = string | null;
export type CheckedAt = string | null;
export type Url = string;
export type AnchorIds = string[];
export type NewEventIds = string[];
export type Region1 = "SK" | "EU";
export type LevelFrom = number | null;
export type LevelTo = number;
export type LevelChanges = LevelChange[];
export type Id3 = string;
export type ValueFrom = string | null;
export type ValueTo = string | null;
export type AnchorChanges = ValueChange[];
export type SourceChanges = ValueChange[];
export type Id4 = string;
/**
 * ISO 3166-1 alpha-2
 */
export type Country = string;
export type Name1 = string;
export type Url1 = string;
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
export type Level3 = number | null;
/**
 * (level - 1) / (len(scale) - 1)
 */
export type Normalized = number | null;
/**
 * Date the level was declared, if stated
 */
export type Since1 = string | null;
/**
 * Last time the value was read successfully
 */
export type AsOf = string | null;
export type Status4 = "ok" | "stale" | "failed" | "disabled";
export type Error1 = string | null;
/**
 * sha1 of the paragraph stating the level, to detect any change in wording
 */
export type TextHash = string | null;
/**
 * Other levels in force at the same time, e.g. a higher level for railways only
 */
export type Detail1 = string | null;
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
export type Anchors = AnchorReading[];
export type ReportYear = number;
export type Url2 = string;
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
export type Published1 = string;
export type Url3 = string;
export type PointsEn = string[];
export type PointsSk = string[];
export type Source1 = string;
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
export type SchemaVersion2 = 2;
export type UpdatedAt1 = string;
export type Id5 = string;
export type Type =
  | "attack"
  | "attempted_attack"
  | "plot_disrupted"
  | "arrest"
  | "conviction"
  | "threat_statement"
  | "sabotage"
  | "other";
/**
 * 0 only for a threat with no act: listed, but it weighs nothing in the index, as in the old method
 */
export type Severity = number;
/**
 * The day it happened, not the day it was reported
 */
export type Date = string;
export type Country1 = string;
export type Name2 = string;
export type Lat = number;
export type Lon = number;
export type Precision = "city" | "region" | "country";
export type Ideology =
  "jihadist" | "right_wing" | "left_anarchist" | "ethno_separatist" | "state_linked" | "other" | "unknown";
export type SkLink = "none" | "indirect" | "direct";
export type Topic = "terrorism" | "hybrid";
export type TitleEn = string;
export type TitleSk = string | null;
export type ArticleId = string;
export type Url4 = string;
export type Source2 = string;
export type Tier1 = "A" | "B" | "C";
export type PublishedAt = string;
export type Kind1 = "new_incident" | "update";
/**
 * None on reports carried over from the old pipeline, which kept no summary per article
 */
export type SummaryEn = string | null;
export type SummarySk = string | null;
/**
 * What this report says the incident was
 */
export type Type1 =
  | "attack"
  | "attempted_attack"
  | "plot_disrupted"
  | "arrest"
  | "conviction"
  | "threat_statement"
  | "sabotage"
  | "other";
/**
 * How severe this report says it was
 */
export type Severity1 = number;
/**
 * The day this report says it happened
 */
export type EventDate = string;
export type AlsoReportedBy = string[];
/**
 * Its timeline, oldest first
 */
export type Reports = Report[];
/**
 * Outlets that reported it
 */
export type Domains = string[];
export type HasTierA = boolean;
export type BestTier = ("A" | "B" | "C") | null;
export type Corroborated = boolean;
export type FirstSeen = string;
export type LastUpdated = string;
/**
 * The old pipeline's event id, for incidents carried over at the start
 */
export type SeededFrom = string | null;
export type Incidents1 = Incident[];
export type Action = "merge" | "remove" | "detach";
export type Note1 = string;
export type Applied = boolean;
export type Corrections = Correction[];
export type SchemaVersion3 = 2;
export type UpdatedAt2 = string;
/**
 * sha1 of the canonical URL
 */
export type Id6 = string;
export type SourceId = string;
export type Tier2 = "A" | "B" | "C";
export type Url5 = string;
export type Title = string;
export type Lang = string;
export type PublishedAt1 = string;
export type FetchedAt = string;
export type Snippet = string;
export type Domain = string;
export type AlsoReportedBy1 = string[];
export type FirstSeen1 = string;
export type Id7 = string;
export type Kind2 = "new_incident" | "update" | "context" | "none";
export type Domain1 = "terrorism" | "hybrid" | "cyber" | "unrest" | "geopolitics" | "other";
export type SkLink1 = "none" | "indirect" | "direct";
/**
 * @maxItems 6
 */
export type Countries =
  | []
  | [string]
  | [string, string]
  | [string, string, string]
  | [string, string, string, string]
  | [string, string, string, string, string]
  | [string, string, string, string, string, string];
export type IncidentType =
  | (
      | "attack"
      | "attempted_attack"
      | "plot_disrupted"
      | "arrest"
      | "conviction"
      | "threat_statement"
      | "sabotage"
      | "other"
    )
  | null;
export type Severity2 = number;
export type IncidentDate = string | null;
export type IncidentCountry = string | null;
export type IncidentPlace = string | null;
export type Ideology1 =
  "jihadist" | "right_wing" | "left_anarchist" | "ethno_separatist" | "state_linked" | "other" | "unknown";
export type SummaryEn1 = string;
export type SummarySk1 = string;
export type Confidence1 = number;
/**
 * The model that labelled it
 */
export type LabelledBy = string | null;
export type LabelledAt = string | null;
/**
 * Answers that left it out or mislabelled
 */
export type LabelAttempts = number;
export type IncidentId = string | null;
export type MatchedBy = string | null;
export type MatchAttempts = number;
/**
 * Why no model is asked again
 */
export type GivenUp = string | null;
export type Reports1 = Article[];
export type SchemaVersion4 = 2;
export type UpdatedAt3 = string;
export type Id8 = string;
export type NameEn = string;
export type NameSk = string;
/**
 * f(articles 24 h / 90-day median)
 */
export type Value1 = number | null;
export type Articles24H = number | null;
export type BaselineMedian = number | null;
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
export type SummaryEn2 = string;
export type SummarySk2 = string | null;
export type TopItems = TopItem[];
export type SkAngleEn = string | null;
export type SkAngleSk = string | null;
export type TextEn1 = string;
export type TextSk1 = string | null;
export type ItemIds = string[];
/**
 * Article URLs of its items, so the line keeps its links when the brief is carried forward
 */
export type Urls = string[];
export type Lines = BriefLine[];
/**
 * When this theatre's text was written; older than the run when a call failed
 */
export type WrittenAt = string | null;
export type WrittenBy = string | null;
export type Theatres = TheatreV2[];
export type Date1 = string;
export type TitleEn1 = string;
export type TitleSk1 = string | null;
export type Origin = "manual" | "news";
export type Verified = boolean;
export type Url6 = string | null;
export type Watchlist = WatchlistEntry[];

/**
 * Every file the website reads from v2/ of the data branch.
 */
export interface Published {
  status: Status;
  summary: Summary;
  incidents: IncidentsFile;
  reports: ReportsFile;
  geopolitics: GeopoliticsFile;
  [k: string]: unknown;
}
/**
 * status.json: what each stage did, in facts rather than one word.
 *
 * This interface was referenced by `Published`'s JSON-Schema
 * via the `definition` "Status".
 */
export interface Status {
  schema_version: SchemaVersion;
  updated_at: UpdatedAt;
  started_at: StartedAt;
  git_sha: GitSha;
  overall: Overall;
  reasons: Reasons;
  stages: Stages;
  queue: Queue;
  ai: Ai;
  labelled_by_24h: LabelledBy24H;
  last_scored: LastScored;
  brief_written_at: BriefWrittenAt;
  sources: Sources;
}
export interface Stages {
  [k: string]: Stage;
}
/**
 * This interface was referenced by `Published`'s JSON-Schema
 * via the `definition` "Stage".
 */
export interface Stage {
  status: Status1;
  detail: Detail;
}
/**
 * This interface was referenced by `Published`'s JSON-Schema
 * via the `definition` "Queue".
 */
export interface Queue {
  waiting_label: WaitingLabel;
  waiting_match: WaitingMatch;
  oldest_waiting_hours: OldestWaitingHours;
  given_up_24h: GivenUp24H;
  labelled_24h: Labelled24H;
}
export interface Ai {
  [k: string]: {
    [k: string]: unknown;
  };
}
/**
 * Articles labelled per model, 24 hours
 */
export interface LabelledBy24H {
  [k: string]: number;
}
/**
 * This interface was referenced by `Published`'s JSON-Schema
 * via the `definition` "SourceHealth".
 */
export interface SourceHealth {
  id: Id;
  name: Name;
  tier: Tier;
  group: Group;
  status: Status2;
  last_success: LastSuccess;
  last_error: LastError;
  items: Items;
  http_status: HttpStatus;
  error: Error;
  note: Note;
  zero_runs: ZeroRuns;
  last_items_at: LastItemsAt;
}
/**
 * summary.json: what the first screen needs.
 *
 * This interface was referenced by `Published`'s JSON-Schema
 * via the `definition` "Summary".
 */
export interface Summary {
  schema_version: SchemaVersion1;
  run_id: RunId;
  scored_at: ScoredAt;
  terrorism: Terrorism | null;
  /**
   * What changed between the last two scoring runs
   */
  diff: Diff | null;
  anchors: Anchors;
  tesat: Tesat | null;
  sis_annual: SisAnnual | null;
  gtd: Gtd | null;
}
/**
 * This interface was referenced by `Published`'s JSON-Schema
 * via the `definition` "Terrorism".
 */
export interface Terrorism {
  SK: RegionAssessment;
  EU: RegionAssessment;
}
/**
 * This interface was referenced by `Published`'s JSON-Schema
 * via the `definition` "RegionAssessment".
 */
export interface RegionAssessment {
  region: Region;
  level: Level;
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
 * This interface was referenced by `Published`'s JSON-Schema
 * via the `definition` "Component".
 */
export interface Component {
  id: Id1;
  weight: Weight;
  value: Value;
  inputs: Inputs;
  event_ids: EventIds;
}
export interface Inputs {
  [k: string]: number | string | null;
}
/**
 * This interface was referenced by `Published`'s JSON-Schema
 * via the `definition` "Gate".
 */
export interface Gate {
  id: Id2;
  effect: Effect;
  event_ids: EventIds1;
}
/**
 * This interface was referenced by `Published`'s JSON-Schema
 * via the `definition` "LlmAssessment".
 */
export interface LlmAssessment {
  status: Status3;
  level: Level1;
  position: Position;
  confidence: Confidence;
  drivers: Drivers;
  what_changed_en: WhatChangedEn;
  what_changed_sk: WhatChangedSk;
  model: Model;
}
/**
 * This interface was referenced by `Published`'s JSON-Schema
 * via the `definition` "Driver".
 */
export interface Driver {
  text_en: TextEn;
  text_sk: TextSk;
  event_ids: EventIds2;
}
/**
 * This interface was referenced by `Published`'s JSON-Schema
 * via the `definition` "OfficialLevel".
 */
export interface OfficialLevel {
  source: Source;
  level: Level2;
  label_sk: LabelSk;
  since: Since;
  checked_at: CheckedAt;
  url: Url;
}
/**
 * This interface was referenced by `Published`'s JSON-Schema
 * via the `definition` "Diff".
 */
export interface Diff {
  new_event_ids: NewEventIds;
  level_changes: LevelChanges;
  anchor_changes: AnchorChanges;
  source_changes: SourceChanges;
}
/**
 * This interface was referenced by `Published`'s JSON-Schema
 * via the `definition` "LevelChange".
 */
export interface LevelChange {
  region: Region1;
  level_from: LevelFrom;
  level_to: LevelTo;
}
/**
 * This interface was referenced by `Published`'s JSON-Schema
 * via the `definition` "ValueChange".
 */
export interface ValueChange {
  id: Id3;
  value_from: ValueFrom;
  value_to: ValueTo;
}
/**
 * An official reading from a government page: a national threat level, or another
 * government's travel advice for a country.
 *
 * This interface was referenced by `Published`'s JSON-Schema
 * via the `definition` "AnchorReading".
 */
export interface AnchorReading {
  id: Id4;
  country: Country;
  name: Name1;
  url: Url1;
  scale: Scale;
  raw: Raw;
  level: Level3;
  normalized: Normalized;
  since: Since1;
  as_of: AsOf;
  status: Status4;
  error: Error1;
  text_hash: TextHash;
  detail: Detail1;
  manual: Manual;
  kind: Kind;
  issuer: Issuer;
}
/**
 * Europol TE-SAT yearly figures, typed in from the PDF (manual_anchors.yaml).
 *
 * This interface was referenced by `Published`'s JSON-Schema
 * via the `definition` "Tesat".
 */
export interface Tesat {
  report_year: ReportYear;
  url: Url2;
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
 * This interface was referenced by `Published`'s JSON-Schema
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
 * This interface was referenced by `Published`'s JSON-Schema
 * via the `definition` "SisAnnual".
 */
export interface SisAnnual {
  report_year: ReportYear1;
  published: Published1;
  url: Url3;
  points_en: PointsEn;
  points_sk: PointsSk;
}
/**
 * Yearly Global Terrorism Database counts (static/gtd_aggregates.json, aggregates only).
 *
 * This interface was referenced by `Published`'s JSON-Schema
 * via the `definition` "Gtd".
 */
export interface Gtd {
  source: Source1;
  data_ends: DataEnds;
  generated: Generated;
  SK: Sk;
  EU: Eu;
}
/**
 * This interface was referenced by `Published`'s JSON-Schema
 * via the `definition` "GtdYear".
 */
export interface GtdYear {
  year: Year;
  incidents: Incidents;
  deaths: Deaths;
}
/**
 * incidents/current.json and incidents/YYYY-MM.json.
 *
 * This interface was referenced by `Published`'s JSON-Schema
 * via the `definition` "IncidentsFile".
 */
export interface IncidentsFile {
  schema_version: SchemaVersion2;
  updated_at: UpdatedAt1;
  incidents: Incidents1;
  corrections: Corrections;
}
/**
 * This interface was referenced by `Published`'s JSON-Schema
 * via the `definition` "Incident".
 */
export interface Incident {
  id: Id5;
  type: Type;
  severity: Severity;
  date: Date;
  country: Country1;
  place: Place | null;
  ideology: Ideology;
  sk_link: SkLink;
  topic: Topic;
  title_en: TitleEn;
  title_sk: TitleSk;
  reports: Reports;
  domains: Domains;
  has_tier_a: HasTierA;
  best_tier: BestTier;
  corroborated: Corroborated;
  first_seen: FirstSeen;
  last_updated: LastUpdated;
  seeded_from: SeededFrom;
}
/**
 * This interface was referenced by `Published`'s JSON-Schema
 * via the `definition` "Place".
 */
export interface Place {
  name: Name2;
  lat: Lat;
  lon: Lon;
  precision: Precision;
}
/**
 * An article on an incident's timeline.
 *
 * This interface was referenced by `Published`'s JSON-Schema
 * via the `definition` "Report".
 */
export interface Report {
  article_id: ArticleId;
  url: Url4;
  source: Source2;
  tier: Tier1;
  published_at: PublishedAt;
  kind: Kind1;
  summary_en: SummaryEn;
  summary_sk: SummarySk;
  type: Type1;
  severity: Severity1;
  event_date: EventDate;
  also_reported_by: AlsoReportedBy;
}
/**
 * This interface was referenced by `Published`'s JSON-Schema
 * via the `definition` "Correction".
 */
export interface Correction {
  action: Action;
  note: Note1;
  applied: Applied;
}
/**
 * reports.json: labelled, relevant articles of the last 48 hours.
 *
 * This interface was referenced by `Published`'s JSON-Schema
 * via the `definition` "ReportsFile".
 */
export interface ReportsFile {
  schema_version: SchemaVersion3;
  updated_at: UpdatedAt2;
  reports: Reports1;
}
/**
 * A news item worth showing to a model, with what became of it.
 *
 * This interface was referenced by `Published`'s JSON-Schema
 * via the `definition` "Article".
 */
export interface Article {
  id: Id6;
  source_id: SourceId;
  tier: Tier2;
  url: Url5;
  title: Title;
  lang: Lang;
  published_at: PublishedAt1;
  fetched_at: FetchedAt;
  snippet: Snippet;
  domain: Domain;
  also_reported_by: AlsoReportedBy1;
  first_seen: FirstSeen1;
  label: ArticleLabel | null;
  labelled_by: LabelledBy;
  labelled_at: LabelledAt;
  label_attempts: LabelAttempts;
  /**
   * incident_place with coordinates
   */
  place: Place | null;
  incident_id: IncidentId;
  matched_by: MatchedBy;
  match_attempts: MatchAttempts;
  given_up: GivenUp;
}
/**
 * One article's label, as validated after the provider's strict mode.
 *
 * This interface was referenced by `Published`'s JSON-Schema
 * via the `definition` "ArticleLabel".
 */
export interface ArticleLabel {
  id: Id7;
  kind: Kind2;
  domain: Domain1;
  sk_link: SkLink1;
  countries: Countries;
  incident_type: IncidentType;
  severity: Severity2;
  incident_date: IncidentDate;
  incident_country: IncidentCountry;
  incident_place: IncidentPlace;
  ideology: Ideology1;
  summary_en: SummaryEn1;
  summary_sk: SummarySk1;
  confidence: Confidence1;
}
/**
 * This interface was referenced by `Published`'s JSON-Schema
 * via the `definition` "GeopoliticsFile".
 */
export interface GeopoliticsFile {
  schema_version: SchemaVersion4;
  updated_at: UpdatedAt3;
  theatres: Theatres;
  watchlist: Watchlist;
}
/**
 * This interface was referenced by `Published`'s JSON-Schema
 * via the `definition` "TheatreV2".
 */
export interface TheatreV2 {
  id: Id8;
  name_en: NameEn;
  name_sk: NameSk;
  activity: Activity;
  countries: Countries1;
  tone: Tone | null;
  sparkline: Sparkline;
  top_items: TopItems;
  sk_angle_en: SkAngleEn;
  sk_angle_sk: SkAngleSk;
  lines: Lines;
  written_at: WrittenAt;
  written_by: WrittenBy;
}
/**
 * This interface was referenced by `Published`'s JSON-Schema
 * via the `definition` "Activity".
 */
export interface Activity {
  value: Value1;
  articles_24h: Articles24H;
  baseline_median: BaselineMedian;
}
/**
 * This interface was referenced by `Published`'s JSON-Schema
 * via the `definition` "Tone".
 */
export interface Tone {
  value: Value2;
  baseline_median: BaselineMedian1;
}
/**
 * This interface was referenced by `Published`'s JSON-Schema
 * via the `definition` "TopItem".
 */
export interface TopItem {
  item_id: ItemId;
  summary_en: SummaryEn2;
  summary_sk: SummarySk2;
}
/**
 * This interface was referenced by `Published`'s JSON-Schema
 * via the `definition` "BriefLine".
 */
export interface BriefLine {
  text_en: TextEn1;
  text_sk: TextSk1;
  item_ids: ItemIds;
  urls: Urls;
}
/**
 * This interface was referenced by `Published`'s JSON-Schema
 * via the `definition` "WatchlistEntry".
 */
export interface WatchlistEntry {
  date: Date1;
  title_en: TitleEn1;
  title_sk: TitleSk1;
  origin: Origin;
  verified: Verified;
  url: Url6;
}
