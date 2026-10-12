/** Controller-owned formal ratings; never infer grades or admission from scores. */
export type Grade = 'S' | 'A' | 'B';
export type GradeFilter = 'all' | Grade | 'ungraded';
export type FormalAssessment = {
  grade: Grade;
  score: number;
  score_breakdown: number[] | Record<string, number>;
  source_version: string;
  source_program: string;
  source_pdf_sha256: string;
  assessment_sha256: string;
  registry_seq: number;
  rationale: unknown;
  review_boundary: unknown;
  load_bearing_contribution_confirmed: boolean;
};
export type FormalGrades = {
  schema_version: 1;
  rubric: { axes: string[]; max_score: 40 };
  assessments: Record<string, FormalAssessment>;
};

export function axisScores(assessment: FormalAssessment, axes: string[]): number[] {
  const breakdown = assessment.score_breakdown;
  if (Array.isArray(breakdown) && breakdown.length === axes.length) return breakdown;
  if (breakdown && !Array.isArray(breakdown)
    && Object.keys(breakdown).length === axes.length
    && axes.every((axis) => Object.hasOwn(breakdown, axis))) return axes.map((axis) => breakdown[axis]);
  throw new Error('Formal assessment must contain all eight rubric axes');
}

export function parseFormalGrades(value: unknown): FormalGrades {
  const data = value as FormalGrades;
  const axes = data?.rubric?.axes;
  if (data?.schema_version !== 1 || data.rubric?.max_score !== 40
    || !Array.isArray(axes) || axes.length !== 8 || new Set(axes).size !== 8
    || !axes.every((axis) => typeof axis === 'string' && axis.length > 0)
    || !data.assessments || typeof data.assessments !== 'object' || Array.isArray(data.assessments)) {
    throw new Error('Unsupported formal grading schema/rubric');
  }
  for (const [id, assessment] of Object.entries(data.assessments)) {
    const scores = axisScores(assessment, axes);
    if (!['S', 'A', 'B'].includes(assessment.grade)
      || scores.some((score) => typeof score !== 'number' || !Number.isFinite(score) || score < 0 || score > 5)
      || typeof assessment.score !== 'number' || !Number.isFinite(assessment.score)
      || Math.abs(scores.reduce((total, score) => total + score, 0) - assessment.score) > 1e-9) {
      throw new Error(`Invalid formal assessment: ${id}`);
    }
  }
  return data;
}

export function formalAssessment(data: FormalGrades | null, id: string): FormalAssessment | undefined {
  return data && Object.hasOwn(data.assessments, id) ? data.assessments[id] : undefined;
}

export function matchesFormalGrade(data: FormalGrades | null, id: string, filter: GradeFilter): boolean {
  return filter === 'all' || (formalAssessment(data, id)?.grade ?? 'ungraded') === filter;
}

export function displayText(value: unknown): string {
  if (value === undefined || value === null) return '未提供';
  return typeof value === 'string' ? value : JSON.stringify(value);
}
