const { bundle } = require("@remotion/bundler");
const { renderMedia, selectComposition } = require("@remotion/renderer");
const path = require("path");
const fs = require("fs");

async function start() {
  const args = process.argv.slice(2);
  const propsArg = args[0] ? JSON.parse(args[0]) : {};

  console.log("📦 Bundling Remotion video...");
  const bundled = await bundle({
    entryPoint: path.resolve("./src/index.ts"),
    webpackOverride: (config) => config,
  });

  console.log("🎬 Selecting composition...");
  const composition = await selectComposition({
    serveUrl: bundled,
    id: "HelloWorld",
    inputProps: propsArg,
  });

  console.log("🚀 Rendering video...");
  const outputLocation = path.resolve("../output_deal.mp4");
  await renderMedia({
    composition,
    serveUrl: bundled,
    codec: "h264",
    outputLocation,
    inputProps: propsArg,
  });

  console.log(`✅ Video rendered successfully at: ${outputLocation}`);
}

start().catch((err) => {
  console.error("❌ Error rendering video:", err);
  process.exit(1);
});
