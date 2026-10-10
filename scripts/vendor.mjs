// Copy third-party frontend files from node_modules into static/vendor so the
// site never depends on external CDNs at runtime.
import { copyFileSync, mkdirSync } from "node:fs";

const files = [
  ["node_modules/htmx.org/dist/htmx.min.js", "static/vendor/htmx/htmx.min.js"],
  ["node_modules/vazirmatn/fonts/webfonts/Vazirmatn[wght].woff2", "static/vendor/vazirmatn/Vazirmatn-Variable.woff2"],
  ["node_modules/vazirmatn/OFL.txt", "static/vendor/vazirmatn/OFL.txt"],
];

for (const [src, dest] of files) {
  mkdirSync(dest.slice(0, dest.lastIndexOf("/")), { recursive: true });
  copyFileSync(src, dest);
  console.log(`vendored ${dest}`);
}
