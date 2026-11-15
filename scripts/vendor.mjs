// Bundle the dashboard's browser libraries into app/static/vendor/.
//
// The dashboard (app/static/index.html) has no frontend build, so each library
// is pre-bundled here into one self-contained IIFE that the page loads with a
// plain <script>. The outputs are committed; re-run `npm run vendor` only after
// changing versions in package.json.
import { build } from 'esbuild';
import { readFileSync } from 'node:fs';

const pkg = (name) => JSON.parse(readFileSync(new URL(`../node_modules/${name}/package.json`, import.meta.url)));
const outdir = new URL('../app/static/vendor/', import.meta.url).pathname;

const bundles = [
  {
    // Paper Shaders (vanilla ShaderMount) -> window.PaperShaders
    out: 'paper-shaders.js', name: '@paper-design/shaders',
    contents: `export { ShaderMount, meshGradientFragmentShader, getShaderColorFromString, ShaderFitOptions, defaultObjectSizing } from '@paper-design/shaders';`,
    globalName: 'PaperShaders',
  },
  {
    // NumberFlow: registers the <number-flow> custom element
    out: 'number-flow.js', name: 'number-flow',
    contents: `import 'number-flow';`,
  },
  {
    // GSAP core + ScrambleTextPlugin -> window.gsap
    out: 'gsap-scramble.js', name: 'gsap',
    contents: `import { gsap } from 'gsap'; import { ScrambleTextPlugin } from 'gsap/ScrambleTextPlugin';
gsap.registerPlugin(ScrambleTextPlugin); window.gsap = gsap;`,
  },
];

for (const b of bundles) {
  const { version, license } = pkg(b.name);
  await build({
    stdin: { contents: b.contents, resolveDir: process.cwd(), loader: 'js' },
    bundle: true, minify: true, format: 'iife', globalName: b.globalName,
    target: ['es2020'], outfile: outdir + b.out, legalComments: 'none',
    banner: { js: `/* ${b.name}@${version} (${typeof license === 'string' ? license : 'see package'}) — bundled by scripts/vendor.mjs; do not edit. */` },
  });
  console.log(`vendored ${b.name}@${version} -> app/static/vendor/${b.out}`);
}
