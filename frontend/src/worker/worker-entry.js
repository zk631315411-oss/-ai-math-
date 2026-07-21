// Worker 线程 Polyfill — 主线程的 index.html polyfill 对 Worker 无效
if (!Promise.withResolvers) {
  Promise.withResolvers = function () {
    let resolve, reject;
    const promise = new Promise(function (res, rej) {
      resolve = res;
      reject = rej;
    });
    return { promise, resolve, reject };
  };
}

// 加载 v5 ES Module worker（esbuild 会将其转为 IIFE，版本与 react-pdf 的 core 一致）
import 'pdfjs-dist/build/pdf.worker.min.mjs';
