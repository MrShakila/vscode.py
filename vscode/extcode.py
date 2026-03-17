'''// Built using vscode.py
const vscode = require("vscode");
const { spawn, execSync } = require("child_process");
const path = require("path");
const pythonExtensionPath = path.join(__dirname, "extension.py");
const requirementsPath = path.join(__dirname, "requirements.txt");

const wslib = require("ws");
const fs = require("fs");
let ws;

function commandCallback(command) {
  if (ws && ws.readyState == 1) {
    ws.send(JSON.stringify({ type: 1, name: command }));
  } else {
    setTimeout(() => commandCallback(command), 50);
  }
}

// func: registerCommands

function getPythonPath() {
  const venvPath = path.join(__dirname, "venv");
  const pythonBin = process.platform === "win32" ? "Scripts/python.exe" : "bin/python";
  const fullPath = path.join(venvPath, pythonBin);
  if (fs.existsSync(fullPath)) {
    return fullPath;
  }
  return null;
}

function findPython(extensionName) {
  const commands = [
    vscode.workspace.getConfiguration(extensionName).get("pythonPath"),
    vscode.workspace.getConfiguration("python").get("defaultInterpreterPath"),
    vscode.workspace.getConfiguration("python").get("pythonPath"),
    "python3",
    "python",
    "py"
  ];
  for (const cmd of commands) {
    if (!cmd) continue;
    try {
      execSync(`${cmd} --version`, { stdio: 'ignore' });
      return cmd;
    } catch (e) {
      // ignore
    }
  }
  return null;
}

async function activate(context) {
  registerCommands(context);

  const pkg = JSON.parse(fs.readFileSync(path.join(__dirname, "package.json"), "utf8"));
  const extensionName = pkg.name;

  let pyVar = findPython(extensionName);
  if (!pyVar) {
    vscode.window.showErrorMessage("Python was not found. Please install Python to use this extension.");
    return;
  }

  let venvPath = path.join(__dirname, "./venv");
  let createvenvPath = path.join(venvPath, "createvenv.txt");
  let shouldInstall = false;

  if (!fs.existsSync(createvenvPath)) {
    try {
      console.log("Creating virtual environment...");
      execSync(`${pyVar} -m venv ${venvPath}`);
      fs.writeFileSync(
        createvenvPath,
        "Delete this file only if you want to recreate the venv! Do not include this file when you package/publish the extension."
      );
      shouldInstall = true;
    } catch (e) {
      vscode.window.showErrorMessage("Failed to create virtual environment: " + e.message);
      return;
    }
  }

  pyVar = getPythonPath() || pyVar;

  const lastInstallPath = path.join(venvPath, "last_install.txt");
  if (!shouldInstall && fs.existsSync(requirementsPath)) {
      if (!fs.existsSync(lastInstallPath)) {
          shouldInstall = true;
      } else {
          const reqMtime = fs.statSync(requirementsPath).mtimeMs;
          const lastMtime = fs.statSync(lastInstallPath).mtimeMs;
          if (reqMtime > lastMtime) {
              shouldInstall = true;
          }
      }
  }

  if (shouldInstall && fs.existsSync(requirementsPath)) {
    try {
      console.log("Installing dependencies...");
      execSync(`${pyVar} -m pip install -r ${requirementsPath}`);
      fs.writeFileSync(lastInstallPath, new Date().toISOString());
    } catch (e) {
      vscode.window.showWarningMessage("Failed to install dependencies: " + e.message);
    }
  }

  let py = spawn(pyVar, [pythonExtensionPath, "--run-webserver"]);
  let webviews = {};
  let progressRecords = {};

  py.stdout.on("data", (data) => {
    let mes = data.toString().trim();
    if (ws) {
      console.log(mes);
    }
    let arr = mes.split(" ");
    if (arr.length >= 3 && arr[arr.length - 1].startsWith("ws://localhost:")) {
      const uri = arr[arr.length - 1];
      ws = new wslib.WebSocket(uri);
      console.log("Connecting to " + uri);
      ws.on("open", () => {
        console.log("Connected!");
        ws.send(JSON.stringify({ type: 2, event: "activate" }));
      });
      ws.on("message", async (message) => {
        console.log("received: %s", message.toString());
        try {
          let data = JSON.parse(message.toString());
          if (data.type == 1) {
            eval(data.code);
          } else if (data.type == 2) {
            eval(
              data.code +
                `.then(res => ws.send(JSON.stringify({ type: 3, res, uuid: "${data.uuid}" })));`
            );
          } else if (data.type == 3) {
            let res = eval(data.code);
            ws.send(JSON.stringify({ type: 3, res, uuid: data.uuid }));
          }
        } catch (e) {
          console.log(e);
        }
      });

      ws.on("close", () => {
        console.log("Connection closed!");
      });
    }
  });
  py.stderr.on("data", (data) => {
    console.error(`An Error occurred in the python script: ${data}`);
  });

  py.on('close', (code) => {
      console.log(`Python process exited with code ${code}`);
  });
}

function deactivate() {}

module.exports = { activate, deactivate };
'''