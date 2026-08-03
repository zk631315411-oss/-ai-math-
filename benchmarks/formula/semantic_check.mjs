import { ComputeEngine } from '../../frontend/node_modules/@cortex-js/compute-engine/dist/esm-min/compute-engine.js';

const engine = new ComputeEngine();

function normalizeLatex(value) {
  return value
    .replace(/\\(?:left|right)/g, '')
    .replace(/\\[dt]frac/g, '\\frac')
    .replace(/\\leqslant/g, '\\le')
    .replace(/\\geqslant/g, '\\ge')
    .replace(/\\leq/g, '\\le')
    .replace(/\\geq/g, '\\ge')
    .replace(/\\neq/g, '\\ne')
    .replace(/\\emptyset/g, '\\varnothing')
    .replace(/\\operatorname\{(sin|cos|tan|log|ln|lim)\}/g, '\\$1')
    .replace(/\s+/g, '');
}

function containsError(value) {
  if (Array.isArray(value)) {
    return value[0] === 'Error' || value.some(containsError);
  }
  if (value && typeof value === 'object') {
    return Object.values(value).some(containsError);
  }
  return false;
}

function mathJson(value) {
  try {
    const json = engine.parse(value, { canonical: true }).canonical.json;
    return containsError(json) ? null : json;
  } catch {
    return null;
  }
}

function splitTopLevel(value, separator) {
  const parts = [];
  let start = 0;
  let braces = 0;
  for (let index = 0; index < value.length; index += 1) {
    if (value[index] === '{') braces += 1;
    if (value[index] === '}') braces -= 1;
    if (braces === 0 && value.startsWith(separator, index)) {
      parts.push(value.slice(start, index));
      index += separator.length - 1;
      start = index + 1;
    }
  }
  parts.push(value.slice(start));
  return parts;
}

function structuralMathJson(value) {
  const normalized = value.replace(/\\(?:left|right)/g, '').trim();
  const match = normalized.match(/^\\begin\{([A-Za-z*]+)\}([\s\S]*)\\end\{\1\}$/);
  if (!match) return null;

  const rows = splitTopLevel(match[2].trim(), '\\\\').map((row) =>
    splitTopLevel(row, '&').map((cell) => {
      const parsed = mathJson(cell.trim());
      return parsed ?? ['Unparsed', normalizeLatex(cell)];
    }),
  );
  return { environment: match[1], rows };
}

function semanticEquivalent(actual, expected) {
  if (normalizeLatex(actual) === normalizeLatex(expected)) {
    return { equivalent: true, method: 'normalized' };
  }

  const actualStructure = structuralMathJson(actual);
  const expectedStructure = structuralMathJson(expected);
  if (actualStructure || expectedStructure) {
    return {
      equivalent: Boolean(actualStructure && expectedStructure)
        && JSON.stringify(actualStructure) === JSON.stringify(expectedStructure),
      method: 'structure',
    };
  }

  const actualJson = mathJson(actual);
  const expectedJson = mathJson(expected);
  return {
    equivalent: Boolean(actualJson && expectedJson)
      && JSON.stringify(actualJson) === JSON.stringify(expectedJson),
    method: actualJson && expectedJson ? 'mathjson' : 'unscorable',
  };
}

let input = '';
for await (const chunk of process.stdin) input += chunk;
const rows = JSON.parse(input);
process.stdout.write(JSON.stringify(rows.map(({ actual, expected }) => semanticEquivalent(actual, expected))));
