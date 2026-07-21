import * as esbuild from 'esbuild';

await esbuild.build({
  entryPoints: ['src/worker/worker-entry.js'],
  bundle: true,
  format: 'iife',
  target: 'es2016',
  outfile: 'public/pdf.worker.js',
  minify: true,
  define: {
    // pdfjs worker 不需要这些 Node API
    'globalThis.process': 'undefined',
  },
});

console.log('Worker built: public/pdf.worker.js');
