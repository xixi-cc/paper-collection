import assert from 'node:assert/strict';
import { test } from 'node:test';
import { parseFormalGrades, axisScores, formalAssessment, matchesFormalGrade } from '../src/formalGrades.ts';

const axes = Array.from({ length: 8 }, (_, i) => `评分轴${i}`);
function dataset() {
  return {
    schema_version: 1, rubric: { axes, max_score: 40 },
    assessments: { exact: {
      grade: 'B', score: 40, score_breakdown: Array(8).fill(5),
      source_program: 'Collection', source_version: 'v2',
      source_pdf_sha256: 'a'.repeat(64), assessment_sha256: 'b'.repeat(64),
      registry_seq: 123, rationale: '有限模型', review_boundary: '未独立复现',
      load_bearing_contribution_confirmed: false,
    } },
  };
}

test('explicit accepted grade is never forced to S by a 40 point total', () => {
  const data = parseFormalGrades(dataset());
  assert.equal(formalAssessment(data, 'exact').grade, 'B');
  assert.ok(matchesFormalGrade(data, 'exact', 'B'));
  assert.ok(matchesFormalGrade(data, 'exact', 'all'));
  assert.ok(!matchesFormalGrade(data, 'exact', 'S'));
  assert.ok(!matchesFormalGrade(data, 'exact', 'A'));
  assert.ok(!matchesFormalGrade(data, 'exact', 'ungraded'));
});

test('missing formal remains visible in all and ungraded, without ID/version inference', () => {
  const data = parseFormalGrades(dataset());
  for (const id of ['missing', 'exactv2', '__proto__']) {
    assert.equal(formalAssessment(data, id), undefined);
    assert.ok(matchesFormalGrade(data, id, 'all'));
    assert.ok(matchesFormalGrade(data, id, 'ungraded'));
    assert.ok(!matchesFormalGrade(data, id, 'S'));
  }
  assert.ok(matchesFormalGrade(null, 'exact', 'ungraded'));
});

test('all eight axes retain rubric order and origin/version/boundary survive parsing', () => {
  const data = dataset();
  data.assessments.exact.score_breakdown = Object.fromEntries([...axes].reverse().map((axis) => [axis, 5]));
  const parsed = parseFormalGrades(data);
  assert.deepEqual(axisScores(parsed.assessments.exact, axes), Array(8).fill(5));
  assert.deepEqual(parsed.assessments.exact, data.assessments.exact);
});

test('unsupported schema, missing axes and inconsistent totals fail visibly', () => {
  for (const mutate of [
    (data) => { data.schema_version = 2; },
    (data) => { data.assessments.exact.score_breakdown.pop(); },
    (data) => { data.assessments.exact.score = 39; },
    (data) => { data.assessments.exact.grade = 'C'; },
    (data) => { data.assessments.exact.score_breakdown[0] = NaN; },
  ]) {
    const data = dataset();
    mutate(data);
    assert.throws(() => parseFormalGrades(data));
  }
});
