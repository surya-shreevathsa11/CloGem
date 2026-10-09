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

const PYTHON_READY =
  "import ensurepip, sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)";

function pythonCandidates(platform, env = {}) {
  if (env.CLOGEM_PYTHON) {
    return [env.CLOGEM_PYTHON];
  }
  const names =
    platform === "win32"
      ? ["python", "py", "python3"]
      : ["python3", "python3.13", "python3.12", "python3.11", "python3.10"];
  if (platform === "darwin") {
    names.push(
      "/opt/homebrew/bin/python3.13",
      "/opt/homebrew/bin/python3.12",
      "/opt/homebrew/opt/python@3.13/bin/python3.13",
      "/opt/homebrew/opt/python@3.12/bin/python3.12",
      "/usr/local/bin/python3.13",
      "/usr/local/bin/python3.12",
      "/usr/local/opt/python@3.13/bin/python3.13",
      "/usr/local/opt/python@3.12/bin/python3.12",
    );
  }
  return names;
}

function findReadyPython(candidates, spawnImpl = spawnSync) {
  for (const candidate of candidates) {
    const check = spawnImpl(candidate, ["-c", PYTHON_READY], { stdio: "ignore" });
    if (check && check.status === 0) {
      return candidate;
    }
  }
  return null;
}

function commandOnPath(name) {
  if (name.startsWith("/") || /^[A-Za-z]:[\\/]/.test(name)) {
    return fs.existsSync(name);
  }
  const finder = process.platform === "win32" ? "where" : "which";
  return spawnSync(finder, [name], { stdio: "ignore" }).status === 0;
}

function pythonInstallSpec(platform, commandExists) {
  if (platform === "darwin") {
    const brew =
      ["/opt/homebrew/bin/brew", "/usr/local/bin/brew"].find((item) => commandExists(item)) ||
      (commandExists("brew") ? "brew" : null);
    if (!brew) {
      return null;
    }
    return {
      cmd: [brew, "install", "python@3.12"],
      label: "Installing Python with Homebrew",
      needsTty: false,
    };
  }
  if (platform === "win32") {
    return null;
  }
  if (commandExists("apt-get")) {
    return {
      cmd: ["sudo", "apt-get", "install", "-y", "python3", "python3-venv", "python3-pip"],
      label: "Installing Python with apt",
      needsTty: true,
    };
  }
  if (commandExists("dnf")) {
    return {
      cmd: ["sudo", "dnf", "install", "-y", "python3"],
      label: "Installing Python with dnf",
      needsTty: true,
    };
  }
  if (commandExists("pacman")) {
    return {
      cmd: ["sudo", "pacman", "-S", "--noconfirm", "python"],
      label: "Installing Python with pacman",
      needsTty: true,
    };
  }
  return null;
}

function pythonSetupMessage(platform, hasBrew) {
  if (platform === "darwin") {
    const lines = [
      "Python 3.10 or newer, with the venv module, is required.",
      "A Mac does not use apt. Install Python with Homebrew:",
    ];
    if (!hasBrew) {
      lines.push(
        '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"',
      );
    }
    lines.push("  brew install python@3.12", "Or download the macOS installer: https://www.python.org/downloads/macos/", "Then run clogem again.");
    return lines.join("\n");
  }
  if (platform === "win32") {
    return [
      "Python 3.10 or newer is required.",
      "Install it from https://www.python.org/downloads/ and turn on Add python.exe to PATH.",
      "Then run clogem again.",
    ].join("\n");
  }
  return [
    "Python 3.10 or newer, with the venv module, is required.",
    "Debian or Ubuntu: sudo apt-get install -y python3 python3-venv python3-pip",
    "Fedora: sudo dnf install -y python3",
    "Arch: sudo pacman -S python",
    "Then run clogem again.",
  ].join("\n");
}

function scrubInstallLog(platform, log) {
  const text = String(log || "").trim();
  if (!text) {
    return "";
  }
  if (platform !== "linux" && /debian|ubuntu|apt install|apt-get/i.test(text)) {
    return "";
  }
  return text;
}

