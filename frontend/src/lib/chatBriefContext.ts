import type { ChatMessage, MissionProposal } from "../api/client";
import { isOsintToolList, type BriefReplyContext } from "../lib/chatMessageDisplay";

export function briefContextForChatMessage(
  message: ChatMessage,
  opts: {
    isLatestAssistant: boolean;
    draft: MissionProposal | null;
    hasToolDraft: boolean;
    launchError: string | null;
    missionLaunched?: boolean;
  },
): BriefReplyContext | undefined {
  if (message.role !== "assistant") return undefined;

  if (message.mission_card) {
    return {
      missionLaunched: true,
      target: message.mission_card.target,
    };
  }

  const proposal =
    message.proposal ?? (opts.isLatestAssistant ? opts.draft : null);

  if (opts.isLatestAssistant && opts.missionLaunched) {
    return {
      missionLaunched: true,
      target: proposal?.target,
    };
  }

  if (opts.isLatestAssistant && opts.launchError) {
    return {
      launchError: opts.launchError,
      target: proposal?.target,
      needsConfirm: proposal?.ready,
      osintOnly: isOsintToolList(proposal?.plan?.tool_names),
    };
  }

  if (opts.isLatestAssistant && opts.hasToolDraft) {
    return { toolProposal: true };
  }

  if (proposal?.ready) {
    return {
      target: proposal.target,
      needsConfirm: !proposal.auto_execute,
      missionLaunched: !!proposal.auto_execute,
      osintOnly: isOsintToolList(proposal?.plan?.tool_names),
    };
  }

  return opts.isLatestAssistant ? {} : undefined;
}
