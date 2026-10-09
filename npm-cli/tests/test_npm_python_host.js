"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const {
  findReadyPython,
  pythonCandidates,
  pythonInstallSpec,
  pythonSetupMessage,
  scrubInstallLog,
  venvFailureNeedsPython,
  hostToolInstallSpec,
  hostToolMessage,
  missingHostTools,
} = require("../npm/bin/clogem.js");

const DEBIAN_VENV_LOG = `
The virtual environment was not created successfully because ensurepip is not
available.  On Debian/Ubuntu systems, you need to install the python3-venv
package using the following command.

    apt install python3.12-venv
`;

test("macOS python search includes Homebrew before falling through", () => {
  const names = pythonCandidates("darwin", {});
  assert.equal(names[0], "python3");
  assert.ok(names.includes("/opt/homebrew/opt/python@3.12/bin/python3.12"));
  assert.ok(names.includes("/usr/local/opt/python@3.12/bin/python3.12"));
  assert.deepEqual(pythonCandidates("linux", {}), [
    "python3",
    "python3.13",
    "python3.12",
    "python3.11",
    "python3.10",
  ]);
});

test("CLOGEM_PYTHON stays the only candidate", () => {
  assert.deepEqual(pythonCandidates("darwin", { CLOGEM_PYTHON: "/custom/python" }), ["/custom/python"]);
});

test("the first interpreter that can import ensurepip wins", () => {
  const seen = [];
  const chosen = findReadyPython(["python3", "python3.12"], (cmd) => {
    seen.push(cmd);
    return { status: cmd === "python3.12" ? 0 : 1 };
  });
  assert.equal(chosen, "python3.12");
  assert.deepEqual(seen, ["python3", "python3.12"]);
});

test("install command follows the OS package manager", () => {
  const mac = pythonInstallSpec("darwin", (name) => name === "/opt/homebrew/bin/brew");
  assert.deepEqual(mac.cmd, ["/opt/homebrew/bin/brew", "install", "python@3.12"]);
  assert.equal(mac.needsTty, false);

  const linux = pythonInstallSpec("linux", (name) => name === "apt-get");
  assert.deepEqual(linux.cmd, ["sudo", "apt-get", "install", "-y", "python3", "python3-venv", "python3-pip"]);
  assert.equal(linux.needsTty, true);

  const fedora = pythonInstallSpec("linux", (name) => name === "dnf");
  assert.equal(fedora.cmd[0], "sudo");
  assert.equal(fedora.cmd[1], "dnf");

  assert.equal(pythonInstallSpec("darwin", () => false), null);
  assert.equal(pythonInstallSpec("win32", () => true), null);
  assert.equal(pythonInstallSpec("linux", () => false), null);
});

test("git curl and node follow the OS package manager", () => {
  const present = new Set(["git", "curl", "node", "npm"]);
  assert.deepEqual(missingHostTools((name) => (present.has(name) ? "/usr/bin/" + name : null)), []);

  const mac = hostToolInstallSpec("darwin", ["git", "node"], (name) =>
    name === "/opt/homebrew/bin/brew" ? true : false,
  );
  assert.deepEqual(mac.cmd, ["/opt/homebrew/bin/brew", "install", "git", "node"]);
  assert.doesNotMatch(hostToolMessage("darwin", ["git", "node"]), /apt-get/);

  const linux = hostToolInstallSpec("linux", ["curl", "npm"], (name) => name === "apt-get");
  assert.deepEqual(linux.cmd, ["sudo", "apt-get", "install", "-y", "curl", "ca-certificates", "nodejs", "npm"]);
  assert.equal(hostToolInstallSpec("linux", [], () => true), null);
});

test("macOS instructions never tell the user to run apt", () => {
  for (const hasBrew of [true, false]) {
    const text = pythonSetupMessage("darwin", hasBrew);
    assert.match(text, /brew install python@3\.12/);
    assert.doesNotMatch(text, /apt install|apt-get/);
    assert.match(text, /Mac does not use apt/);
  }
  assert.match(pythonSetupMessage("linux", false), /apt-get install/);
  assert.match(scrubInstallLog("darwin", DEBIAN_VENV_LOG), /^$/);
  assert.match(scrubInstallLog("linux", DEBIAN_VENV_LOG), /apt install python3\.12-venv/);
  assert.equal(venvFailureNeedsPython(DEBIAN_VENV_LOG), true);
  assert.equal(venvFailureNeedsPython("No space left on device"), false);
});
