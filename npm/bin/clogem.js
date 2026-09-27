#!/usr/bin/env node
"use strict";

const { spawnSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

const pkgRoot = path.resolve(__dirname, "..", "..");
const dataDir = path.join(os.homedir(), ".local", "share", "clogem");
const appDir = path.join(dataDir, "app");
const venvDir = path.join(dataDir, "venv");
const versionFile = path.join(dataDir, "installed-version");

function fail(message) {
  console.error(`clogem: ${message}`);
  process.exit(1);
}

function pythonLauncher() {
  if (process.env.CLOGEM_PYTHON) {
    return process.env.CLOGEM_PYTHON;
  }
  return process.platform === "win32" ? "python" : "python3";
}

function venvPython() {
  return process.platform === "win32"
    ? path.join(venvDir, "Scripts", "python.exe")
    : path.join(venvDir, "bin", "python");
}

function venvClogem() {
  return process.platform === "win32"
    ? path.join(venvDir, "Scripts", "clogem.exe")
    : path.join(venvDir, "bin", "clogem");
}

function run(cmd, args) {
  const result = spawnSync(cmd, args, { stdio: "inherit" });
  if (result.error) {
    fail(result.error.message);
  }
  return result.status == null ? 1 : result.status;
}

function pythonIsNewEnough(python) {
  const check = spawnSync(python, [
    "-c",
    "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)",
  ]);
  return check.status === 0;
}

function copyTree(from, to) {
  fs.cpSync(from, to, {
    recursive: true,
    filter(src) {
      return !src.split(path.sep).includes("__pycache__") && !src.endsWith(".pyc");
    },
  });
}

function ensureApp() {
  const version = JSON.parse(fs.readFileSync(path.join(pkgRoot, "package.json"), "utf8")).version;
  let installed = "";
  try {
    installed = fs.readFileSync(versionFile, "utf8").trim();
  } catch (_err) {
    installed = "";
  }
  if (installed === version && fs.existsSync(venvClogem())) {
    return;
  }
  const python = pythonLauncher();
  if (!pythonIsNewEnough(python)) {
    fail("Python 3.10+ is required. Install it, then run clogem again.");
  }
  fs.mkdirSync(dataDir, { recursive: true });
  fs.rmSync(appDir, { recursive: true, force: true });
  fs.mkdirSync(appDir, { recursive: true });
  for (const name of ["clogem", ".ai", "pyproject.toml", "setup.py", "README.md"]) {
    copyTree(path.join(pkgRoot, name), path.join(appDir, name));
  }
  if (!fs.existsSync(venvPython())) {
    if (run(python, ["-m", "venv", venvDir]) !== 0) {
      fail("Could not create a virtualenv.");
    }
  }
  if (run(venvPython(), ["-m", "pip", "install", "-e", appDir]) !== 0) {
    fail("Could not install the Clogem Python package.");
  }
  fs.writeFileSync(versionFile, `${version}\n`);
}

function main() {
  ensureApp();
  const args = process.argv.slice(2).filter((arg) => arg !== "--skip-setup");
  const marker = path.join(dataDir, "setup-done");
  const wantsSetup = args[0] === "setup";
  const firstRun = process.stdin.isTTY && !fs.existsSync(marker) && !wantsSetup && !process.argv.includes("--skip-setup");
  if (firstRun) {
    const status = run(venvClogem(), ["setup"]);
    if (status !== 0) {
      process.exit(status);
    }
  }
  process.exit(run(venvClogem(), args));
}

main();
