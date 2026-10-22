export type AgeLevel = "fresh" | "amber" | "red";

export const AMBER_AFTER_H = 10;
export const RED_AFTER_H = 14;

/** Hours since the run finished, and whether that is normal, late, or a missed run. */
export function dataAge(finishedAt: string, now: Date): { hours: number; level: AgeLevel } {
  const hours = (now.getTime() - new Date(finishedAt).getTime()) / 3_600_000;
  const level: AgeLevel = hours > RED_AFTER_H ? "red" : hours > AMBER_AFTER_H ? "amber" : "fresh";
  return { hours, level };
}
