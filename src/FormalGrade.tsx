import { axisScores, formalAssessment, type FormalGrades } from './formalGrades';

export function FormalGrade({ data, id }: { data: FormalGrades | null; id: string }) {
  const assessment = formalAssessment(data, id);
  if (!assessment || !data) return <span className="formal-grade-status">正式评级：未评级</span>;
  const scores = axisScores(assessment, data.rubric.axes);
  return (
    <details className="formal-grade">
      <summary>正式评级：{assessment.grade} · {assessment.score} / 40</summary>
      <table>
        <caption>八轴评分（每轴 5 分，满分 40 分）</caption>
        <tbody>{data.rubric.axes.map((axis, index) => (
          <tr key={axis}><th scope="row">{axis}</th><td>{scores[index]} / 5</td></tr>
        ))}</tbody>
      </table>

    </details>
  );
}
