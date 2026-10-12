import { axisScores, displayText, formalAssessment, type FormalGrades } from './formalGrades';

export function FormalGrade({ data, id }: { data: FormalGrades | null; id: string }) {
  const assessment = formalAssessment(data, id);
  if (!assessment || !data) return <span className="formal-grade-status">正式评级：未评级</span>;
  const scores = axisScores(assessment, data.rubric.axes);
  return (
    <details className="formal-grade">
      <summary>正式评级：{assessment.grade} · {assessment.score} / 40</summary>
      <p>评审版本：{assessment.source_version} · 原评审来源：{assessment.source_program}</p>
      <table>
        <caption>八轴评分（每轴 5 分，满分 40 分）</caption>
        <tbody>{data.rubric.axes.map((axis, index) => (
          <tr key={axis}><th scope="row">{axis}</th><td>{scores[index]} / 5</td></tr>
        ))}</tbody>
      </table>
      <p>评级理由：{displayText(assessment.rationale)}</p>
      <p>评审边界：{displayText(assessment.review_boundary)}</p>
      <p>关键贡献已确认：{assessment.load_bearing_contribution_confirmed === true ? '是' : assessment.load_bearing_contribution_confirmed === false ? '否' : '未提供'}</p>
      <details className="formal-grade-evidence">
        <summary>评审记录</summary>
        <p>Registry 序号：{assessment.registry_seq}</p>
        <p>原文 PDF SHA-256：<code>{assessment.source_pdf_sha256}</code></p>
        <p>评审 SHA-256：<code>{assessment.assessment_sha256}</code></p>
      </details>
    </details>
  );
}
