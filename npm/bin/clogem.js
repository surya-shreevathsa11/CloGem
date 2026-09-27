#!/usr/bin/env node
"use strict";

const { spawn, spawnSync } = require("child_process");
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

function runQuiet(cmd, args, label) {
  const rose = "\x1b[38;2;190;85;85m";
  const soft = "\x1b[38;2;255;175;175m";
  const reset = "\x1b[0m";
  const frames = ["·  ", "·· ", "···", " ··", "  ·"];
  const tty = process.stdout.isTTY;

  return new Promise((resolve) => {
    let frame = 0;
    const timer = tty
      ? setInterval(() => {
          process.stdout.write(`\r${rose}  ${label} ${soft}${frames[frame % frames.length]}${reset}`);
          frame += 1;
        }, 180)
      : null;
    if (!tty) {
      process.stdout.write(`${label}\n`);
    }
    const child = spawn(cmd, args, {
      env: {
        ...process.env,
        PIP_DISABLE_PIP_VERSION_CHECK: "1",
        PIP_PROGRESS_BAR: "off",
        PIP_NO_COLOR: "1",
      },
      stdio: ["ignore", "pipe", "pipe"],
    });
    let log = "";
    child.stdout.on("data", (chunk) => {
      log += chunk;
    });
    child.stderr.on("data", (chunk) => {
      log += chunk;
    });
    child.on("error", (err) => {
      if (timer) {
        clearInterval(timer);
      }
      process.stdout.write("\r\x1b[2K");
      resolve({ code: 1, log: err.message });
    });
    child.on("close", (code) => {
      if (timer) {
        clearInterval(timer);
      }
      if (tty) {
        process.stdout.write("\r\x1b[2K");
      }
      resolve({ code: code == null ? 1 : code, log });
    });
  });
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

async function ensureApp() {
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
    const created = await runQuiet(python, ["-m", "venv", venvDir], "preparing");
    if (created.code !== 0) {
      if (created.log.trim()) {
        console.error(created.log.trim());
      }
      fail("Could not create a virtualenv.");
    }
  }
  const installedPkg = await runQuiet(
    venvPython(),
    ["-m", "pip", "install", "-q", "--progress-bar", "off", "--disable-pip-version-check", "-e", appDir],
    "installing",
  );
  if (installedPkg.code !== 0) {
    const tail = installedPkg.log.trim().split("\n").slice(-20).join("\n");
    if (tail) {
      console.error(tail);
    }
    fail("Could not install the Clogem Python package.");
  }
  if (process.stdout.isTTY) {
    process.stdout.write("\x1b[38;2;190;85;85m  ready\x1b[0m\n");
  }
  fs.writeFileSync(versionFile, `${version}\n`);
}

async function main() {
  await ensureApp();
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