function venvFailureNeedsPython(log) {
  return /ensurepip|python3-venv|no module named ['"]venv['"]|debian\/ubuntu/i.test(String(log || ""));
}

const HOST_TOOLS = ["git", "curl", "node", "npm"];

function missingHostTools(commandExists) {
  return HOST_TOOLS.filter((name) => !commandExists(name));
}

function hostToolInstallSpec(platform, missing, commandExists) {
  if (!missing.length) {
    return null;
  }
  if (platform === "darwin") {
    const brew =
      ["/opt/homebrew/bin/brew", "/usr/local/bin/brew"].find((item) => commandExists(item)) ||
      (commandExists("brew") ? "brew" : null);
    if (!brew) {
      return null;
    }
    const packages = [];
    if (missing.includes("git")) packages.push("git");
    if (missing.includes("curl")) packages.push("curl");
    if (missing.includes("node") || missing.includes("npm")) packages.push("node");
    if (!packages.length) {
      return null;
    }
    return {
      cmd: [brew, "install", ...packages],
      label: "Installing git, curl, and Node with Homebrew",
      needsTty: false,
    };
  }
  if (platform === "win32") {
    return null;
  }
  const packages = [];
  if (missing.includes("git")) packages.push("git");
  if (missing.includes("curl")) packages.push("curl", "ca-certificates");
  if (missing.includes("node") || missing.includes("npm")) packages.push("nodejs", "npm");
  if (!packages.length) {
    return null;
  }
  if (commandExists("apt-get")) {
    return {
      cmd: ["sudo", "apt-get", "install", "-y", ...packages],
      label: "Installing git, curl, and Node with apt",
      needsTty: true,
    };
  }
  if (commandExists("dnf")) {
    return {
      cmd: ["sudo", "dnf", "install", "-y", ...packages],
      label: "Installing git, curl, and Node with dnf",
      needsTty: true,
    };
  }
  if (commandExists("pacman")) {
    return {
      cmd: ["sudo", "pacman", "-S", "--noconfirm", ...packages],
      label: "Installing git, curl, and Node with pacman",
      needsTty: true,
    };
  }
  return null;
}

function hostToolMessage(platform, missing) {
  if (platform === "darwin") {
    const names = [];
    if (missing.includes("git")) names.push("git");
    if (missing.includes("curl")) names.push("curl");
    if (missing.includes("node") || missing.includes("npm")) names.push("node");
    return `On a Mac, install them with Homebrew:\n  brew install ${names.join(" ")}`;
  }
  if (platform === "win32") {
    return "Install Git, curl, and Node.js 18 or newer, then run clogem again.";
  }
  const packages = [];
  if (missing.includes("git")) packages.push("git");
  if (missing.includes("curl")) packages.push("curl", "ca-certificates");
  if (missing.includes("node") || missing.includes("npm")) packages.push("nodejs", "npm");
  return `Install them with the system package manager, for example:\n  sudo apt-get install -y ${packages.join(" ")}`;
}

function ensureHostTools() {
  const missing = missingHostTools(commandOnPath);
  if (!missing.length) {
    return;
  }
  const spec = hostToolInstallSpec(process.platform, missing, commandOnPath);
  if (!spec || (spec.needsTty && !process.stdin.isTTY)) {
    console.error(hostToolMessage(process.platform, missing));
    return;
  }
  console.error(spec.label);
  const result = spawnSync(spec.cmd[0], spec.cmd.slice(1), { stdio: "inherit" });
  if (result.error || result.status !== 0) {
    console.error(hostToolMessage(process.platform, missing));
  }
}

let triedHostPythonInstall = false;

function tryHostPythonInstall() {
  if (triedHostPythonInstall || process.env.CLOGEM_PYTHON) {
    return false;
  }
  triedHostPythonInstall = true;
  const spec = pythonInstallSpec(process.platform, commandOnPath);
  if (!spec || (spec.needsTty && !process.stdin.isTTY)) {
    return false;
  }
  console.error(spec.label);
  const result = spawnSync(spec.cmd[0], spec.cmd.slice(1), { stdio: "inherit" });
  return !result.error && result.status === 0;
}

function ensurePython() {
  const platform = process.platform;
  const ready = () => findReadyPython(pythonCandidates(platform, process.env));
  let python = ready();
  if (python) {
    return python;
  }
  if (process.env.CLOGEM_PYTHON) {
    fail(`CLOGEM_PYTHON is not usable (need Python 3.10+ with venv): ${process.env.CLOGEM_PYTHON}`);
  }
  tryHostPythonInstall();
  python = ready();
  if (python) {
    return python;
  }
  const hasBrew = platform === "darwin" && pythonInstallSpec(platform, commandOnPath) != null;
  fail(pythonSetupMessage(platform, hasBrew));
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
  const python = ensurePython();
  ensureHostTools();
  fs.mkdirSync(dataDir, { recursive: true });
  fs.rmSync(appDir, { recursive: true, force: true });
  fs.mkdirSync(appDir, { recursive: true });
  for (const name of ["clogem", ".ai", "pyproject.toml", "setup.py", "README.md"]) {
    copyTree(path.join(pkgRoot, name), path.join(appDir, name));
  }
  if (!fs.existsSync(venvPython())) {
    let created = await runQuiet(python, ["-m", "venv", venvDir], "preparing");
    if (created.code !== 0 && venvFailureNeedsPython(created.log)) {
      fs.rmSync(venvDir, { recursive: true, force: true });
      if (tryHostPythonInstall()) {
        const repaired = findReadyPython(pythonCandidates(process.platform, process.env));
        if (repaired) {
          created = await runQuiet(repaired, ["-m", "venv", venvDir], "preparing");
        }
      }
    }
    if (created.code !== 0) {
      const needsPython = venvFailureNeedsPython(created.log);
      const log = scrubInstallLog(process.platform, created.log);
      if (log) {
        console.error(log);
      }
      if (needsPython) {
        const hasBrew = process.platform === "darwin" && pythonInstallSpec(process.platform, commandOnPath) != null;
        console.error(pythonSetupMessage(process.platform, hasBrew));
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

async function updateClogem() {
  const npm = process.platform === "win32" ? "npm.cmd" : "npm";
  const result = await runQuiet(npm, ["update", "-g", "@shywolf/clogem"], "updating");
  if (result.code !== 0) {
    const tail = (result.log || "").trim().split("\n").slice(-8).join("\n");
    if (tail) {
      console.error(tail);
    }
    fail("Could not update. Try: npm install -g @shywolf/clogem");
  }
  fs.rmSync(versionFile, { force: true });
  fs.rmSync(appDir, { recursive: true, force: true });
  if (process.stdout.isTTY) {
    process.stdout.write("\x1b[38;2;190;85;85m  updated\x1b[0m\n");
  } else {
    process.stdout.write("updated\n");
  }
  process.exit(0);
}

async function main() {
  if (process.argv[2] === "update") {
    await updateClogem();
    return;
  }
  await ensureApp();
  const args = process.argv.slice(2).filter((arg) => arg !== "--skip-setup");
  const marker = path.join(dataDir, "setup-done");
  const wantsSetup = args[0] === "setup" || args[0] === "key";
  const firstRun = process.stdin.isTTY && !fs.existsSync(marker) && !wantsSetup && !process.argv.includes("--skip-setup");
  if (firstRun) {
    const status = run(venvClogem(), ["setup"]);
    if (status !== 0) {
      process.exit(status);
    }
  }
  process.exit(run(venvClogem(), args));
}

if (require.main === module) {
  main();
}

module.exports = {
  PYTHON_READY,
  findReadyPython,
  pythonCandidates,
  pythonInstallSpec,
  pythonSetupMessage,
  scrubInstallLog,
  venvFailureNeedsPython,
  missingHostTools,
  hostToolInstallSpec,
  hostToolMessage,
};
