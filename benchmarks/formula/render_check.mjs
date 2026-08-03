import katex from '../../frontend/node_modules/katex/dist/katex.mjs';

let input = '';
for await (const chunk of process.stdin) input += chunk;
const formulas = JSON.parse(input);
const result = formulas.map((latex) => {
  try {
    katex.renderToString(latex, { throwOnError: true, strict: 'error' });
    return true;
  } catch {
    return false;
  }
});
process.stdout.write(JSON.stringify(result));
