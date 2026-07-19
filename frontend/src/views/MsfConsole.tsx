import { useCallback, useEffect, useRef, useState } from "react";
import { getSocket } from "../api/socket";
import { ConfirmDialog } from "../components/ConfirmDialog";

export function MsfConsole() {
  const [consoleId, setConsoleId] = useState<string | null>(null);
  const [output, setOutput] = useState("");
  const [command, setCommand] = useState("");
  const [status, setStatus] = useState("closed");
  const [confirmClose, setConfirmClose] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const terminalRef = useRef<HTMLDivElement>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const startPolling = useCallback(
    (id: string) => {
      stopPolling();
      const socket = getSocket();
      pollRef.current = setInterval(() => {
        socket.emit("msf_console_read", { console_id: id });
      }, 1000);
    },
    [stopPolling],
  );

  useEffect(() => {
    const socket = getSocket();

    const onCreated = (data: { console?: { id?: string | number; prompt?: string } }) => {
      const id = data.console?.id != null ? String(data.console.id) : null;
      setConsoleId(id);
      setStatus(id ? `open:${id}` : "closed");
      if (data.console?.prompt) {
        setOutput((prev) => prev + data.console!.prompt);
      }
      if (id) startPolling(id);
    };

    const onOutput = (data: {
      console_id?: string;
      output?: { data?: string; prompt?: string };
    }) => {
      const chunk = data.output?.data ?? "";
      const prompt = data.output?.prompt ?? "";
      if (chunk || prompt) {
        setOutput((prev) => prev + chunk + prompt);
      }
    };

    const onDestroyed = (data: { console_id?: string }) => {
      if (!data.console_id || data.console_id === consoleId) {
        stopPolling();
        setConsoleId(null);
        setStatus("closed");
      }
    };

    const onError = (data: { error?: string }) => {
      setOutput((prev) => prev + `\n[ERROR] ${data.error ?? "Console error"}\n`);
    };

    socket.on("msf_console_created", onCreated);
    socket.on("msf_console_output", onOutput);
    socket.on("msf_console_destroyed", onDestroyed);
    socket.on("msf_console_error", onError);

    return () => {
      socket.off("msf_console_created", onCreated);
      socket.off("msf_console_output", onOutput);
      socket.off("msf_console_destroyed", onDestroyed);
      socket.off("msf_console_error", onError);
      stopPolling();
    };
  }, [consoleId, startPolling, stopPolling]);

  useEffect(() => {
    const el = terminalRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [output]);

  useEffect(() => {
    return () => {
      if (consoleId) {
        getSocket().emit("msf_console_destroy", { console_id: consoleId });
      }
    };
  }, [consoleId]);

  function openConsole() {
    if (consoleId) return;
    setOutput("");
    getSocket().emit("msf_console_create", {});
  }

  function destroyConsole() {
    if (!consoleId) return;
    stopPolling();
    getSocket().emit("msf_console_destroy", { console_id: consoleId });
    setConsoleId(null);
    setStatus("closed");
  }

  function sendCommand() {
    if (!consoleId || !command.trim()) return;
    getSocket().emit("msf_console_write", {
      console_id: consoleId,
      command,
    });
    setCommand("");
  }

  return (
    <div>
      <h2>MSF Console</h2>
      <div className="panel">
        <div className="row">
          <button
            type="button"
            className="btn btn--primary"
            onClick={openConsole}
            disabled={consoleId !== null}
          >
            Open Console
          </button>
          <button
            type="button"
            className="btn btn--danger"
            onClick={() => setConfirmClose(true)}
            disabled={!consoleId}
          >
            Close Console
          </button>
          <span className="badge">{status}</span>
        </div>
        <div ref={terminalRef} className="terminal">
          {output || "Console idle."}
        </div>
        <div className="row" style={{ marginTop: "0.75rem" }}>
          <input
            type="text"
            placeholder="msf command"
            value={command}
            onChange={(e) => setCommand(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") sendCommand();
            }}
            disabled={!consoleId}
          />
          <button
            type="button"
            className="btn"
            onClick={sendCommand}
            disabled={!consoleId}
          >
            Send
          </button>
        </div>
      </div>

      <ConfirmDialog
        open={confirmClose}
        title="Close MSF Console"
        message="Destroy the active Metasploit console session?"
        confirmLabel="Close"
        onConfirm={() => {
          destroyConsole();
          setConfirmClose(false);
        }}
        onCancel={() => setConfirmClose(false)}
      />
    </div>
  );
}
