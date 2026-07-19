type Props = {
  state: string;
};

function variant(state: string): string {
  if (state === "SUCCESS") return "status-pulse--success";
  if (state === "FAILURE") return "status-pulse--failure";
  if (state === "PENDING") return "status-pulse--pending";
  if (state === "STARTED" || state === "RUNNING") return "status-pulse--active";
  return "";
}

export function StatusPulse({ state }: Props) {
  return (
    <span className={`status-pulse ${variant(state)}`}>
      <span className="status-pulse__dot" />
      {state}
    </span>
  );
}
