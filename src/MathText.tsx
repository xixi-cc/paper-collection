import { Fragment } from 'react';
import katex from 'katex';
import 'katex/dist/katex.min.css';

// Preserve ordinary text and render only explicitly delimited mathematics.
const math = /(\$\$[\s\S]+?\$\$|(?<!\\)\$(?!\$)[^$\n]+?(?<!\\)\$|\\\([\s\S]+?\\\)|\\\[[\s\S]+?\\\])/g;

function cleanText(text: string) {
  return text.replace(/\\"\{?o\}?/g, 'ö').replace(/\\\\/g, ' ');
}

export function MathText({ text }: { text: string }) {
  const parts = text.split(math);
  return <>{parts.map((part, index) => {
    if (index % 2 === 0) return <Fragment key={index}>{cleanText(part)}</Fragment>;
    const display = part.startsWith('$$') || part.startsWith('\\[');
    const expression = part.slice(display || part.startsWith('\\(') ? 2 : 1, display || part.endsWith('\\)') ? -2 : -1);
    const normalized = expression.replace(/\\unicode\{x2013\}/g, '\\text{–}');
    const html = katex.renderToString(normalized, {
      displayMode: display, throwOnError: false, trust: false,
      macros: { '\\tr': '\\operatorname{tr}', '\\Tr': '\\operatorname{Tr}', '\\Diag': '\\operatorname{Diag}', '\\mH': '\\mathbf{H}' },
    });
    return <span key={index} dangerouslySetInnerHTML={{ __html: html }} />;
  })}</>;
}
